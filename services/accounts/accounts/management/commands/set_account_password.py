from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from accounts.management.password_input import (
    PrivatePasswordCommand, normalized_email, read_password, validated_password,
)
from accounts.models import DeviceSession, User


class Command(PrivatePasswordCommand):
    help = "Reset an existing account password and invalidate all its credentials."

    def handle(self, *args, **options):
        email = normalized_email(options["email"])
        password = read_password(options["password_stdin"])
        with transaction.atomic():
            user = User.objects.select_for_update().filter(email__iexact=email).first()
            if user is None:
                raise CommandError("Account not found.")
            user.set_password(validated_password(password, user))
            user.save(update_fields=["password"])
            DeviceSession.objects.filter(user=user, revoked_at__isnull=True).update(
                revoked_at=timezone.now()
            )
        self.stdout.write("Password updated; existing credentials invalidated.")
