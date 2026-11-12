#!/usr/bin/env python3
"""Disposable loopback/no-mail environment. Never uses the science venv or port8000."""

import argparse
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SERVICE = REPO / "services/accounts"


def invoke(command, **kwargs):
    subprocess.run([str(x) for x in command], check=True, **kwargs)


def private(path, contents):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(contents)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["init", "start", "stop", "status"])
    p.add_argument("--directory", type=Path, required=True)
    p.add_argument("--port", type=int, default=18081)
    p.add_argument("--pg-port", type=int, default=55433)
    p.add_argument(
        "--pg-bin",
        type=Path,
        default=Path(
            shutil.which("initdb") or "/opt/homebrew/opt/postgresql@17/bin/initdb"
        ).parent,
    )
    a = p.parse_args()
    root = a.directory.resolve()
    if a.command == "init":
        if (
            not (1024 <= a.port <= 65535 and 1024 <= a.pg_port <= 65535)
            or a.port == a.pg_port
        ):
            p.error("Distinct unprivileged ports required")
        root.mkdir(mode=0o700)  # Existing directory is never overwritten.
        env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(root / "venv"))
        invoke(["uv", "sync", "--project", SERVICE, "--frozen"], env=env)
        invoke(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
                "-out",
                root / "signing.pem",
            ],
            stderr=subprocess.DEVNULL,
        )
        (root / "signing.pem").chmod(0o600)
        config = {
            "ACCOUNTS_DEBUG": "1",
            "ACCOUNTS_ISSUER": f"http://127.0.0.1:{a.port}",
            "ACCOUNTS_ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
            "ACCOUNTS_SECRET_KEY": secrets.token_urlsafe(64),
            "ACCOUNTS_SESSION_EPOCH": secrets.token_urlsafe(48),
            "ACCOUNTS_RSA_KEY_FILE": str(root / "signing.pem"),
            "ACCOUNTS_MAIL_DELIVERY": "disabled",
            "PGHOST": "127.0.0.1",
            "PGPORT": str(a.pg_port),
            "PGDATABASE": "titan_accounts_local",
            "PGUSER": "titan_accounts_local",
            "PGPASSWORD": "",
        }
        private(root / "service.json", json.dumps(config))
        private(
            root / "launch.json",
            json.dumps({"port": a.port, "pg_port": a.pg_port, "pg_bin": str(a.pg_bin)}),
        )
        invoke(
            [
                a.pg_bin / "initdb",
                "-D",
                root / "pgdata",
                "-U",
                "titan_accounts_local",
                "--auth-local=trust",
                "--auth-host=trust",
            ],
            stdout=subprocess.DEVNULL,
        )
        print("Private disposable local environment initialized; mail is disabled.")
        return
    config = json.loads((root / "service.json").read_text())
    launch = json.loads((root / "launch.json").read_text())
    pg = Path(launch["pg_bin"])
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ACCOUNTS_", "PG"))}
    env.update(config)
    pg_args = [pg / "pg_ctl", "-D", root / "pgdata"]
    pidfile = root / "gunicorn.pid"
    if a.command == "start":
        invoke(
            pg_args
            + [
                "-l",
                root / "postgres.log",
                "-o",
                f"-h 127.0.0.1 -p {launch['pg_port']} -c unix_socket_directories={root} -c shared_buffers=32MB -c max_connections=20",
                "start",
            ]
        )
        check = subprocess.run(
            [
                str(pg / "psql"),
                "-d",
                "postgres",
                "-tAc",
                "SELECT 1 FROM pg_database WHERE datname='titan_accounts_local'",
            ],
            env=env,
            capture_output=True,
            check=True,
        )
        if check.stdout.strip() != b"1":
            invoke([pg / "createdb", "titan_accounts_local"], env=env)
        for command in ["migrate", "bootstrap_accounts"]:
            invoke(
                [root / "venv/bin/python", "manage.py", command], cwd=SERVICE, env=env
            )
        invoke(
            [
                root / "venv/bin/gunicorn",
                "config.wsgi:application",
                "--chdir",
                SERVICE,
                "--bind",
                f"127.0.0.1:{launch['port']}",
                "--workers",
                "1",
                "--threads",
                "2",
                "--forwarded-allow-ips",
                "",
                "--daemon",
                "--pid",
                pidfile,
                "--error-logfile",
                root / "gunicorn-error.log",
            ],
            env=env,
        )
        print(f"Local issuer running at http://127.0.0.1:{launch['port']}; no SMTP.")
    elif a.command == "stop":
        if pidfile.exists():
            pid = int(pidfile.read_text())
            process = subprocess.run(
                ["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True
            )
            if str(pidfile) not in process.stdout or "gunicorn" not in process.stdout:
                raise RuntimeError(
                    "PID ownership could not be established; no process killed"
                )
            os.kill(pid, signal.SIGTERM)
        invoke(pg_args + ["stop", "-m", "fast"])
    else:
        invoke(pg_args + ["status"])
        print("Gunicorn PID file present:", pidfile.exists())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            "Local operation failed ("
            + type(exc).__name__
            + "); inspect private logs.",
            file=sys.stderr,
        )
        sys.exit(1)
