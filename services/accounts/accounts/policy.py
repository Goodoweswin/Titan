"""Deployment trust policy. Changing account mode also requires a new SESSION_EPOCH."""

from django.conf import settings


def account_eligible(user):
    if not user.is_active:
        return False
    if settings.ACCOUNT_MODE == "managed":
        return user.admin_provisioned
    return settings.ACCOUNT_MODE == "self_service" and user.verified_at is not None
