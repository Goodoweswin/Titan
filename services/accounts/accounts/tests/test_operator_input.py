"""Exercise administrator input ownership through real CLI and documented wrappers."""

import io
import json
import os
import re
import select
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings

from accounts.models import DeviceSession, MailOutbox, OneTimeToken, User
from .test_endpoints import PASSWORD

REPO = Path(__file__).resolve().parents[4]
SERVICE = REPO / "services/accounts"
EMAIL = "operator-input@example.invalid"
RESET_PASSWORD = "Synthetic-Operator-Reset-42!"


def command_arguments(command):
    args = [command, "--email", EMAIL]
    if command == "provision_account":
        args += ["--name", "Operator"]
    return args


def private_cli_config():
    database = connection.settings_dict
    # Subprocesses must use only pytest's disposable DB, never the base database.
    assert database["NAME"].startswith("test_")
    return {
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "ACCOUNTS_ACCOUNT_MODE": "managed",
        "ACCOUNTS_MAIL_DELIVERY": "disabled",
        **{
            "PG" + key: str(database[value] or "")
            for key, value in {
                "DATABASE": "NAME", "HOST": "HOST", "PORT": "PORT",
                "USER": "USER", "PASSWORD": "PASSWORD",
            }.items()
        },
    }


def account_state():
    return (
        list(User.objects.order_by("pk").values()),
        list(DeviceSession.objects.order_by("pk").values()),
        list(OneTimeToken.objects.order_by("pk").values()),
        list(MailOutbox.objects.order_by("pk").values()),
    )


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
@pytest.mark.parametrize("command", ["provision_account", "set_account_password"])
def test_explicit_password_stdin_rejects_tty_before_read_without_mutation(
    monkeypatch, user, command
):
    class UnreadableTerminal(io.StringIO):
        def isatty(self):
            return True

        def read(self, *args):
            pytest.fail("Explicit stdin attempted to read an echo-enabled terminal")

    monkeypatch.setattr(sys, "stdin", UnreadableTerminal())
    arguments = command_arguments(command)
    if command == "set_account_password":
        arguments[2] = user.email
    before = account_state()
    with pytest.raises(CommandError, match="hidden.*confirm"):
        call_command(*arguments, password_stdin=True)
    assert account_state() == before


class TerminalChild:
    """Keep terminal input/output private; send only while the child owns input."""

    def __init__(self, arguments, env, queued_input=None):
        pty = pytest.importorskip("pty")
        self.termios = pytest.importorskip("termios")
        fcntl = pytest.importorskip("fcntl")
        self.master, self.slave = pty.openpty()
        self.output = bytearray()
        if queued_input is not None:
            attributes = self.termios.tcgetattr(self.slave)
            attributes[3] &= ~self.termios.ECHO
            self.termios.tcsetattr(self.slave, self.termios.TCSANOW, attributes)
            os.write(self.master, queued_input)
            # The canary is queued before starting a child, while echo is off.
            # Its rejection must leave it unread on this now echo-enabled TTY.
            attributes[3] |= self.termios.ECHO
            self.termios.tcsetattr(self.slave, self.termios.TCSANOW, attributes)

        def own_terminal():
            os.setsid()
            fcntl.ioctl(0, self.termios.TIOCSCTTY, 0)

        self.process = subprocess.Popen(
            arguments, stdin=self.slave, stdout=self.slave, stderr=self.slave,
            cwd=REPO, env=env,
            # Acquiring a controlling terminal can flush prequeued input on
            # macOS. Explicit stdin needs a real TTY, not /dev/tty ownership.
            preexec_fn=own_terminal if queued_input is None else None,
        )

    def read_until(self, marker):
        deadline = time.monotonic() + 10
        while marker not in self.output and time.monotonic() < deadline:
            if select.select([self.master], [], [], 0.1)[0]:
                self.output.extend(os.read(self.master, 4096))
            elif self.process.poll() is not None:
                break
        return marker in self.output

    def hidden_input(self, prompt, password):
        assert self.read_until(prompt), "Documented wrapper did not reach hidden prompt"
        assert self.process.poll() is None, "Child exited before input ownership check"
        assert not self.termios.tcgetattr(self.slave)[3] & self.termios.ECHO
        os.write(self.master, password.encode() + b"\n")

    def finish(self):
        # Drain while waiting: macOS terminal teardown can wait for output to
        # drain, so wait-before-read can deadlock even on a tiny error message.
        self.read_until(b"\x00UNREACHABLE-TERMINAL-MARKER\x00")
        return self.process.wait(timeout=1)

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
        os.close(self.master)
        os.close(self.slave)
        self.process.wait(timeout=5)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("command", ["provision_account", "set_account_password"])
