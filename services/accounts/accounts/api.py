import json
from functools import wraps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.models import AccessToken

from .forms import clean_name
from .models import DeviceSession, TokenBinding, User
from .policy import account_eligible
from .security import digest, error, live, revoke


def protected(methods):
    def decorate(view):
        @csrf_exempt
        @wraps(view)
        def handle(request, *args, **kwargs):
            if request.method not in methods:
                return error("method_not_allowed", "Method not allowed.", 405)
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer ") or len(header) > 4096:
                return error("unauthorized", "Please sign in again.", 401)
            checksum = digest(header[7:])
            binding = (
                TokenBinding.objects.select_related("session__user")
                .filter(pk=checksum, kind="access")
                .first()
            )
            access = AccessToken.objects.filter(
                token_checksum=checksum, expires__gt=timezone.now()
            ).first()
            if not binding or not access or not live(binding.session):
                return error("unauthorized", "Please sign in again.", 401)
            with transaction.atomic():
                User.objects.select_for_update().get(pk=binding.session.user_id)
                family = DeviceSession.objects.select_related("user").get(
                    pk=binding.session_id
                )
                if not live(family):
                    return error("unauthorized", "Please sign in again.", 401)
                request.account_session = family
                request.account_user = family.user
                DeviceSession.objects.filter(pk=family.pk).update(
                    last_seen_at=timezone.now()
                )
                return view(request, *args, **kwargs)

        return handle

    return decorate


def profile(request):
    user = request.account_user
    return {
        "id": str(user.pk),
        "name": user.name,
        "email": user.email,
        "createdAt": user.date_joined.isoformat(),
        "emailVerified": user.verified_at is not None,
        "administratorApproved": settings.ACCOUNT_MODE == "managed" and account_eligible(user),
        "sessionId": str(request.account_session.pk),
    }


@protected(["GET", "PATCH"])
def me(request):
    if request.method == "PATCH":
        try:
            body = json.loads(request.body)
            if not isinstance(body, dict) or set(body) != {"name"}:
                raise ValidationError("Only name can be changed.")
            request.account_user.name = clean_name(body["name"])
        except (ValueError, TypeError, ValidationError):
            return error("invalid_profile", "Provide a name of 1–60 characters.", 400)
        request.account_user.save(update_fields=["name"])
    return JsonResponse(profile(request))


@protected(["GET"])
def sessions(request):
    rows = DeviceSession.objects.filter(
        user=request.account_user,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).order_by("-created_at")
    return JsonResponse(
        {
            "sessions": [
                {
                    "id": str(row.pk),
                    "label": row.label,
                    "platform": row.platform,
                    "createdAt": row.created_at.isoformat(),
                    "lastSeenAt": row.last_seen_at.isoformat(),
                    "expiresAt": row.expires_at.isoformat(),
                    "current": row.pk == request.account_session.pk,
                }
                for row in rows
                if live(row)
            ]
        }
    )


@protected(["DELETE"])
def delete_session(request, session_id):
    row = DeviceSession.objects.filter(pk=session_id, user=request.account_user).first()
    if not row:
        return error("not_found", "Session not found.", 404)
    revoke(row)
    return HttpResponse(status=204)


@protected(["POST"])
def revoke_all(request):
    if (
        not 0
        <= (timezone.now() - request.account_session.auth_time).total_seconds()
        <= 300
    ):
        return error(
            "recent_auth_required", "Sign in again before revoking all sessions.", 403
        )
    DeviceSession.objects.filter(
        user=request.account_user, revoked_at__isnull=True
    ).update(revoked_at=timezone.now())
    return HttpResponse(status=204)
