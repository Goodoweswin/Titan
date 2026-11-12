"""Managed trust is explicit; mail verification and approval never conflate."""
import io
import re
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib import admin
from django.core.management import call_command, get_commands
from django.core.management.base import CommandError
from django.test import Client, RequestFactory, override_settings

from accounts.admin import AccountAdmin
from accounts.mail import enqueue_link
from accounts.models import DeviceSession, MailOutbox, OneTimeToken, User
from .test_admin_concurrency import edit_form, save_admin
from .test_deployment import REQUIRED, load_settings
from .test_endpoints import CALLBACK, PASSWORD, VERIFIER, authorize, headers, mint, refresh


def approve(user, verified=False):
    user.admin_provisioned = True
    if not verified:
        user.verified_at = None
    user.save()
    return user


def code_request(client, user, application):
    response = authorize(client, user, application)
    assert response.status_code == 302
    return {
        "grant_type": "authorization_code", "client_id": "titan-desktop",
        "code": parse_qs(urlparse(response["Location"]).query)["code"][0],
        "redirect_uri": CALLBACK, "code_verifier": VERIFIER,
    }


def assert_invalidated(client, tokens, pending):
    assert client.get("/api/v1/me", **headers(tokens)).status_code == 401
    assert client.get("/o/userinfo/", **headers(tokens)).status_code == 401
    assert refresh(client, tokens["refresh_token"]).status_code == 400
    assert client.post("/o/token/", pending).status_code == 400
    assert client.session.get("_auth_user_id") is None


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_managed_unverified_account_can_complete_protocol_and_logout(client, user, application):
    approve(user)
    assert client.post("/login", {"email": user.email, "password": PASSWORD}).status_code == 302
    tokens, _ = mint(client, user, application)
    profile = client.get("/api/v1/me", **headers(tokens)).json()
    assert profile["administratorApproved"] is True
    assert profile["emailVerified"] is False
    assert client.get("/o/userinfo/", **headers(tokens)).json()["email_verified"] is False
    sessions = client.get("/api/v1/sessions", **headers(tokens)).json()["sessions"]
    assert len(sessions) == 1 and sessions[0]["current"]
    rotated = refresh(client, tokens["refresh_token"])
    assert rotated.status_code == 200
    assert rotated.json()["session_id"] == tokens["session_id"]
    assert client.delete("/api/v1/sessions/" + tokens["session_id"], **headers(rotated.json())).status_code == 204
    assert client.get("/api/v1/me", **headers(rotated.json())).status_code == 401
    tokens, _ = mint(client, user, application)
    assert client.post("/api/v1/sessions/revoke-all", **headers(tokens)).status_code == 204
    assert refresh(client, tokens["refresh_token"]).status_code == 400
    assert client.post("/logout").status_code == 302
    assert client.session.get("_auth_user_id") is None


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_verified_but_unapproved_account_cannot_authorize_or_login(client, user, application):
    assert authorize(client, user, application).status_code == 403
    client.logout()
    assert client.post("/login", {"email": user.email, "password": PASSWORD}).status_code == 400
    assert client.session.get("_auth_user_id") is None


@pytest.mark.django_db
def test_default_self_service_still_requires_verification_and_never_claims_approval(client, user, application):
    assert getattr(user, "admin_provisioned", False) is False
    approve(user, verified=True)
    tokens, _ = mint(client, user, application)
    assert client.get("/api/v1/me", **headers(tokens)).json()["administratorApproved"] is False
    user.verified_at = None
    user.save(update_fields=["verified_at"])
    assert authorize(client, user, application).status_code == 403
    assert client.get("/api/v1/me", **headers(tokens)).status_code == 401
    assert refresh(client, tokens["refresh_token"]).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("before,after", [("self_service", "managed"), ("managed", "self_service")])
