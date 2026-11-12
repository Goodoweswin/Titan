#!/usr/bin/env python3
"""Stream PostgreSQL custom dumps through age; restore ONLY into a fresh DB.
Requires pg_dump/pg_restore/createdb and age on PATH. PG* is the source/admin
connection. Credentials belong in a private .pgpass or environment, never argv.
"""

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(args, **kwargs):
    return subprocess.run(args, check=True, stderr=subprocess.DEVNULL, **kwargs)


def pipeline(left, right, output=None):
    first = subprocess.Popen(left, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        result = subprocess.run(
            right, stdin=first.stdout, stdout=output, stderr=subprocess.DEVNULL
        )
        first.stdout.close()
        status = first.wait()
        if status or result.returncode:
            raise RuntimeError(
                "Backup/restore pipeline failed; inspect isolated destination offline"
            )
    finally:
        if first.poll() is None:
            first.terminate()
            first.wait()


def private_write(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)


def backup(args):
    output = Path(args.output)
    if not os.environ.get("PGDATABASE"):
        raise ValueError("Explicit PGDATABASE is required")
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            pipeline(
                ["pg_dump", "--format=custom", "--no-owner", "--no-acl"],
                ["age", "--encrypt", "--recipient", args.recipient],
                handle,
            )
        with output.open("rb") as handle:
            checksum = hashlib.file_digest(handle, "sha256").hexdigest()
        private_write(
            str(output) + ".json",
            json.dumps(
                {
                    "format": "postgres-custom+age-v1",
                    "sha256": checksum,
                    "source_database": os.environ["PGDATABASE"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "restore_requires_new_session_epoch": True,
                },
                indent=2,
            )
            + "\n",
        )
    except Exception:
        output.unlink(missing_ok=True)
        raise
    print("Encrypted backup and checksum manifest created.")


def restore(args):
    # No force, clean, overwrite or production-name option exists by design.
    if not re.fullmatch(r"titan_accounts_restore_[a-z0-9_]{1,48}", args.database):
        raise ValueError("Restore database must have titan_accounts_restore_ prefix")
    if args.database == os.environ.get("PGDATABASE"):
        raise ValueError("Cannot restore over source database")
    epoch_file = Path(args.epoch_file)
    if epoch_file.exists() or epoch_file.is_symlink():
        raise ValueError("Epoch destination must not already exist")
    source = Path(args.input)
    manifest = json.loads(Path(str(source) + ".json").read_text())
    with source.open("rb") as handle:
        checksum = hashlib.file_digest(handle, "sha256").hexdigest()
    if checksum != manifest["sha256"]:
        raise ValueError("Backup checksum mismatch")
    # createdb fails if target exists, BEFORE decrypting or restoring anything.
    run(["createdb", "--template=template0", args.database])
    pipeline(
        ["age", "--decrypt", "--identity", args.identity, str(source)],
        [
            "pg_restore",
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-acl",
            "--dbname",
            args.database,
        ],
        subprocess.DEVNULL,
    )
    # No service is started. Operator must explicitly use BOTH target and new epoch.
    private_write(
        epoch_file,
        "PGDATABASE="
        + args.database
        + "\nACCOUNTS_SESSION_EPOCH="
        + secrets.token_urlsafe(48)
        + "\n",
    )
    print(
        "Restored into fresh isolated database; private new-epoch env created. No service started."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("backup")
    create.add_argument("--output", required=True)
    create.add_argument("--recipient", required=True)
    load = sub.add_parser("restore")
    load.add_argument("--input", required=True)
    load.add_argument("--identity", required=True)
    load.add_argument("--database", required=True)
    load.add_argument("--epoch-file", required=True)
    args = parser.parse_args()
    try:
        (backup if args.command == "backup" else restore)(args)
    except Exception as exc:
        # Do not emit subprocess stderr, connection data, or decrypted material.
        print(
            "Operation failed ("
            + type(exc).__name__
            + "). No live database overwritten.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
