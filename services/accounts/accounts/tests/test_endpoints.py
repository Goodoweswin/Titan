import base64
import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from oauth2_provider.models import Application


def test_discovery_exposes_native_pkce_endpoints(client):
    response = client.get("/.well-known/openid-configuration")
    assert response.status_code == 200
    body = response.json()
    assert body["issuer"] == "http://testserver"
    assert body["code_challenge_methods_supported"] == ["S256"]
    assert body["id_token_signing_alg_values_supported"] == ["RS256"]


def test_anonymous_profile_is_structured_unauthorized(client):
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
    assert response.json()["request_id"]


PASSWORD = "Strong-Example-Password-42!"
VERIFIER = "a" * 64
CALLBACK = "http://127.0.0.1:47991/oauth/callback"


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="alice",
        email="alice@example.org",
        name="Alice",
        password=PASSWORD,
        verified_at=timezone.now(),
    )


@pytest.fixture
def application(db):
    return Application.objects.create(
        name="Titan",
        client_id="titan-desktop",
        client_type="public",
        authorization_grant_type="authorization-code",
        redirect_uris="http://127.0.0.1/oauth/callback",
        algorithm="RS256",
        skip_authorization=True,
    )


def authorize(client, user, application, **extra):
    client.force_login(user)
    session = client.session
    session["auth_time"] = int(timezone.now().timestamp())
    session["epoch"] = "test-epoch"
    session.save()
    params = {
        "client_id": "titan-desktop",
        "response_type": "code",
        "redirect_uri": CALLBACK,
        "scope": "openid profile email",
        "state": "some-state",
        "nonce": "nonce-value",
        "code_challenge": base64.urlsafe_b64encode(
            hashlib.sha256(VERIFIER.encode()).digest()
        )
        .decode()
        .rstrip("="),
        "code_challenge_method": "S256",
    }
    params.update(extra)
    return client.get("/o/authorize/?" + urlencode(params))


def mint(client, user, application):
    response = authorize(client, user, application)
    assert response.status_code == 302, response.content
    code = parse_qs(urlparse(response["Location"]).query)["code"][0]
    data = {
        "grant_type": "authorization_code",
        "client_id": "titan-desktop",
        "code": code,
        "redirect_uri": CALLBACK,
        "code_verifier": VERIFIER,
    }
    result = client.post("/o/token/", data)
    assert result.status_code == 200, result.content
    return result.json(), data


def headers(tokens):
    return {"HTTP_AUTHORIZATION": "Bearer " + tokens["access_token"]}


def refresh(client, token):
    return client.post(
        "/o/token/",
        {
            "grant_type": "refresh_token",
            "client_id": "titan-desktop",
            "refresh_token": token,
        },
    )


@pytest.mark.django_db
def test_code_pkce_profile_and_replay(client, user, application):
    tokens, data = mint(client, user, application)
    assert tokens["expires_in"] == 600
    assert tokens["id_token"]
    result = client.get("/api/v1/me", **headers(tokens))
    assert result.status_code == 200
    assert result.json()["emailVerified"] is True
    assert result.json()["name"] == "Alice"
    assert result.json()["sessionId"]
    assert client.post("/o/token/", data).status_code == 400


@pytest.mark.django_db
def test_wrong_pkce_does_not_mint(client, user, application):
    response = authorize(client, user, application)
    code = parse_qs(urlparse(response["Location"]).query)["code"][0]
    response = client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "client_id": "titan-desktop",
            "code": code,
            "redirect_uri": CALLBACK,
            "code_verifier": "b" * 64,
        },
    )
    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize(
    "redirect",
    [
        "http://localhost:47991/oauth/callback",
        "http://127.0.0.1:47991/wrong",
        "http://127.0.0.1.evil.test:47991/oauth/callback",
        "http://127.0.0.1:47991/oauth/callback?extra=1",
        "http://user@127.0.0.1:47991/oauth/callback",
    ],
)
def test_exact_loopback_redirect(client, user, application, redirect):
    response = authorize(client, user, application, redirect_uri=redirect)
    assert response.status_code == 400
    assert "Location" not in response


@pytest.mark.django_db
def test_unverified_cannot_authorize(client, user, application):
    user.verified_at = None
    user.save()
    response = authorize(client, user, application)
    assert response.status_code == 403


@pytest.mark.django_db
def test_rotation_replay_revokes_descendant_access(client, user, application):
    tokens, _ = mint(client, user, application)
    rotated = refresh(client, tokens["refresh_token"])
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != tokens["refresh_token"]
    assert refresh(client, tokens["refresh_token"]).status_code == 400
    assert client.get("/api/v1/me", **headers(rotated.json())).status_code == 401
    assert refresh(client, rotated.json()["refresh_token"]).status_code == 400


