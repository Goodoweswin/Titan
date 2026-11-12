import re
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from .test_endpoints import PASSWORD, headers, mint, refresh


@pytest.mark.django_db
def test_registration_normalizes_and_hides_duplicate(client):
    data = {
        "email": "  Mixed+tag@Example.ORG  ",
        "name": " Researcher ",
        "password": PASSWORD,
    }
    first = client.post("/register", data)
    assert first.status_code == 200
    duplicate = client.post("/register", {**data, "email": "mixed+TAG@example.org"})
    assert duplicate.status_code == 200
    assert first.content == duplicate.content
    registered = get_user_model().objects.get(email="mixed+tag@example.org")
    assert registered.name == "Researcher"
    assert registered.check_password(PASSWORD)
    assert registered.verified_at is None
    assert get_user_model().objects.count() == 1


@pytest.mark.django_db
def test_invalid_password_and_nickname_rejected(client):
    for data in [
        {"email": "ok@example.org", "name": "Name", "password": "short"},
        {"email": "ok@example.org", "name": "Bad\nName", "password": PASSWORD},
    ]:
        assert client.post("/register", data).status_code == 400
    assert get_user_model().objects.count() == 0


@pytest.mark.django_db
def test_browser_login_wrong_password_and_precise_csrf(client, user):
    response = client.post("/login", {"email": user.email, "password": "wrong"})
    assert response.status_code == 400
    secure = Client(enforce_csrf_checks=True)
    secure.get("/login")
    csrf = secure.cookies["titan_accounts_csrf"].value
    assert (
        secure.post("/login", {"email": user.email, "password": PASSWORD}).status_code
        == 403
    )
    assert (
        secure.post(
            "/login",
            {"email": user.email, "password": PASSWORD, "csrfmiddlewaretoken": csrf},
            HTTP_ORIGIN="http://testserver.evil.test",
        ).status_code
        == 403
    )
    assert (
        secure.post(
            "/login",
            {"email": user.email, "password": PASSWORD, "csrfmiddlewaretoken": csrf},
            HTTP_ORIGIN="http://testserver",
        ).status_code
        == 302
    )


@pytest.mark.django_db
def test_verify_once_and_expire(client):
    from accounts.models import MailOutbox, OneTimeToken

    client.post(
        "/register",
        {"email": "verify@example.org", "name": "Name", "password": PASSWORD},
    )
    url = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    assert client.get(url).status_code == 200
    assert get_user_model().objects.get(email="verify@example.org").verified_at is None
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 400
    assert get_user_model().objects.get(email="verify@example.org").verified_at
    client.post(
        "/register",
        {"email": "expired@example.org", "name": "Name", "password": PASSWORD},
    )
    url = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    OneTimeToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert client.post(url).status_code == 400


@pytest.mark.django_db
def test_reset_invalidates_access_refresh_browser_and_other_reset_links(
    client, user, application
):
    from accounts.models import MailOutbox

    tokens, _ = mint(client, user, application)
    client.post("/recover", {"email": user.email})
    old = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    client.post("/recover", {"email": user.email})
    url = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    assert (
        client.post(url, {"password": "Another-Strong-Password-42!"}).status_code == 200
    )
    assert client.post(url, {"password": PASSWORD}).status_code == 400
    assert client.post(old, {"password": PASSWORD}).status_code == 400
    assert client.get("/api/v1/me", **headers(tokens)).status_code == 401
    assert refresh(client, tokens["refresh_token"]).status_code == 400
    user.refresh_from_db()
    assert user.check_password("Another-Strong-Password-42!")


@pytest.mark.django_db
def test_recent_auth_absolute_expiry_and_restore_epoch(
    client, user, application, settings
):
    from accounts.models import DeviceSession

    tokens, _ = mint(client, user, application)
    family = DeviceSession.objects.get(pk=tokens["session_id"])
    assert 2591990 <= tokens["refresh_expires_in"] <= 2592000
    family.auth_time = timezone.now() - timedelta(minutes=6)
    family.save()
    assert (
        client.post("/api/v1/sessions/revoke-all", **headers(tokens)).status_code == 403
    )
    family.expires_at = timezone.now() - timedelta(seconds=1)
    family.save()
    assert refresh(client, tokens["refresh_token"]).status_code == 400
    tokens, _ = mint(client, user, application)
    settings.SESSION_EPOCH = "restored-database-new-epoch"
    assert client.get("/api/v1/me", **headers(tokens)).status_code == 401
    assert refresh(client, tokens["refresh_token"]).status_code == 400