def test_deployment_mode_transition_with_new_epoch_invalidates_all_credentials(client, user, application, before, after):
    approve(user, verified=True)
    with override_settings(ACCOUNT_MODE=before):
        tokens, _ = mint(client, user, application)
        pending = code_request(client, user, application)
    with override_settings(ACCOUNT_MODE=after, SESSION_EPOCH="next-deployment-epoch"):
        assert_invalidated(client, tokens, pending)


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
@pytest.mark.parametrize("mutation", ["approval", "disabled"])
def test_revocation_then_reapproval_cannot_revive_any_credentials(client, user, application, mutation):
    approve(user)
    tokens, _ = mint(client, user, application)
    pending = code_request(client, user, application)
    field = "admin_provisioned" if mutation == "approval" else "is_active"
    version = user.auth_version
    setattr(user, field, False)
    user.save(update_fields=[field])
    assert user.auth_version != version
    version = user.auth_version
    setattr(user, field, True)
    user.save(update_fields=[field])
    if mutation == "approval":
        assert user.auth_version != version
    assert_invalidated(client, tokens, pending)


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_stale_admin_name_form_preserves_approval_revocation(user):
    approve(user)
    stale = edit_form(User.objects.get(pk=user.pk), name="New nickname")
    user.admin_provisioned = False
    user.save()
    version = user.auth_version
    save_admin(stale)
    user.refresh_from_db()
    assert user.admin_provisioned is False
    assert user.auth_version == version
    assert user.name == "New nickname"
    assert "admin_provisioned" in AccountAdmin(User, admin.site).get_readonly_fields(RequestFactory().get("/admin"), user)


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_profile_cannot_grant_or_change_administrator_approval(client, user, application):
    approve(user)
    tokens, _ = mint(client, user, application)
    for field in ["administratorApproved", "admin_provisioned", "emailVerified"]:
        assert client.patch("/api/v1/me", {field: True}, content_type="application/json", **headers(tokens)).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
def test_managed_disables_every_email_route_without_side_effects(client, user, method):
    user.verified_at = None
    user.save()
    links = []
    for purpose in ["verify", "reset"]:
        enqueue_link(user, purpose)
        links.append(re.search(r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body).group())
    before = (User.objects.count(), OneTimeToken.objects.count(), MailOutbox.objects.count(), user.password)
    with override_settings(ACCOUNT_MODE="managed"):
        for route in ["/register", "/recover", "/resend", *links]:
            response = getattr(client, method)(route, {"email": "new@example.org", "name": "New", "password": PASSWORD})
            assert response.status_code == 403
            assert "管理员" in response.content.decode()
        page = client.get("/login")
        assert "账号由管理员开通" in page.content.decode()
        for path in ["/register", "/recover", "/resend"]:
            assert f'href="{path}' not in page.content.decode()
    user.refresh_from_db()
    assert (User.objects.count(), OneTimeToken.objects.count(), MailOutbox.objects.count(), user.password) == before
    assert user.verified_at is None
    assert not OneTimeToken.objects.filter(consumed_at__isnull=False).exists()


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
@pytest.mark.parametrize("origin,status", [("http://testserver", 302), ("null", 403), ("http://evil.invalid", 403)])
def test_managed_login_keeps_csrf_and_referrer_policy(user, origin, status):
    approve(user)
    client = Client(enforce_csrf_checks=True)
    page = client.get("/login")
    assert page["Referrer-Policy"] == "same-origin"
    response = client.post("/login", {"email": user.email, "password": PASSWORD, "csrfmiddlewaretoken": client.cookies["titan_accounts_csrf"].value}, HTTP_ORIGIN=origin)
    assert response.status_code == status


def run_private_command(monkeypatch, command, password=PASSWORD, **options):
    assert command in get_commands(), f"Missing private administrator command: {command}"
    monkeypatch.setattr("sys.stdin", io.StringIO(password + "\n"))
    output = io.StringIO()
    call_command(command, password_stdin=True, stdout=output, stderr=output, **options)
    assert password not in output.getvalue()
    return output.getvalue()


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_provision_normalizes_email_and_never_fakes_verification(monkeypatch):
    run_private_command(monkeypatch, "provision_account", email="  Mixed@Example.ORG  ", name="  Person  ")
    user = User.objects.get(email="mixed@example.org")
    assert user.name == "Person"
    assert user.admin_provisioned is True
    assert user.verified_at is None
    assert user.is_active and not user.is_staff and not user.is_superuser
    assert user.check_password(PASSWORD)
    assert not MailOutbox.objects.exists()
    with pytest.raises(CommandError):
        run_private_command(monkeypatch, "provision_account", email="MIXED@example.org", name="Replacement")
    user.refresh_from_db()
    assert user.name == "Person" and User.objects.count() == 1


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
@pytest.mark.parametrize("email,name,password", [
    ("new@example.org", "New", "weak"),
    ("longpersonname@example.org", "longpersonname", "longpersonname"),
    ("bad-email", "New", PASSWORD),
    ("new@example.org", "bad\nname", PASSWORD),
    ("new@example.org", "New", "x" * 1025),
])
def test_provision_rejects_invalid_identity_and_password(monkeypatch, email, name, password):
    with pytest.raises(CommandError):
        run_private_command(monkeypatch, "provision_account", email=email, name=name, password=password)
    assert not User.objects.exists()