@pytest.mark.django_db
def test_disabled_user_cannot_use_access_or_refresh(client, user, application):
    tokens, _ = mint(client, user, application)
    user.is_active = False
    user.save()
    assert client.get("/api/v1/me", **headers(tokens)).status_code == 401
    assert refresh(client, tokens["refresh_token"]).status_code == 400


@pytest.mark.django_db
def test_profile_validation_and_session_ownership(client, user, application):
    tokens, _ = mint(client, user, application)
    assert (
        client.patch(
            "/api/v1/me",
            {"name": "New Name"},
            content_type="application/json",
            **headers(tokens),
        ).json()["name"]
        == "New Name"
    )
    for data in [
        {"name": ""},
        {"name": "a" * 61},
        {"name": "bad\nname"},
        {"email": "evil@example.org"},
        {"name": 12},
    ]:
        assert (
            client.patch(
                "/api/v1/me", data, content_type="application/json", **headers(tokens)
            ).status_code
            == 400
        )
    sessions = client.get("/api/v1/sessions", **headers(tokens)).json()["sessions"]
    assert len(sessions) == 1 and sessions[0]["current"]
    other = get_user_model().objects.create_user(
        username="bob",
        email="bob@example.org",
        name="Bob",
        password=PASSWORD,
        verified_at=timezone.now(),
    )
    other_tokens, _ = mint(client, other, application)
    assert (
        client.delete(
            "/api/v1/sessions/" + sessions[0]["id"], **headers(other_tokens)
        ).status_code
        == 404
    )
    assert client.get("/api/v1/me", **headers(tokens)).status_code == 200
    assert (
        client.delete(
            "/api/v1/sessions/" + sessions[0]["id"], **headers(tokens)
        ).status_code
        == 204
    )
    assert client.get("/api/v1/me", **headers(tokens)).status_code == 401


@pytest.mark.django_db
def test_code_redemption_requires_identical_port(client, user, application):
    response = authorize(client, user, application)
    code = parse_qs(urlparse(response["Location"]).query)["code"][0]
    response = client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "client_id": "titan-desktop",
            "code": code,
            "redirect_uri": "http://127.0.0.1:47992/oauth/callback",
            "code_verifier": VERIFIER,
        },
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_userinfo_revocation_and_revoke_all(client, user, application):
    tokens, _ = mint(client, user, application)
    assert client.get("/o/userinfo/", **headers(tokens)).json()["sub"] == str(user.pk)
    assert (
        client.post("/api/v1/sessions/revoke-all", **headers(tokens)).status_code == 204
    )
    assert client.get("/o/userinfo/", **headers(tokens)).status_code == 401
    tokens, _ = mint(client, user, application)
    assert (
        client.post(
            "/o/revoke_token/",
            {"token": tokens["refresh_token"], "client_id": "titan-desktop"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/me", **headers(tokens)).status_code == 401


@pytest.mark.django_db
def test_refresh_keeps_absolute_deadline(client, user, application):
    from accounts.models import DeviceSession

    tokens, _ = mint(client, user, application)
    family = DeviceSession.objects.get(pk=tokens["session_id"])
    family.expires_at = timezone.now() + timedelta(seconds=1000)
    family.save()
    new = refresh(client, tokens["refresh_token"]).json()
    assert 990 <= new["refresh_expires_in"] <= 1000
    assert new["session_id"] == tokens["session_id"]


@pytest.mark.django_db
def test_prompt_login_and_max_age_zero_require_password(client, user, application):
    for extra in [{"prompt": "login"}, {"max_age": "0"}]:
        response = authorize(client, user, application, **extra)
        assert response.status_code == 302
        assert urlparse(response["Location"]).path == "/login"
        destination = parse_qs(urlparse(response["Location"]).query)["next"][0]
        logged = client.post(
            "/login", {"email": user.email, "password": PASSWORD, "next": destination}
        )
        assert logged.status_code == 302
        done = client.get(logged["Location"])
        assert done.status_code == 302
        assert urlparse(done["Location"]).hostname == "127.0.0.1"


@pytest.mark.django_db
def test_pkce_plain_duplicates_and_unregistered_client_rejected(
    client, user, application
):
    response = authorize(client, user, application, code_challenge_method="plain")
    assert "code=" not in response.get("Location", "")
    response = authorize(client, user, application, client_id="unregistered")
    assert response.status_code == 400
    response = client.post(
        "/o/token/",
        "client_id=titan-desktop&grant_type=refresh_token&refresh_token=a&refresh_token=b",
        content_type="application/x-www-form-urlencoded",
    )
    assert response.status_code == 400