@pytest.mark.django_db
def test_hashed_token_storage_and_signed_id_token(client, user, application):
    import json

    from jwcrypto import jwk, jwt
    from oauth2_provider.models import AccessToken, RefreshToken

    tokens, _ = mint(client, user, application)
    assert AccessToken.objects.get().token == ""
    assert RefreshToken.objects.get().token == ""
    keys = client.get("/o/.well-known/jwks.json").json()
    key = jwk.JWK(**keys["keys"][0])
    verified = jwt.JWT(key=key, jwt=tokens["id_token"], algs=["RS256"])
    claims = json.loads(verified.claims)
    assert claims["iss"] == "http://testserver"
    assert claims["aud"] == "titan-desktop"
    assert claims["nonce"] == "nonce-value"
    assert claims["sub"] == str(user.pk)
    assert claims["email"] == "alice@example.org"


@pytest.mark.django_db
def test_registration_verification_continues_authorization(client, application):
    import base64
    import hashlib
    from urllib.parse import parse_qs, urlencode, urlparse

    from accounts.models import MailOutbox

    from .test_endpoints import CALLBACK, VERIFIER

    target = "/o/authorize/?" + urlencode(
        {
            "client_id": "titan-desktop",
            "response_type": "code",
            "redirect_uri": CALLBACK,
            "scope": "openid profile email",
            "state": "continue-state",
            "nonce": "continue-nonce",
            "code_challenge": base64.urlsafe_b64encode(
                hashlib.sha256(VERIFIER.encode()).digest()
            )
            .decode()
            .rstrip("="),
            "code_challenge_method": "S256",
        }
    )
    client.post(
        "/register",
        {
            "email": "new@example.org",
            "name": "New",
            "password": PASSWORD,
            "next": target,
        },
    )
    url = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    assert client.post(url).status_code == 200
    response = client.post("/login", {"email": "new@example.org", "password": PASSWORD})
    assert response["Location"] == target
    authorized = client.get(response["Location"])
    assert parse_qs(urlparse(authorized["Location"]).query)["state"] == [
        "continue-state"
    ]


@pytest.mark.django_db
def test_recovery_continuation_and_external_next_rejected(client, user, application):
    from accounts.models import MailOutbox

    target = "/o/authorize/?client_id=titan-desktop"
    client.get("/recover", {"next": target})
    client.post("/recover", {"email": user.email, "next": target})
    url = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    client.post(url, {"password": "New-Strong-Password-42!"})
    response = client.post(
        "/login", {"email": user.email, "password": "New-Strong-Password-42!"}
    )
    assert response["Location"] == target
    response = client.post(
        "/login",
        {
            "email": user.email,
            "password": "New-Strong-Password-42!",
            "next": "https://evil.test",
        },
    )
    assert response["Location"] == "/complete"


@pytest.mark.django_db
def test_durable_account_and_source_throttling(client, user):
    from django.test import Client

    for _ in range(10):
        assert (
            client.post(
                "/login", {"email": user.email, "password": "wrong"}
            ).status_code
            == 400
        )
    assert (
        Client()
        .post("/login", {"email": "different@example.org", "password": "wrong"})
        .status_code
        == 429
    )
    assert (
        Client()
        .post(
            "/login",
            {"email": user.email, "password": PASSWORD},
            REMOTE_ADDR="192.0.2.20",
        )
        .status_code
        == 429
    )


@pytest.mark.django_db
def test_resend_does_not_revive_consumed_verification(client):
    from accounts.models import MailOutbox

    client.post(
        "/register",
        {"email": "repeat@example.org", "name": "Repeat", "password": PASSWORD},
    )
    old = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    client.post("/resend", {"email": "repeat@example.org"})
    latest = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    assert old != latest
    assert client.post(old).status_code == 200
    assert client.post(latest).status_code == 400
    assert client.post(old).status_code == 400


@pytest.mark.django_db
def test_password_change_and_restart_invalidation(client, user, application, settings):
    tokens, _ = mint(client, user, application)
    # A normal worker restart has no special state to reconstruct: a new client works.
    assert Client().get("/api/v1/me", **headers(tokens)).status_code == 200
    user.set_password("Out-of-band-Strong-Password-42!")
    user.save()
    assert Client().get("/api/v1/me", **headers(tokens)).status_code == 401
    assert refresh(client, tokens["refresh_token"]).status_code == 400
