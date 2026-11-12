#!/usr/bin/env python3
"""Prepare an image-only rollback override; never execute Docker or alter data/gateway."""

import argparse
import json
import re
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--current", type=Path, required=True)
p.add_argument("--target", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
current = json.loads(a.current.read_text())
target = json.loads(a.target.read_text())
if not current.get("migration_digest") or current["migration_digest"] != target.get(
    "migration_digest"
):
    p.error(
        "Schema differs; automatic image rollback refused. Review forward recovery separately."
    )
image = target.get("image", "")
if not re.fullmatch(r"[^\s]+@sha256:[a-f0-9]{64}", image):
    p.error("Target must be a recorded immutable image digest")
with a.output.open("x") as handle:
    json.dump(
        {"services": {"accounts-api": {"image": image}, "worker": {"image": image}}},
        handle,
        indent=2,
    )
    handle.write("\n")
print(
    "Image-only rollback override prepared; database, volumes, epoch, gateway and services untouched."
)
