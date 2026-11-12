#!/usr/bin/env python3
"""Create a non-secret, per-release review record. Never deploys/restarts anything."""

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--image", required=True)
p.add_argument("--previous-image")
p.add_argument("--candidate-gateway", type=Path, required=True)
p.add_argument("--previous-gateway", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
for image in (a.image, a.previous_image):
    if image is not None and not re.fullmatch(r"[^\s]+@sha256:[a-f0-9]{64}", image):
        p.error("Both images must use immutable sha256 digests")
root = Path(__file__).resolve().parents[3]
revision = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=root, text=True
).strip()
record = {
    "revision": revision,
    "image": a.image,
    "previous_image": a.previous_image,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "candidate_gateway_sha256": hashlib.sha256(
        a.candidate_gateway.read_bytes()
    ).hexdigest(),
    "previous_gateway_sha256": hashlib.sha256(
        a.previous_gateway.read_bytes()
    ).hexdigest(),
    "migrations": [
        path.name
        for path in sorted(
            (root / "services/accounts/accounts/migrations").glob("[0-9]*.py")
        )
    ],
    "migration_digest": hashlib.sha256(
        (root / "services/accounts/uv.lock").read_bytes()
        + b"".join(
            path.read_bytes()
            for path in sorted(
                (root / "services/accounts/accounts/migrations").glob("[0-9]*.py")
            )
        )
    ).hexdigest(),
    "deployment_performed": False,
    "required_gates": [
        "schema rollback compatibility reviewed",
        "old product health before and after",
        "Caddy validate using installed version",
        "384 MiB measured with container limits",
        "SMTP verification/recovery delivered",
        "encrypted backup restored with new epoch",
    ],
}
with a.output.open("x") as handle:
    json.dump(record, handle, indent=2)
    handle.write("\n")
print("Release review manifest written; nothing deployed.")
