#!/usr/bin/env python3
"""Offline structure validation, not Docker/Caddy execution or resource acceptance."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
config = yaml.safe_load((ROOT / "compose.yaml").read_text())
assert config["name"] == "titan-accounts"
assert set(config["services"]) == {"api", "worker", "db"}
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
assert re.search(r"@sha256:[a-f0-9]{64}$", config["services"]["db"]["image"])
assert config["networks"]["database"]["internal"]
assert config["networks"]["gateway"]["external"]
assert config["volumes"]["accounts_database"]["name"] == "titan_accounts_database"
preview = yaml.safe_load((ROOT / "compose.preview.yaml").read_text())
assert preview["services"]["api"]["ports"] == ["127.0.0.1:18080:8000"]
assert re.search(r"FROM .+@sha256:[a-f0-9]{64}", (ROOT / "Dockerfile").read_text())
fragment = (ROOT / "Caddyfile.fragment").read_text()
assert "header_up X-Titan-Client-IP {http.request.remote.host}" in fragment
assert "header_up X-Forwarded-Proto https" in fragment
print(
    "Offline deployment checks passed; container/runtime/capacity gates remain separate."
)
