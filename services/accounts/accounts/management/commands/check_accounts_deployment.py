from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Read-only production role/configuration preflight; sends no mail."

    def handle(self, *args, **options):
        if settings.DEBUG:
            raise CommandError("Production preflight requires DEBUG=0")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname = current_user"
            )
            flags = cursor.fetchone()
            cursor.execute(
                "SELECT has_schema_privilege(current_user, 'public', 'CREATE'), has_database_privilege(current_user, current_database(), 'CREATE')"
            )
            owner_flags = cursor.fetchone()
        if flags is None or any(flags) or any(owner_flags):
            raise CommandError(
                "Account runtime role must not have cluster administration or schema creation privileges"
            )
        delivery = (
            "managed mail delivery is disabled; no mail worker is required."
            if settings.ACCOUNT_MODE == "managed"
            and settings.MAIL_DELIVERY == "disabled"
            else "SMTP delivery remains untested."
        )
        self.stdout.write(
            "Production settings and runtime database role accepted; " + delivery
        )
