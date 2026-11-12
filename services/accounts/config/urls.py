from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from oauth2_provider import views

from accounts.api import delete_session, me, revoke_all, sessions
from accounts.oauth import DiscoveryView, NativeAuthorizationView, NativeTokenView

oauth_patterns = [
    path("authorize/", NativeAuthorizationView.as_view(), name="authorize"),
    path("token/", NativeTokenView.as_view(), name="token"),
    path("revoke_token/", views.RevokeTokenView.as_view(), name="revoke-token"),
    path(".well-known/jwks.json", views.JwksInfoView.as_view(), name="jwks-info"),
    path("userinfo/", views.UserInfoView.as_view(), name="user-info"),
]
urlpatterns = [
    path(".well-known/openid-configuration", DiscoveryView.as_view()),
    path(
        "o/", include((oauth_patterns, "oauth2_provider"), namespace="oauth2_provider")
    ),
    path("api/v1/me", me),
    path("api/v1/sessions", sessions),
    path("api/v1/sessions/revoke-all", revoke_all),
    path("api/v1/sessions/<uuid:session_id>", delete_session),
]
urlpatterns += [path("", include("accounts.urls"))]


if settings.ADMIN_ENABLED:
    urlpatterns += [path("admin/", admin.site.urls)]
