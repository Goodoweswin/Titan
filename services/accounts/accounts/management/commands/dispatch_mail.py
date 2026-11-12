from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.mail import dispatch_batch


class Command(BaseCommand):
    help = "Send at most 50 pending messages once; run periodically without overlapping workers."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        if not settings.MAIL_DELIVERY_ENABLED:
            raise CommandError(
                "Mail delivery is disabled. Use dev_mail for local testing."
            )
        try:
            count = dispatch_batch(options["limit"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Delivered {count} messages.")
