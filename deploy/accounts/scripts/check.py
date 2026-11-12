#!/usr/bin/env python3
"""Offline structure validation, not Docker/Caddy execution or resource acceptance."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
config = yaml.safe_load((ROOT / "compose.yaml").read_text())
assert config["name"] == "titan-accounts"
# A gateway can join old product networks too; avoid its common "api" DNS alias.
assert set(config["services"]) == {"accounts-api", "worker", "db"}
assert not config["services"]["worker"].get("profiles")
assert all(not service.get("ports") for service in config["services"].values())
assert (
    sum(int(service["mem_limit"][:-1]) for service in config["services"].values())
    == 384
)
for name, service in config["services"].items():
    assert service["mem_limit"] == service["memswap_limit"]
    assert service["logging"]["options"] == {"max-size": "5m", "max-file": "2"}
    assert "network_mode" not in service and not service.get("privileged")
    if name != "db":
        assert service["read_only"] and service["cap_drop"] == ["ALL"]
        assert service["user"] == "10001:10001"
        # A comma in an unquoted YAML flow item silently creates a second mount.
        # Check the parsed mount contract before Docker tries to start the API.
        assert len(service["tmpfs"]) == 1, "Expected one bounded /tmp mount"
        mount, options = service["tmpfs"][0].split(":", 1)
        assert mount == "/tmp" and set(options.split(",")) == {
            "size=16m", "mode=1777"
        }, "Expected a 16 MiB writable temporary directory with sticky permissions"
assert re.search(r"@sha256:[a-f0-9]{64}$", config["services"]["db"]["image"])
assert config["networks"]["database"]["internal"]
assert config["networks"]["gateway"]["external"]
assert config["volumes"]["accounts_database"]["name"] == "titan_accounts_database"
managed = yaml.safe_load((ROOT / "compose.managed.yaml").read_text())
assert set(managed["services"]) == {"accounts-api", "worker"}
assert managed["services"]["worker"]["profiles"] == ["mail-worker-disabled"]
for name in ("accounts-api", "worker"):
    assert managed["services"][name]["environment"] == {
        "ACCOUNTS_ACCOUNT_MODE": "managed",
        "ACCOUNTS_MAIL_DELIVERY": "disabled",
    }
assert (
    sum(int(config["services"][name]["mem_limit"][:-1]) for name in ("accounts-api", "db"))
    == 304
)
example = dict(
    line.split("=", 1)
    for line in (ROOT / "env.managed.example").read_text().splitlines()
    if line and not line.startswith("#")
)
assert example["ACCOUNTS_ACCOUNT_MODE"] == "managed"
assert example["ACCOUNTS_MAIL_DELIVERY"] == "disabled"
assert not any("SMTP" in key or key == "ACCOUNTS_FROM_EMAIL" for key in example)
for key in ("ACCOUNTS_IMAGE", "ACCOUNTS_ISSUER", "ACCOUNTS_SECRET_KEY", "PGPASSWORD"):
    assert example[key] == ""
preview = yaml.safe_load((ROOT / "compose.preview.yaml").read_text())
assert preview["services"]["accounts-api"]["ports"] == ["127.0.0.1:18080:8000"]
assert re.search(r"FROM .+@sha256:[a-f0-9]{64}", (ROOT / "Dockerfile").read_text())
fragment = (ROOT / "Caddyfile.fragment").read_text()
assert "reverse_proxy titan-accounts-accounts-api-1:8000" in fragment
assert "header_up X-Titan-Client-IP {http.request.remote.host}" in fragment
assert "header_up X-Forwarded-Proto https" in fragment
print(
    "Offline deployment checks passed; container/runtime/capacity gates remain separate."
)
