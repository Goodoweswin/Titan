"""Verify the signed installers and prepare the Titan Beta update feed."""

import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import tempfile


def _version(value):
    if not isinstance(value, str) or not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value, re.ASCII):
        raise ValueError(f"Invalid app version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def require_forward_update(candidate, previous):
    if previous is None:
        return
    current_version = _version(previous["version"])
    next_version = _version(candidate["version"])
    if next_version < current_version:
        raise ValueError("Candidate is older than the active Beta update")
    if next_version == current_version and candidate != previous:
        raise ValueError("This application version is already active with different release metadata")


def _verified_signature(artifact, version, public_key):
    signature = artifact.with_name(artifact.name + ".sig").read_text(encoding="ascii").strip()
    signature_bytes = base64.b64decode(signature, validate=True)
    with tempfile.TemporaryDirectory(prefix="titan-minisign-") as directory:
        public_key_file = Path(directory) / "key.pub"
        public_key_file.write_bytes(base64.b64decode(public_key.strip(), validate=True))
        signature_file = Path(directory) / "update.minisig"
        signature_file.write_bytes(signature_bytes)
        subprocess.run(
            ["minisign", "-Vm", str(artifact), "-p", str(public_key_file), "-x", str(signature_file)],
            check=True,
        )

    trusted_comment = signature_bytes.decode("ascii").splitlines()[2]
    signed_versions = [
        value.removeprefix("version:")
        for value in trusted_comment.split("\t")
        if value.startswith("version:")
    ]
    if signed_versions != [version]:
        raise ValueError(f"The trusted signature version for {artifact.name} does not match the app version")
    return signature


def prepare_update(release_dir, version, tag, public_key, notes):
    _version(version)
    if not re.fullmatch(rf"v{re.escape(version)}-beta\.[1-9][0-9]*", tag):
        raise ValueError("Release tag does not match the app version and Beta channel")
    artifacts = {
        "darwin-aarch64": f"Titan-{version}-macos-arm64.app.tar.gz",
        "windows-x86_64": f"Titan-{version}-windows-x64-setup.exe",
    }
    return {
        "version": version,
        "notes": notes,
        "platforms": {
            platform: {
                "url": f"https://github.com/Goodoweswin/Titan/releases/download/{tag}/{name}",
                "signature": _verified_signature(release_dir / name, version, public_key),
            }
            for platform, name in artifacts.items()
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--notes", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    notes = args.notes.read_text(encoding="utf-8").strip()
    manifest = prepare_update(args.release_dir, args.version, args.tag, config["plugins"]["updater"]["pubkey"], notes)
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous else None
    require_forward_update(manifest, previous)
    args.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
