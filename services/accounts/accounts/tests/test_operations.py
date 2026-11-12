from datetime import timedelta
from io import StringIO

import pytest
from django.contrib import admin
from django.core.management import CommandError, call_command
from django.db import OperationalError
from django.test import RequestFactory
from django.utils import timezone

from .test_endpoints import headers, mint, refresh


@pytest.mark.django_db
def test_bootstrap_is_idempotent_and_has_no_secret_output():
    from oauth2_provider.models import Application

    stream = StringIO()
    call_command("bootstrap_accounts", stdout=stream)
    call_command("bootstrap_accounts", stdout=stream)
    client = Application.objects.get(client_id="titan-desktop")
    assert client.client_type == "public"
    assert client.algorithm == "RS256"
    assert client.redirect_uris == "http://127.0.0.1/oauth/callback"
    assert Application.objects.count() == 1
    assert client.client_secret not in stream.getvalue()


@pytest.mark.django_db
def test_admin_disable_then_reenable_does_not_resurrect_tokens(
    client, user, application
):
    from accounts.admin import AccountAdmin
    from accounts.models import User

    tokens, _ = mint(client, user, application)
    model_admin = AccountAdmin(User, admin.site)
    request = RequestFactory().post("/admin/")
    from .test_admin_concurrency import edit_form

    disable = edit_form(user, is_active=False)
    model_admin.save_model(request, user, disable, True)
    enable = edit_form(user, is_active=True)
    model_admin.save_model(request, user, enable, True)
    assert client.get("/api/v1/me", **headers(tokens)).status_code == 401
    assert refresh(client, tokens["refresh_token"]).status_code == 400


@pytest.mark.django_db
def test_outbox_bounds_and_erases_delivered_bodies(client, user, mailoutbox):
    from accounts.mail import dispatch_batch
    from accounts.models import MailOutbox

    for _ in range(3):
        client.post("/recover", {"email": user.email})
    assert dispatch_batch(2) == 2
    assert len(mailoutbox) == 2
    assert MailOutbox.objects.filter(sent_at__isnull=False, body="").count() == 2
    assert MailOutbox.objects.filter(sent_at__isnull=True).count() == 1
    with pytest.raises(ValueError):
        dispatch_batch(51)


@pytest.mark.django_db
def test_mail_failure_has_bounded_retry_without_logging_link(
    client, user, monkeypatch, caplog
):
    from django.core.mail.backends.locmem import EmailBackend

    from accounts.mail import dispatch_batch
    from accounts.models import MailOutbox

    client.post("/recover", {"email": user.email})

    def broken(*args, **kwargs):
        raise OSError("sensitive-provider-detail")

    monkeypatch.setattr(EmailBackend, "send_messages", broken)
    assert dispatch_batch(10) == 0
    row = MailOutbox.objects.get()
    assert row.attempts == 1 and row.available_at > timezone.now()
    for _ in range(6):
        MailOutbox.objects.update(available_at=timezone.now() - timedelta(seconds=1))
        dispatch_batch(10)
    row.refresh_from_db()
    assert row.attempts == 5
    assert "sensitive-provider-detail" not in caplog.text


@pytest.mark.django_db
def test_dev_mail_retrieval_requires_debug_and_writes_private_file(
    client, user, settings, tmp_path
):
    from accounts.models import MailOutbox

    client.post("/recover", {"email": user.email})
    row = MailOutbox.objects.get()
    stream = StringIO()
    output = tmp_path / "mail.eml"
    settings.DEBUG = True
    call_command("dev_mail", str(row.pk), output=str(output), stdout=stream)
    assert row.body in output.read_text()
    assert output.stat().st_mode & 0o777 == 0o600
    assert row.body not in stream.getvalue()
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("dev_mail", str(row.pk), output=str(tmp_path / "forbidden"))


@pytest.mark.django_db
def test_database_uncertainty_returns_closed_structured_503(
    client, user, application, monkeypatch
):
    from accounts.models import TokenBinding

    tokens, _ = mint(client, user, application)

    def unavailable(*args, **kwargs):
        raise OperationalError("database unavailable")

    monkeypatch.setattr(TokenBinding.objects, "select_related", unavailable)
    response = client.get("/api/v1/me", **headers(tokens))
    assert response.status_code == 503
    assert response.json()["code"] == "unavailable"


@pytest.mark.django_db
def test_dispatch_command_refuses_unconfigured_delivery():
    with pytest.raises(CommandError):
        call_command("dispatch_mail")


@pytest.mark.django_db
def test_cleanup_retains_active_family_replay_tombstone(client, user, application):
    from oauth2_provider.models import RefreshToken

    tokens, _ = mint(client, user, application)
    current = refresh(client, tokens["refresh_token"]).json()
    RefreshToken.objects.filter(revoked__isnull=False).delete()
    call_command("cleanup_accounts", stdout=StringIO())
    assert refresh(client, tokens["refresh_token"]).status_code == 400
    assert client.get("/api/v1/me", **headers(current)).status_code == 401


@pytest.mark.django_db
def test_expired_mail_body_is_removed_without_sending(client, user, mailoutbox):
    from accounts.mail import dispatch_batch
    from accounts.models import MailOutbox

    client.post("/recover", {"email": user.email})
    MailOutbox.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert dispatch_batch() == 0
    assert len(mailoutbox) == 0
    assert MailOutbox.objects.get().body == ""


@pytest.mark.django_db
def test_epoch_change_invalidates_existing_browser_and_code(
    client, user, application, settings
):
    from urllib.parse import parse_qs, urlparse

    from .test_endpoints import CALLBACK, VERIFIER, authorize

    response = authorize(client, user, application)
    code = parse_qs(urlparse(response["Location"]).query)["code"][0]
    settings.SESSION_EPOCH = "new-restore-epoch"
    response = client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "client_id": "titan-desktop",
            "code": code,
            "redirect_uri": CALLBACK,
            "code_verifier": VERIFIER,
        },
    )
    assert response.status_code == 400
    response = client.get(
        "/o/authorize/",
        {
            "client_id": "titan-desktop",
            "response_type": "code",
            "redirect_uri": CALLBACK,
            "scope": "openid",
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
        },
    )
    assert response.status_code == 302
    assert urlparse(response["Location"]).path == "/login"


@pytest.mark.django_db
def test_disable_reenable_cannot_revive_browser_or_unredeemed_code(
    client, user, application
):
    from urllib.parse import parse_qs, urlparse

    from accounts.admin import AccountAdmin
    from accounts.models import User

    from .test_endpoints import CALLBACK, VERIFIER, authorize

    response = authorize(client, user, application)
    code = parse_qs(urlparse(response["Location"]).query)["code"][0]
    model_admin = AccountAdmin(User, admin.site)
    request = RequestFactory().post("/admin/")
    from .test_admin_concurrency import edit_form

    disable = edit_form(user, is_active=False)
    model_admin.save_model(request, user, disable, True)
    enable = edit_form(user, is_active=True)
    model_admin.save_model(request, user, enable, True)
    response = client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "client_id": "titan-desktop",
            "code": code,
            "redirect_uri": CALLBACK,
            "code_verifier": VERIFIER,
        },
    )
    assert response.status_code == 400
    response = client.get(
        "/o/authorize/",
        {
            "client_id": "titan-desktop",
            "response_type": "code",
            "redirect_uri": CALLBACK,
            "scope": "openid",
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
        },
    )
    assert response.status_code == 302
    assert urlparse(response["Location"]).path == "/login"
