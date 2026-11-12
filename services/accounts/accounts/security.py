import hashlib
import uuid

from django.conf import settings
from django.contrib.auth import logout
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.utils import timezone

from .models import DeviceSession, RateLimit


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def error(code, message, status):
    response = JsonResponse(
        {"code": code, "message": message, "request_id": str(uuid.uuid4())},
        status=status,
    )
    response["Cache-Control"] = "no-store"
    return response


def live(session):
    user = session.user
    return (
        user.is_active
        and user.verified_at is not None
        and session.revoked_at is None
        and session.expires_at > timezone.now()
        and session.epoch == settings.SESSION_EPOCH
        and session.credential == user.get_session_auth_hash()
    )


def revoke(session):
    DeviceSession.objects.filter(pk=session.pk, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )


def rate_limit(request, action, identifier="", limit=10, seconds=900):
    # Proxy address headers are intentionally ignored. Trust must be established at gateway.
    now = timezone.now()
    keys = [digest(action + ":ip:" + request.META.get("REMOTE_ADDR", "unknown"))]
    if identifier:
        keys.append(digest(action + ":account:" + identifier.strip().lower()))
    allowed = True
    with transaction.atomic():
        for key in sorted(keys):
            RateLimit.objects.get_or_create(key=key, defaults={"started_at": now})
            row = RateLimit.objects.select_for_update().get(pk=key)
            if (now - row.started_at).total_seconds() >= seconds:
                row.started_at = now
                row.count = 0
            row.count += 1
            row.save(update_fields=["started_at", "count"])
            allowed = allowed and row.count <= limit
    return allowed


class BrowserEpochMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def process_exception(self, request, exception):
        if isinstance(exception, DatabaseError):
            if request.path.startswith("/o/"):
                return JsonResponse({"error": "temporarily_unavailable"}, status=503)
            return error("unavailable", "Account service temporarily unavailable.", 503)
        return None

    def __call__(self, request):
        try:
            if (
                request.user.is_authenticated
                and request.session.get("epoch") != settings.SESSION_EPOCH
            ):
                logout(request)
            response = self.get_response(request)
        except DatabaseError:
            return error("unavailable", "Account service temporarily unavailable.", 503)
        response["Referrer-Policy"] = "no-referrer"
        response["Cache-Control"] = "no-store"
        return response


def record_browser_auth(sender, request, user, **kwargs):
    request.session["epoch"] = settings.SESSION_EPOCH
    request.session["auth_time"] = int(timezone.now().timestamp())
