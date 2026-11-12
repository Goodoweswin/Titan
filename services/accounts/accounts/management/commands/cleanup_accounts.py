from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import (
    DeviceSession,
    GrantContext,
    MailOutbox,
    OneTimeToken,
    RateLimit,
)


class Command(BaseCommand):
    help = "Remove expired account state; keep replay tombstones until family absolute expiry."

    def handle(self, *args, **options):
        now = timezone.now()
        # Binding rows cascade only after absolute expiry, never merely on rotation/revocation.
        DeviceSession.objects.filter(expires_at__lt=now - timedelta(days=1)).delete()
        GrantContext.objects.filter(created_at__lt=now - timedelta(minutes=5)).delete()
        OneTimeToken.objects.filter(expires_at__lt=now).delete()
        RateLimit.objects.filter(started_at__lt=now - timedelta(days=1)).delete()
        MailOutbox.objects.filter(expires_at__lt=now).exclude(body="").update(body="")
        MailOutbox.objects.filter(expires_at__lt=now - timedelta(days=1)).delete()
        call_command("cleartokens", verbosity=0)
        call_command("clearsessions", verbosity=0)
        self.stdout.write("Expired account state cleaned.")
