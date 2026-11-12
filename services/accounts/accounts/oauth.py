import json
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.oauth2_validators import OAuth2Validator
from oauth2_provider.views import AuthorizationView, ConnectDiscoveryInfoView, TokenView

from .models import DeviceSession, GrantContext, TokenBinding, User
from .security import digest, live, rate_limit, revoke


def loopback(uri):
    try:
        parsed = urlsplit(uri)
        return (
            parsed.scheme == "http"
            and parsed.hostname == "127.0.0.1"
            and parsed.path == "/oauth/callback"
            and parsed.port is not None
            and 1 <= parsed.port <= 65535
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.netloc == f"127.0.0.1:{parsed.port}"
        )
    except (ValueError, TypeError):
        return False


class Validator(OAuth2Validator):
    def validate_client_id(self, client_id, request, *args, **kwargs):
        return client_id == "titan-desktop" and super().validate_client_id(
            client_id, request, *args, **kwargs
        )

    def authenticate_client_id(self, client_id, request, *args, **kwargs):
        return client_id == "titan-desktop" and super().authenticate_client_id(
            client_id, request, *args, **kwargs
        )

    def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):
        return client_id == "titan-desktop" and loopback(redirect_uri)

    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        return "openid" in scopes and set(scopes) <= {"openid", "profile", "email"}

    def save_authorization_code(self, client_id, code, request, *args, **kwargs):
        super().save_authorization_code(client_id, code, request, *args, **kwargs)
        GrantContext.objects.create(
            digest=digest(code["code"]),
            user=request.user,
            auth_time=request.user._titan_auth_time,
            epoch=settings.SESSION_EPOCH,
            credential=request.user.get_session_auth_hash(),
        )

    def validate_code(self, client_id, code, client, request, *args, **kwargs):
        context = (
            GrantContext.objects.select_related("user").filter(pk=digest(code)).first()
        )
        if not context or not context.user.is_active or not context.user.verified_at:
            return False
        if (
            context.epoch != settings.SESSION_EPOCH
            or context.credential != context.user.get_session_auth_hash()
        ):
            return False
        request.titan_context = context
        return super().validate_code(client_id, code, client, request, *args, **kwargs)

    def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
        binding = (
            TokenBinding.objects.select_related("session__user")
            .filter(pk=digest(refresh_token), kind="refresh")
            .first()
        )
        if not binding or not live(binding.session) or binding.consumed_at:
            return False
        request.titan_session = binding.session
        return super().validate_refresh_token(
            refresh_token, client, request, *args, **kwargs
        )

    def _save_bearer_token(self, token, request, *args, **kwargs):
        family = getattr(request, "titan_session", None)
        if family is None:
            context = request.titan_context
            family = DeviceSession.objects.create(
                user=request.user,
                auth_time=context.auth_time,
                expires_at=timezone.now() + timedelta(days=30),
                epoch=context.epoch,
                credential=context.credential,
            )
        else:
            TokenBinding.objects.filter(
                pk=digest(request.refresh_token), kind="refresh"
            ).update(consumed_at=timezone.now())
        super()._save_bearer_token(token, request, *args, **kwargs)
        for field, kind in [("access_token", "access"), ("refresh_token", "refresh")]:
            if field in token:
                TokenBinding.objects.create(
                    digest=digest(token[field]), session=family, kind=kind
                )
        token["session_id"] = str(family.pk)
        token["refresh_expires_in"] = max(
            0, int((family.expires_at - timezone.now()).total_seconds())
        )

    def validate_bearer_token(self, token, scopes, request):
        binding = (
            TokenBinding.objects.select_related("session__user")
            .filter(pk=digest(token or ""), kind="access")
            .first()
        )
        if not binding or not live(binding.session):
            return False
        valid = super().validate_bearer_token(token, scopes, request)
        if valid:
            request.titan_session = binding.session
        return valid

    def get_additional_claims(self, request):
        return {
            "name": request.user.name,
            "email": request.user.email,
            "email_verified": request.user.verified_at is not None,
        }

    def get_id_token_dictionary(self, token, token_handler, request):
        claims, expiration = super().get_id_token_dictionary(
            token, token_handler, request
        )
        context = getattr(request, "titan_session", None) or getattr(
            request, "titan_context", None
        )
        if context:
            claims["auth_time"] = int(context.auth_time.timestamp())
        return claims, expiration

    def revoke_token(self, token, token_type_hint, request, *args, **kwargs):
        binding = (
            TokenBinding.objects.select_related("session")
            .filter(pk=digest(token))
            .first()
        )
        if binding:
            with transaction.atomic():
                User.objects.select_for_update().get(pk=binding.session.user_id)
                session = DeviceSession.objects.select_for_update().get(
                    pk=binding.session_id
                )
                revoke(session)
        return super().revoke_token(token, token_type_hint, request, *args, **kwargs)


