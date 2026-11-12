"""Production boundary checks do not connect to SMTP or a database."""

import os
import subprocess
import sys

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

REQUIRED = {
    "ACCOUNTS_SECRET_KEY": "x" * 64,
    "ACCOUNTS_ISSUER": "https://accounts.example.invalid",
    "ACCOUNTS_SESSION_EPOCH": "deployment-test-epoch",
    "ACCOUNTS_ALLOWED_HOSTS": "accounts.example.invalid",
    "PGDATABASE": "titan_accounts",
    "PGUSER": "titan_accounts_app",
    "PGPASSWORD": "test-only-db-password",
    "PGHOST": "db",
    "PGPORT": "5432",
    "ACCOUNTS_MAIL_DELIVERY": "smtp",
    "ACCOUNTS_FROM_EMAIL": "accounts@example.invalid",
    "ACCOUNTS_SMTP_HOST": "smtp.example.invalid",
    "ACCOUNTS_SMTP_PORT": "587",
    "ACCOUNTS_SMTP_USER": "test-only-user",
    "ACCOUNTS_SMTP_PASSWORD": "test-only-password",
    "ACCOUNTS_TRUSTED_PROXY_IPS": "172.30.81.2",
}


def load_settings(overrides):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ACCOUNTS_", "PG"))}
    env.update(
        REQUIRED,
        ACCOUNTS_DEBUG="0",
        ACCOUNTS_RSA_KEY_FILE=os.environ["ACCOUNTS_RSA_KEY_FILE"],
    )
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-c", "import config.settings"], env=env, capture_output=True
    ).returncode


@pytest.mark.parametrize("missing", list(REQUIRED))
def test_production_requires_explicit_configuration(missing):
    assert load_settings({missing: None}) != 0


@pytest.mark.parametrize(
    "key,value",
    [
        ("ACCOUNTS_ISSUER", "https://accounts.example.invalid/path"),
        ("ACCOUNTS_ISSUER", "https://user:pass@accounts.example.invalid"),
        ("ACCOUNTS_ALLOWED_HOSTS", "*"),
        ("ACCOUNTS_ALLOWED_HOSTS", "other.example.invalid"),
        ("ACCOUNTS_TRUSTED_PROXY_IPS", "0.0.0.0/0"),
        ("ACCOUNTS_TRUSTED_PROXY_IPS", "garbage"),
        ("ACCOUNTS_TRUSTED_PROXY_IPS", ","),
        ("ACCOUNTS_MAIL_DELIVERY", "disabled"),
        ("ACCOUNTS_FROM_EMAIL", "accounts@localhost"),
        ("PGUSER", "postgres"),
    ],
)
def test_production_rejects_unsafe_configuration(key, value):
    assert load_settings({key: value}) != 0


def test_explicit_production_configuration_loads():
    assert load_settings({}) == 0


@override_settings(TRUSTED_PROXY_IPS=["172.30.81.2"])
@pytest.mark.parametrize(
    "peer,trusted", [("172.30.81.2", True), ("203.0.113.4", False)]
)
def test_gateway_headers_require_exact_peer(peer, trusted):
    from accounts.security import TrustedGatewayMiddleware

    request = RequestFactory().get(
        "/login",
        REMOTE_ADDR=peer,
        HTTP_X_TITAN_CLIENT_IP="198.51.100.9",
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_X_FORWARDED_FOR="1.2.3.4",
        HTTP_FORWARDED="for=1.2.3.4;proto=https",
    )
    TrustedGatewayMiddleware(lambda req: HttpResponse())(request)
    assert request.META["REMOTE_ADDR"] == ("198.51.100.9" if trusted else peer)
    assert request.is_secure() is trusted
    assert "HTTP_X_FORWARDED_FOR" not in request.META
    assert "HTTP_FORWARDED" not in request.META


@override_settings(TRUSTED_PROXY_IPS=["172.30.81.2"])
@pytest.mark.parametrize("value", ["", "198.51.100.9, 1.2.3.4", "garbage"])
def test_gateway_rejects_missing_or_multiple_client_addresses(value):
    from accounts.security import TrustedGatewayMiddleware

    request = RequestFactory().get(
        "/login",
        REMOTE_ADDR="172.30.81.2",
        HTTP_X_TITAN_CLIENT_IP=value,
        HTTP_X_FORWARDED_PROTO="https",
    )
    response = TrustedGatewayMiddleware(lambda req: HttpResponse())(request)
    assert response.status_code == 400