@pytest.mark.django_db
def test_provision_is_managed_only(monkeypatch):
    with pytest.raises(CommandError):
        run_private_command(monkeypatch, "provision_account", email="new@example.org", name="New")
    assert not User.objects.exists()


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
@pytest.mark.parametrize("command", ["provision_account", "set_account_password"])
def test_password_argument_is_not_supported(command):
    assert command in get_commands()
    with pytest.raises(CommandError):
        call_command(command, "--email", "new@example.org", "--password", PASSWORD)


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
@pytest.mark.parametrize("matching", [True, False])
def test_hidden_terminal_input_requires_confirmation(monkeypatch, matching):
    assert "provision_account" in get_commands()
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    passwords = iter([PASSWORD, PASSWORD if matching else "Mismatched-Password-42!"])
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(passwords))
    output = io.StringIO()
    if matching:
        call_command("provision_account", email="new@example.org", name="New", stdout=output, stderr=output)
        assert User.objects.get().check_password(PASSWORD)
    else:
        with pytest.raises(CommandError):
            call_command("provision_account", email="new@example.org", name="New", stdout=output, stderr=output)
        assert not User.objects.exists()
    assert PASSWORD not in output.getvalue()


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_no_implicit_pipe_or_hidden_input_fallback(monkeypatch):
    assert "provision_account" in get_commands()
    monkeypatch.setattr("sys.stdin", io.StringIO(PASSWORD + "\n"))
    with pytest.raises(CommandError):
        call_command("provision_account", email="new@example.org", name="New")
    assert not User.objects.exists()


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_password_reset_preserves_approval_and_invalidates_every_credential(monkeypatch, client, user, application):
    approve(user)
    tokens, _ = mint(client, user, application)
    pending = code_request(client, user, application)
    stale = edit_form(User.objects.get(pk=user.pk), name="Name after reset")
    new_password = "Current-Admin-Reset-Value-42!"
    run_private_command(monkeypatch, "set_account_password", password=new_password, email="ALICE@example.org")
    save_admin(stale)
    user.refresh_from_db()
    assert user.admin_provisioned and user.verified_at is None
    assert user.check_password(new_password) and not user.check_password(PASSWORD)
    assert not DeviceSession.objects.filter(revoked_at__isnull=True).exists()
    assert_invalidated(client, tokens, pending)


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
@pytest.mark.parametrize("password", ["weak", "alice@example.org"])
def test_reset_uses_user_password_validators_without_changing_approval(monkeypatch, user, password):
    old_hash = user.password
    with pytest.raises(CommandError):
        run_private_command(monkeypatch, "set_account_password", password=password, email=user.email)
    user.refresh_from_db()
    assert user.password == old_hash
    assert getattr(user, "admin_provisioned", False) is False


def managed_disabled_settings():
    return {
        "ACCOUNTS_ACCOUNT_MODE": "managed", "ACCOUNTS_MAIL_DELIVERY": "disabled",
        **{key: None for key in REQUIRED if key.startswith("ACCOUNTS_SMTP_") or key == "ACCOUNTS_FROM_EMAIL"},
    }


def test_managed_production_starts_without_any_smtp_configuration():
    assert load_settings(managed_disabled_settings()) == 0


