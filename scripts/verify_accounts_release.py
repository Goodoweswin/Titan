"""Check release manifests and the actual native binary's embedded issuer.

This is a static artifact check, not a substitute for native login acceptance.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import plistlib
import tomllib
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--platform", required=True, choices=["macos-arm64", "windows-x64"])
    parser.add_argument("--native-version", help="Windows PE product version read by the build runner")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    origin = urlsplit(args.issuer)
    if (
        origin.scheme != "https" or not origin.hostname or origin.username
        or origin.password or origin.path or origin.query or origin.fragment
        or args.issuer != f"https://{origin.netloc}"
    ):
        parser.error("Issuer must be an exact HTTPS origin without a trailing slash")

    root = Path(__file__).resolve().parents[1]
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    tauri = json.loads((root / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    cargo = tomllib.loads((root / "src-tauri/Cargo.toml").read_text(encoding="utf-8"))
    cargo_lock = tomllib.loads((root / "src-tauri/Cargo.lock").read_text(encoding="utf-8"))
    engine_init = ast.parse((root / "backend/titan_wb/__init__.py").read_text(encoding="utf-8"))
    engine_version = next(
        ast.literal_eval(node.value)
        for node in engine_init.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
    )
    versions = {
        "package": package["version"],
        "packageLock": lock["version"],
        "packageLockRoot": lock["packages"][""]["version"],
        "tauri": tauri["version"],
        "cargo": cargo["package"]["version"],
        "cargoLock": next(p["version"] for p in cargo_lock["package"] if p["name"] == "titan-wb"),
        "scientificEngine": engine_version,
    }
    if len(set(versions.values())) != 1:
        parser.error("Release version manifests disagree")
    binary = args.binary.read_bytes()
    if args.issuer.encode("ascii") not in binary:
        parser.error("Native binary is missing the expected compiled account issuer")
    if args.platform == "macos-arm64":
        info = plistlib.loads((args.binary.parent.parent / "Info.plist").read_bytes())
        native_version = info["CFBundleShortVersionString"]
    else:
        native_version = args.native_version or ""
    parts = native_version.split(".")
    if parts[:3] != package["version"].split(".") or any(p != "0" for p in parts[3:]):
        parser.error("Native bundle/PE product version disagrees with release manifests")
    report = {
        "platform": args.platform,
        "version": package["version"],
        "issuer": args.issuer,
        "versionManifestsAgree": True,
        "nativeVersion": native_version,
        "embeddedIssuerFound": True,
        "nativeBinarySHA256": hashlib.sha256(binary).hexdigest(),
        "scope": "Static artifact check; native login and credential-store acceptance are separate.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
