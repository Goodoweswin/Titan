from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        from .security import record_browser_auth

        user_logged_in.connect(
            record_browser_auth, dispatch_uid="accounts.record_browser_auth"
        )
