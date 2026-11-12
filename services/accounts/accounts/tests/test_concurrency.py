"""These tests require PostgreSQL, exercise separate connections, and never use SQLite."""

import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.test import Client

from .test_endpoints import headers, mint, refresh


def race(function):
    barrier = Barrier(2)

    def worker():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return function(Client())
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: worker(), range(2)))
    return results


@pytest.mark.django_db(transaction=True)
def test_concurrent_refresh_mints_at_most_one_and_replay_revokes_it(
    client, user, application
):
    assert connection.vendor == "postgresql"
    tokens, _ = mint(client, user, application)
    results = race(lambda c: refresh(c, tokens["refresh_token"]))
    assert sorted(r.status_code for r in results) == [200, 400]
    descendant = next(r.json() for r in results if r.status_code == 200)
    assert client.get("/api/v1/me", **headers(descendant)).status_code == 401
    assert refresh(client, descendant["refresh_token"]).status_code == 400


@pytest.mark.django_db(transaction=True)
def test_concurrent_recovery_consumption_has_one_winner(client, user):
    from accounts.models import MailOutbox

    client.post("/recover", {"email": user.email})
    url = re.search(
        r"http://testserver[^\s]+", MailOutbox.objects.latest("created_at").body
    ).group()
    results = race(lambda c: c.post(url, {"password": "Changed-Password-Value-42!"}))
    assert sorted(r.status_code for r in results) == [200, 400]
    user.refresh_from_db()
    assert user.check_password("Changed-Password-Value-42!")


@pytest.mark.django_db(transaction=True)
def test_concurrent_code_exchange_has_one_winner(client, user, application):
    from urllib.parse import parse_qs, urlparse

    from .test_endpoints import CALLBACK, VERIFIER, authorize

    response = authorize(client, user, application)
    code = parse_qs(urlparse(response["Location"]).query)["code"][0]
    data = {
        "grant_type": "authorization_code",
        "client_id": "titan-desktop",
        "code": code,
        "redirect_uri": CALLBACK,
        "code_verifier": VERIFIER,
    }
    results = race(lambda c: c.post("/o/token/", data))
    assert sorted(r.status_code for r in results) == [200, 400]
