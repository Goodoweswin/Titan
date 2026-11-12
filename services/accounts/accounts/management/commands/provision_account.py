import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction

from accounts.forms import clean_name
from accounts.management.password_input import (
    PrivatePasswordCommand, normalized_email, read_password, validated_password,
)
from accounts.models import User


class Command(PrivatePasswordCommand):
    help = "Provision an ordinary managed account without asserting email verification."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--name", required=True)

    def handle(self, *args, **options):
        if settings.ACCOUNT_MODE != "managed":
            raise CommandError("Account provisioning requires managed mode.")
        email = normalized_email(options["email"])
        try:
            name = clean_name(options["name"])
        except ValidationError:
            raise CommandError("Provide a valid account name.") from None
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError("An account with this email already exists.")
        user = User(
            username=str(uuid.uuid4()), email=email, name=name,
            admin_provisioned=True, is_active=True, is_staff=False, is_superuser=False,
        )
        user.set_password(validated_password(read_password(options["password_stdin"]), user))
        try:
            with transaction.atomic():
                user.save(force_insert=True)
        except IntegrityError:
            raise CommandError("An account with this email already exists.") from None
        self.stdout.write("Managed account created.")
