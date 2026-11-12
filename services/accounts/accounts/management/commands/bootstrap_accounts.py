from django.core.management.base import BaseCommand
from oauth2_provider.models import Application


class Command(BaseCommand):
    help = "Create/update the fixed public desktop client. Does not create users or print secrets."

    def handle(self, *args, **options):
        Application.objects.update_or_create(
            client_id="titan-desktop",
            defaults={
                "name": "Titan Desktop",
                "client_type": "public",
                "authorization_grant_type": "authorization-code",
                "redirect_uris": "http://127.0.0.1/oauth/callback",
                "algorithm": "RS256",
                "skip_authorization": True,
            },
        )
        self.stdout.write("Titan desktop client configured.")
