"""Private administrator input; never fall back to echoed password entry."""

import getpass
import sys
import warnings

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.forms import EmailForm


class PrivatePasswordCommand(BaseCommand):
    def create_parser(self, prog_name, subcommand, **kwargs):
        parser = super().create_parser(prog_name, subcommand, allow_abbrev=False, **kwargs)
        original_error = parser.error

        def private_error(_message):
            # Argparse errors interpolate rejected values, including accidental
            # argv passwords. Preserve CLI/CommandError behavior without the values.
            original_error(
                "Invalid arguments. Use --help; passwords require hidden input or --password-stdin."
            )

        parser.error = private_error
        return parser

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument(
            "--password-stdin", action="store_true",
            help="Read one password from private stdin instead of hidden terminal prompts.",
        )


def normalized_email(value):
    form = EmailForm({"email": value})
    if not form.is_valid():
        raise CommandError("Provide a valid email address.")
    return form.cleaned_data["email"].strip().lower()


def read_password(from_stdin):
    try:
        if from_stdin:
            if sys.stdin.isatty():
                raise CommandError(
                    "Use default hidden input with confirmation in a terminal; "
                    "omit --password-stdin."
                )
            password = sys.stdin.read(1027)
            if password.endswith("\n"):
                password = password[:-1]
                if password.endswith("\r"):
                    password = password[:-1]
        else:
            if not sys.stdin.isatty():
                raise CommandError("Use a terminal or explicitly provide --password-stdin.")
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                password = getpass.getpass("Password: ")
                confirmation = getpass.getpass("Confirm password: ")
            if password != confirmation:
                raise CommandError("Passwords do not match.")
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        raise CommandError("Private password input unavailable or cancelled.") from None
    if not 1 <= len(password) <= 1024 or "\n" in password or "\r" in password:
        raise CommandError("Provide one password of at most 1024 characters.")
    return password


def validated_password(password, user):
    try:
        validate_password(password, user=user)
    except ValidationError:
        # Validators may be customized; never print potentially secret-bearing text.
        raise CommandError("Password does not meet the account password requirements.") from None
    return password