def test_real_echo_enabled_tty_rejection_leaves_input_and_account_untouched(user, command):
    arguments = command_arguments(command)
    if command == "set_account_password":
        arguments[2] = user.email
    before = account_state()
    queued = PASSWORD.encode() + b"\n"
    child = TerminalChild(
        [sys.executable, str(SERVICE / "manage.py"), *arguments, "--password-stdin"],
        {**os.environ, **private_cli_config()}, queued_input=queued + b"\x04",
    )
    try:
        assert child.termios.tcgetattr(child.slave)[3] & child.termios.ECHO
        assert child.finish() == 1
        assert b"hidden" in child.output and b"confirm" in child.output
        canary_absent = PASSWORD.encode() not in child.output
        assert canary_absent, "Terminal output exposed the synthetic input"
        assert select.select([child.slave], [], [], 1)[0], "Rejected command consumed input"
        input_untouched = os.read(child.slave, 4096) == queued
        assert input_untouched, "Rejected command changed queued terminal input"
        assert account_state() == before
    finally:
        child.close()


def documented_command(tmp_path, command, private_file=None):
    root = tmp_path / "private-local"
    root.mkdir(mode=0o700)
    (root / "venv").symlink_to(sys.prefix, target_is_directory=True)
    config = root / "service.json"
    config.write_text(json.dumps(private_cli_config()))
    config.chmod(0o600)
    readme = (REPO / "deploy/accounts/README.md").read_text()
    section = readme.split("To run a management command with this launcher configuration:", 1)[1]
    # Execute the actual documented shell wrapper, changing only its sample
    # directory and management command to this disposable synthetic account.
    wrapper = re.search(r"```sh\n(.*?)\n```", section, re.S).group(1)
    invocation = shlex.join(command_arguments(command))
    if private_file is not None:
        invocation += " --password-stdin < " + shlex.quote(str(private_file))
    return wrapper.replace("/tmp/titan-accounts-demo", shlex.quote(str(root))).replace(
        "dev_mail", invocation
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("command", ["provision_account", "set_account_password"])
@pytest.mark.parametrize("input_mode", ["hidden", "private_file"])
def test_documented_local_wrapper_preserves_hidden_and_redirected_input(
    tmp_path, command, input_mode
):
    if command == "set_account_password":
        User.objects.create_user(username="operator", email=EMAIL, password=PASSWORD)
    password = RESET_PASSWORD
    if input_mode == "hidden":
        script = documented_command(tmp_path, command)
        child = TerminalChild(["sh", "-c", script], dict(os.environ))
        try:
            child.hidden_input(b"Password: ", password)
            child.hidden_input(b"Confirm password: ", password)
            assert child.finish() == 0
            secret_absent = password.encode() not in child.output
            assert secret_absent, "Documented terminal workflow exposed synthetic input"
        finally:
            child.close()
    else:
        private_file = tmp_path / "password-input"
        private_file.write_text(password + "\n")
        private_file.chmod(0o600)
        try:
            # Redirect at the shell invocation, exactly as a local operator does.
            script = documented_command(tmp_path, command, private_file)
            result = subprocess.run(
                ["sh", "-c", script], cwd=REPO, capture_output=True, text=True, timeout=10,
            )
            assert result.returncode == 0
            secret_absent = password not in result.stdout + result.stderr
            assert secret_absent, "Documented file workflow exposed synthetic input"
        finally:
            private_file.unlink()
    user = User.objects.get(email=EMAIL)
    assert user.check_password(password)
    if command == "provision_account":
        assert user.admin_provisioned and user.verified_at is None
        assert not user.is_staff and not user.is_superuser
    else:
        assert not user.check_password(PASSWORD)
    assert not MailOutbox.objects.exists() and not OneTimeToken.objects.exists()
