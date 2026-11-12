"""Real ModelForms loaded before competing PostgreSQL writes must merge safely."""

import re
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib import admin
from django.forms import modelform_factory
from django.test import RequestFactory

from accounts.admin import AccountAdmin
from accounts.models import MailOutbox, User

from .test_endpoints import (
    CALLBACK,
    PASSWORD,
    VERIFIER,
    authorize,
    headers,
    mint,
    refresh,
)


def edit_form(instance, **changes):
    form_type = modelform_factory(User, fields=["name", "is_active"])
    form = form_type(
        {"name": instance.name, "is_active": instance.is_active, **changes},
        instance=instance,
    )
    assert form.is_valid(), form.errors
    return form


def save_admin(form):
    AccountAdmin(User, admin.site).save_model(
        RequestFactory().post("/admin/"), form.save(commit=False), form, True
    )


@pytest.mark.django_db(transaction=True)
def test_stale_admin_name_edit_preserves_disable_and_all_credential_invalidation(
    client, user, application
):
    response = authorize(client, user, application)
    code = parse_qs(urlparse(response["Location"]).query)["code"][0]
    client.post("/recover", {"email": user.email})
    old_link = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    stale_form = edit_form(User.objects.get(pk=user.pk), name="Changed nickname")
    save_admin(edit_form(User.objects.get(pk=user.pk), is_active=False))
    disabled_version = User.objects.get(pk=user.pk).auth_version
    save_admin(stale_form)
    user.refresh_from_db()
    assert user.is_active is False
    assert user.name == "Changed nickname"
    assert user.auth_version == disabled_version
    save_admin(edit_form(user, is_active=True))
    assert (
        client.post(
            "/o/token/",
            {
                "grant_type": "authorization_code",
                "client_id": "titan-desktop",
                "code": code,
                "redirect_uri": CALLBACK,
                "code_verifier": VERIFIER,
            },
        ).status_code
        == 400
    )
    assert (
        client.post(old_link, {"password": "Old-Link-Must-Not-Work-42!"}).status_code
        == 400
    )
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
    assert urlparse(response["Location"]).path == "/login"


@pytest.mark.django_db(transaction=True)
def test_stale_admin_nickname_edit_cannot_undo_password_reset(
    client, user, application
):
    tokens, _ = mint(client, user, application)
    stale_form = edit_form(User.objects.get(pk=user.pk), name="Name after reset")
    client.post("/recover", {"email": user.email})
    link = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    new_password = "Current-Reset-Password-Value-42!"
    assert client.post(link, {"password": new_password}).status_code == 200
    current = User.objects.get(pk=user.pk)
    save_admin(stale_form)
    user.refresh_from_db()
    assert user.password == current.password
    assert user.auth_version == current.auth_version
    assert user.check_password(new_password)
    assert not user.check_password(PASSWORD)
    assert user.name == "Name after reset"
    assert client.get("/api/v1/me", **headers(tokens)).status_code == 401
    assert refresh(client, tokens["refresh_token"]).status_code == 400


@pytest.mark.django_db
def test_admin_change_without_form_metadata_fails_closed(user):
    with pytest.raises(ValueError):
        AccountAdmin(User, admin.site).save_model(
            RequestFactory().post("/admin/"), user, None, True
        )


@pytest.mark.django_db(transaction=True)
def test_admin_password_form_preserves_newer_disable_and_version(user):
    model_admin = AccountAdmin(User, admin.site)
    form = model_admin.change_password_form(
        User.objects.get(pk=user.pk),
        {
            "password1": "Admin-Password-Value-42!",
            "password2": "Admin-Password-Value-42!",
            "usable_password": "true",
        },
    )
    assert form.is_valid(), form.errors
    save_admin(edit_form(User.objects.get(pk=user.pk), is_active=False))
    current = User.objects.get(pk=user.pk)
    form.save()
    user.refresh_from_db()
    assert user.is_active is False
    assert user.auth_version == current.auth_version
    assert user.check_password("Admin-Password-Value-42!")


@pytest.mark.django_db(transaction=True)
def test_unchanged_admin_groups_preserve_newer_memberships(user):
    from django.contrib.auth.models import Group

    form_type = modelform_factory(User, fields=["name", "groups"])
    form = form_type(
        {"name": "New nickname", "groups": []}, instance=User.objects.get(pk=user.pk)
    )
    assert form.is_valid(), form.errors
    group = Group.objects.create(name="New assignment")
    user.groups.add(group)
    save_admin(form)
    AccountAdmin(User, admin.site).save_related(
        RequestFactory().post("/admin/"), form, [], True
    )
    assert list(user.groups.values_list("pk", flat=True)) == [group.pk]
