"""Real CSRF middleware accepts account forms without trusting opaque origins."""

import pytest
from django.test import Client

from .test_endpoints import PASSWORD


@pytest.mark.parametrize("secure", [False, True])
@pytest.mark.parametrize("origin_kind,status", [("same", 302), ("null", 403), ("foreign", 403)])
def test_browser_login_checks_origin_with_valid_csrf_token(user, secure, origin_kind, status):
    client = Client(enforce_csrf_checks=True)
    client.get("/login", secure=secure)
    token = client.cookies["titan_accounts_csrf"].value
    scheme = "https" if secure else "http"
    origin = {
        "same": f"{scheme}://testserver",
        "null": "null",
        "foreign": f"{scheme}://testserver.attacker.example",
    }[origin_kind]
    response = client.post(
        "/login",
        {"email": user.email, "password": PASSWORD, "csrfmiddlewaretoken": token},
        secure=secure,
        HTTP_ORIGIN=origin,
    )
    assert response.status_code == status
    assert client.session.get("_auth_user_id") == (str(user.pk) if status == 302 else None)


@pytest.mark.parametrize("referer,status", [("https://testserver/login", 302), (None, 403)])
def test_https_login_preserves_strict_referer_fallback_without_origin(user, referer, status):
    client = Client(enforce_csrf_checks=True)
    client.get("/login", secure=True)
    token = client.cookies["titan_accounts_csrf"].value
    headers = {"HTTP_REFERER": referer} if referer is not None else {}
    response = client.post(
        "/login",
        {"email": user.email, "password": PASSWORD, "csrfmiddlewaretoken": token},
        secure=True,
        **headers,
    )
    assert response.status_code == status
    assert client.session.get("_auth_user_id") == (str(user.pk) if status == 302 else None)
