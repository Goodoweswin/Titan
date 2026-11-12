import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import MailOutbox


class Command(BaseCommand):
    help = "Local-only: list outbox IDs, or export one message to a private file. Never exposes an HTTP mailbox."

    def add_arguments(self, parser):
        parser.add_argument("id", nargs="?")
        parser.add_argument("--output")

    def handle(self, *args, **options):
        if not settings.DEBUG or settings.MAIL_DELIVERY_ENABLED:
            raise CommandError(
                "Dev mail is available only in local debug mode with delivery disabled."
            )
        if not options["id"]:
            for row in MailOutbox.objects.filter(sent_at__isnull=True).order_by(
                "-created_at"
            )[:20]:
                self.stdout.write(str(row.pk))
            return
        if not options["output"]:
            raise CommandError(
                "--output is required; message bodies are never printed."
            )
        try:
            row = MailOutbox.objects.get(pk=options["id"])
        except (MailOutbox.DoesNotExist, ValueError) as exc:
            raise CommandError("Message not found.") from exc
        fd = os.open(options["output"], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(f"To: {row.recipient}\nSubject: {row.subject}\n\n{row.body}\n")
        self.stdout.write("Message exported to a private file.")