class NativeAuthorizationView(AuthorizationView):
    def dispatch(self, request, *args, **kwargs):
        params = request.GET if request.method == "GET" else request.POST
        if any(len(v) != 1 for _, v in params.lists()):
            return JsonResponse({"error": "invalid_request"}, status=400)
        if "max_age" in params:
            try:
                max_age = int(params["max_age"])
                if max_age < 0:
                    raise ValueError
            except ValueError:
                return JsonResponse({"error": "invalid_request"}, status=400)
            authenticated_at = request.session.get("auth_time", 0)
            if max_age == 0 or timezone.now().timestamp() - authenticated_at > max_age:
                from django.contrib.auth.views import redirect_to_login

                continuation = params.copy()
                continuation.pop("max_age", None)
                continuation.pop("prompt", None)
                return redirect_to_login(
                    "/o/authorize/?" + continuation.urlencode(), "/login"
                )
        if request.user.is_authenticated:
            if not request.user.verified_at:
                from .views import page

                request.session["pending_next"] = request.get_full_path()
                return page(
                    request,
                    "Verify email",
                    message="Verify your email before continuing. Use resend verification if needed.",
                    status=403,
                )
            auth_time = request.session.get("auth_time")
            if not isinstance(auth_time, int):
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path(), "/login")
            request.user._titan_auth_time = datetime.fromtimestamp(
                auth_time, dt_timezone.utc
            )
        with transaction.atomic():
            return super().dispatch(request, *args, **kwargs)


@method_decorator(csrf_exempt, name="dispatch")
class NativeTokenView(TokenView):
    def post(self, request, *args, **kwargs):
        if not rate_limit(request, "token", limit=120, seconds=60):
            return JsonResponse({"error": "temporarily_unavailable"}, status=429)
        if any(len(v) != 1 for _, v in request.POST.lists()):
            return JsonResponse({"error": "invalid_request"}, status=400)
        if request.POST.get("client_id") != "titan-desktop":
            return JsonResponse({"error": "invalid_client"}, status=401)
        grant = request.POST.get("grant_type")
        if grant == "authorization_code":
            context = GrantContext.objects.filter(
                pk=digest(request.POST.get("code", ""))
            ).first()
            if context is None:
                return JsonResponse({"error": "invalid_grant"}, status=400)
            with transaction.atomic():
                User.objects.select_for_update().get(pk=context.user_id)
                return super().post(request, *args, **kwargs)
        if grant == "refresh_token":
            binding = (
                TokenBinding.objects.select_related("session")
                .filter(
                    pk=digest(request.POST.get("refresh_token", "")), kind="refresh"
                )
                .first()
            )
            if binding is None:
                return JsonResponse({"error": "invalid_grant"}, status=400)
            with transaction.atomic():
                User.objects.select_for_update().get(pk=binding.session.user_id)
                session = (
                    DeviceSession.objects.select_for_update()
                    .select_related("user")
                    .get(pk=binding.session_id)
                )
                binding.refresh_from_db()
                if binding.consumed_at:
                    revoke(session)
                    return JsonResponse({"error": "invalid_grant"}, status=400)
                if not live(session):
                    return JsonResponse({"error": "invalid_grant"}, status=400)
                return super().post(request, *args, **kwargs)
        return JsonResponse({"error": "unsupported_grant_type"}, status=400)


class DiscoveryView(ConnectDiscoveryInfoView):
    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        data = json.loads(response.content)
        data["id_token_signing_alg_values_supported"] = ["RS256"]
        data["revocation_endpoint"] = settings.ISSUER + "/o/revoke_token/"
        # Public URL is controlled configuration, never a client-controlled Host header.
        for field, path in [
            ("authorization_endpoint", "authorize/"),
            ("token_endpoint", "token/"),
            ("userinfo_endpoint", "userinfo/"),
            ("jwks_uri", ".well-known/jwks.json"),
        ]:
            data[field] = settings.ISSUER + "/o/" + path
        return JsonResponse(data)
