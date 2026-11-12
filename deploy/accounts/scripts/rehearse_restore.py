#!/usr/bin/env python3
"""Real PostgreSQL + age drill using disposable source AND restored databases.
Use account venv and PG* admin connection. Neither local port8000 nor live DB changes.
"""

import argparse
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPTS = Path(__file__).resolve().parent


def run(argv, **kwargs):
    return subprocess.run([str(x) for x in argv], check=True, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory", type=Path, required=True)
    a = p.parse_args()
    root = a.directory.resolve()
    root.mkdir(mode=0o700)
    suffix = secrets.token_hex(6)
    source = "titan_accounts_rehearsal_" + suffix
    target = "titan_accounts_restore_" + suffix
    run(["createdb", source])
    os.environ.update(
        PGDATABASE=source,
        ACCOUNTS_DEBUG="1",
        ACCOUNTS_ISSUER="http://testserver",
        ACCOUNTS_ALLOWED_HOSTS="testserver",
        ACCOUNTS_SESSION_EPOCH="test-epoch",
        ACCOUNTS_MAIL_DELIVERY="disabled",
        DJANGO_SETTINGS_MODULE="config.test_settings",
    )
    sys.path.insert(0, str(REPO / "services/accounts"))
    import django

    django.setup()
    from urllib.parse import parse_qs, urlparse

    from accounts.mail import enqueue_link
    from accounts.models import MailOutbox
    from accounts.tests.test_endpoints import authorize, mint
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.db import connections
    from django.test import Client
    from django.utils import timezone
    from oauth2_provider.models import Application

    call_command("migrate", verbosity=0)
    call_command("bootstrap_accounts", verbosity=0)
    user = get_user_model().objects.create_user(
        username="restore-drill",
        email="restore@example.invalid",
        password=secrets.token_urlsafe(24),
        name="Restore drill",
        verified_at=timezone.now(),
    )
    app = Application.objects.get(client_id="titan-desktop")
    browser = Client()
    tokens, _ = mint(browser, user, app)
    authorization = authorize(browser, user, app)
    code = parse_qs(urlparse(authorization["Location"]).query)["code"][0]
    enqueue_link(user, "reset")
    body = MailOutbox.objects.latest("created_at").body
    reset_path = urlparse(body.splitlines()[1]).path
    private = root / "old-credentials.json"
    private.touch(mode=0o600)
    private.write_text(
        json.dumps(
            {
                "tokens": tokens,
                "code": code,
                "reset_path": reset_path,
                "cookie": browser.cookies["titan_accounts_session"].value,
            }
        )
    )
    identity = root / "backup.agekey"
    run(["age-keygen", "-o", identity], stderr=subprocess.DEVNULL)
    recipient = subprocess.check_output(
        ["age-keygen", "-y", str(identity)], text=True
    ).strip()
    backup = root / "fixture.dump.age"
    run(
        [
            sys.executable,
            SCRIPTS / "backup_restore.py",
            "backup",
            "--output",
            backup,
            "--recipient",
            recipient,
        ]
    )
    epoch = root / "restore.env"
    restore = [
        sys.executable,
        SCRIPTS / "backup_restore.py",
        "restore",
        "--input",
        backup,
        "--identity",
        identity,
        "--database",
        target,
        "--epoch-file",
        epoch,
    ]
    run(restore)
    restored = dict(line.split("=", 1) for line in epoch.read_text().splitlines())
    assert restored["ACCOUNTS_SESSION_EPOCH"] != os.environ["ACCOUNTS_SESSION_EPOCH"]
    probe = r"""
import json, os, django
from pathlib import Path
django.setup()
from django.test import Client
from accounts.models import User
from accounts.tests.test_endpoints import CALLBACK, VERIFIER
old=json.loads(Path(os.environ['DRILL_CREDENTIALS']).read_text())
c=Client()
assert User.objects.filter(email='restore@example.invalid').exists()
assert c.get('/api/v1/me', HTTP_AUTHORIZATION='Bearer '+old['tokens']['access_token']).status_code == 401
assert c.post('/o/token/', {'grant_type':'refresh_token', 'client_id':'titan-desktop', 'refresh_token':old['tokens']['refresh_token']}).status_code == 400
assert c.post('/o/token/', {'grant_type':'authorization_code', 'client_id':'titan-desktop', 'code':old['code'], 'redirect_uri':CALLBACK, 'code_verifier':VERIFIER}).status_code == 400
assert c.post(old['reset_path'], {'password':'Restored-Strong-Password-928!'}).status_code == 400
c.cookies['titan_accounts_session']=old['cookie']
c.get('/login')
assert '_auth_user_id' not in c.session
print('Restored user preserved; old access/refresh/code/browser/reset credentials all rejected.')
"""
    env = dict(os.environ, **restored, DRILL_CREDENTIALS=str(private))
    run([sys.executable, "-c", probe], cwd=REPO / "services/accounts", env=env)
    # An existing destination must fail; the source fixture remains untouched.
    repeat = subprocess.run(
        restore[:-1] + [str(root / "must-not-exist.env")], capture_output=True
    )
    assert repeat.returncode != 0
    assert not (root / "must-not-exist.env").exists()
    assert User_count() == 1
    connections.close_all()
    result = {
        "source": source,
        "restore": target,
        "age_version": subprocess.check_output(["age", "--version"], text=True).strip(),
        "old_credentials_rejected": ["access", "refresh", "code", "browser", "reset"],
        "existing_destination_refused": True,
        "source_unchanged": True,
        "source_and_restore_removed_after_verification": True,
    }
    run(["dropdb", target])
    run(["dropdb", source])
    private.unlink()
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Restore drill passed; only the two disposable databases were removed.")


def User_count():
    from accounts.models import User

    return User.objects.count()


if __name__ == "__main__":
    main()
