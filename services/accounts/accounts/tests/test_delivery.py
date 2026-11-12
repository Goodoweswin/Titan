"""Launcher persistence and operator preflight boundaries; no production changes."""

import importlib.util
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command

REPO = Path(__file__).resolve().parents[4]
LAUNCHER = REPO / "deploy/accounts/scripts/local.py"


def launcher_module():
    spec = importlib.util.spec_from_file_location("accounts_local_launcher", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("mode", [None, "self_service", "managed"])
def test_local_init_persists_explicit_account_mode_without_smtp(
    tmp_path, monkeypatch, mode
):
    module = launcher_module()
    root = tmp_path / "private-local"

    # Keep the real parser/config writes; external resource provisioning is
    # exercised separately by the isolated real launcher drill.
    def provision(command, **kwargs):
        if command[0] == "openssl":
            (root / "signing.pem").write_text("synthetic-key-not-used")

    monkeypatch.setattr(module, "invoke", provision)
    argv = [str(LAUNCHER), "init", "--directory", str(root)]
    if mode is not None:
        argv += ["--account-mode", mode]
    monkeypatch.setattr(sys, "argv", argv)
    module.main()
    config = json.loads((root / "service.json").read_text())
    assert config["ACCOUNTS_ACCOUNT_MODE"] == (mode or "self_service")
    assert config["ACCOUNTS_MAIL_DELIVERY"] == "disabled"
    assert not any("SMTP" in key or key == "ACCOUNTS_FROM_EMAIL" for key in config)
    assert root.stat().st_mode & 0o777 == 0o700
    for name in ("service.json", "launch.json", "signing.pem"):
        assert (root / name).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "command,mode",
    [
        ("init", "invalid"),
        ("start", "managed"),
        ("stop", "managed"),
        ("status", "self_service"),
    ],
)
def test_mode_errors_precede_files_and_processes(tmp_path, command, mode):
    root = tmp_path / "must-not-exist"
    # Empty PATH establishes that no external launcher command can run.
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            command,
            "--directory",
            str(root),
            "--account-mode",
            mode,
        ],
        env={**os.environ, "PATH": ""},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert not root.exists()
    expected = "invalid choice" if command == "init" else "only valid for init"
    assert expected in result.stderr


@pytest.mark.parametrize(
    "mode,delivery,expected",
    [
        ("managed", "disabled", "mail delivery is disabled"),
        ("managed", "smtp", "SMTP delivery remains untested"),
        ("self_service", "smtp", "SMTP delivery remains untested"),
    ],
)
def test_production_preflight_success_describes_selected_delivery(
    settings, mode, delivery, expected
):
    from accounts.management.commands import check_accounts_deployment as preflight

    settings.DEBUG = False
    settings.ACCOUNT_MODE = mode
    settings.MAIL_DELIVERY = delivery

    class Cursor:
        def execute(self, query):
            self.role_query = "pg_roles" in query

        def fetchone(self):
            return (False, False, False, False) if self.role_query else (False, False)

    @contextmanager
    def cursor():
        yield Cursor()

    output = StringIO()
    with patch.object(preflight.connection, "cursor", cursor):
        call_command("check_accounts_deployment", stdout=output)
    assert expected in output.getvalue()
    if delivery == "disabled":
        assert "SMTP" not in output.getvalue()


@pytest.mark.parametrize(
    "roles,ownership",
    [
        ((True, False, False, False), (False, False)),
        ((False, True, False, False), (False, False)),
        ((False, False, True, False), (False, False)),
        ((False, False, False, True), (False, False)),
        ((False, False, False, False), (True, False)),
        ((False, False, False, False), (False, True)),
        (None, (False, False)),
    ],
)
def test_managed_preflight_still_rejects_privileged_roles(settings, roles, ownership):
    from accounts.management.commands import check_accounts_deployment as preflight

    settings.DEBUG = False
    settings.ACCOUNT_MODE = "managed"
    settings.MAIL_DELIVERY = "disabled"

    class Cursor:
        def execute(self, query):
            self.role_query = "pg_roles" in query

        def fetchone(self):
            return roles if self.role_query else ownership

    @contextmanager
    def cursor():
        yield Cursor()

    with (
        patch.object(preflight.connection, "cursor", cursor),
        pytest.raises(CommandError),
    ):
        call_command("check_accounts_deployment", stdout=StringIO())