@pytest.mark.parametrize("missing", [key for key in REQUIRED if not key.startswith("ACCOUNTS_SMTP_") and key != "ACCOUNTS_FROM_EMAIL"])
def test_managed_disabled_retains_other_production_requirements(missing):
    assert load_settings({**managed_disabled_settings(), missing: None}) != 0


@pytest.mark.parametrize("mode", ["unknown", "", "Managed"])
def test_unknown_account_mode_fails_closed(mode):
    assert load_settings({"ACCOUNTS_ACCOUNT_MODE": mode}) != 0


def test_self_service_cannot_disable_mail_and_managed_smtp_keeps_checks():
    assert load_settings({**managed_disabled_settings(), "ACCOUNTS_ACCOUNT_MODE": "self_service"}) != 0
    assert load_settings({"ACCOUNTS_ACCOUNT_MODE": "managed"}) == 0
    assert load_settings({"ACCOUNTS_ACCOUNT_MODE": "managed", "ACCOUNTS_SMTP_PASSWORD": None}) != 0


@pytest.mark.django_db
def test_managed_policy_rejects_existing_verified_unapproved_code_access_and_refresh(client, user, application):
    tokens, _ = mint(client, user, application)
    pending = code_request(client, user, application)
    # Exercise eligibility itself separately from the required deployment epoch change.
    with override_settings(ACCOUNT_MODE="managed"):
        assert client.get("/api/v1/me", **headers(tokens)).status_code == 401
        assert client.get("/o/userinfo/", **headers(tokens)).status_code == 401
        assert client.post("/o/token/", pending).status_code == 400
        assert refresh(client, tokens["refresh_token"]).status_code == 400


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_provision_never_overwrites_existing_unapproved_account(monkeypatch, user):
    before = (user.password, user.name, user.verified_at)
    with pytest.raises(CommandError):
        run_private_command(monkeypatch, "provision_account", email="ALICE@EXAMPLE.ORG", name="Replacement")
    user.refresh_from_db()
    assert not user.admin_provisioned
    assert (user.password, user.name, user.verified_at) == before


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
@pytest.mark.parametrize("password", ["", "first-line\nsecond-line", "x" * 1025])
def test_private_input_rejects_empty_multiline_and_oversized_values(monkeypatch, user, password):
    before = user.password
    with pytest.raises(CommandError):
        run_private_command(monkeypatch, "set_account_password", email=user.email, password=password)
    user.refresh_from_db()
    assert user.password == before


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_terminal_echo_fallback_fails_without_creating_user(monkeypatch):
    import getpass
    import warnings

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def unavailable(prompt):
        warnings.warn("Cannot control echo", getpass.GetPassWarning)
        return PASSWORD

    monkeypatch.setattr("getpass.getpass", unavailable)
    assert "provision_account" in get_commands()
    with pytest.raises(CommandError):
        call_command("provision_account", email="new@example.org", name="New")
    assert not User.objects.exists()


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_reset_preserves_disabled_unapproved_account_state(monkeypatch, user):
    user.is_active = False
    user.save(update_fields=["is_active"])
    verified = user.verified_at
    run_private_command(monkeypatch, "set_account_password", email=user.email, password="Another-Private-Password-42!")
    user.refresh_from_db()
    assert not user.is_active and not user.admin_provisioned
    assert user.verified_at == verified


@pytest.mark.django_db
@override_settings(ACCOUNT_MODE="managed")
def test_reset_unknown_account_does_not_create_one(monkeypatch):
    with pytest.raises(CommandError):
        run_private_command(monkeypatch, "set_account_password", email="missing@example.org")
    assert not User.objects.exists()


@pytest.mark.django_db(transaction=True)
@override_settings(ACCOUNT_MODE="managed")
def test_stale_full_model_save_cannot_restore_pre_revocation_credentials(client, user, application):
    approve(user)
    tokens, _ = mint(client, user, application)
    pending = code_request(client, user, application)
    stale = User.objects.get(pk=user.pk)
    user.admin_provisioned = False
    user.save()
    user.admin_provisioned = True
    user.save()
    current_version = user.auth_version
    stale.name = "Saved after reapproval"
    stale.save()
    user.refresh_from_db()
    assert user.auth_version == current_version
    assert_invalidated(client, tokens, pending)
