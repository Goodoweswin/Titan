import base64
from pathlib import Path
import subprocess

import pytest

from scripts.prepare_beta_update import prepare_update, require_forward_update


@pytest.fixture
def signed_update(tmp_path):
    def write_signature(version, suffix="macos-arm64.app.tar.gz"):
        archive = tmp_path / f"Titan-0.4.4-{suffix}"
        archive.write_bytes(suffix.encode())
        signature = base64.b64encode(
            f"untrusted comment: signature\nfirst\ntrusted comment: file:{suffix}\tversion:{version}\nlast\n".encode()
        ).decode()
        archive.with_name(archive.name + ".sig").write_text(signature + "\n")
        return signature

    return write_signature


def test_manifest_uses_both_verified_assets_at_the_exact_beta_tag(tmp_path, signed_update, monkeypatch):
    signature = signed_update("0.4.4")
    windows_signature = signed_update("0.4.4", "windows-x64-setup.exe")
    public_key = base64.b64encode(b"public key").decode()
    checked = set()

    def verify(command, *, check):
        assert check is True
        assert command[:2] == ["minisign", "-Vm"]
        suffix = Path(command[2]).read_text()
        checked.add(suffix)
        assert Path(command[4]).read_bytes() == b"public key"
        assert f"file:{suffix}".encode() in Path(command[6]).read_bytes()
        assert b"version:0.4.4" in Path(command[6]).read_bytes()

    monkeypatch.setattr(subprocess, "run", verify)
    assert prepare_update(tmp_path, "0.4.4", "v0.4.4-beta.1", public_key, "更新完成") == {
        "version": "0.4.4",
        "notes": "更新完成",
        "platforms": {
            "darwin-aarch64": {
                "url": "https://github.com/Goodoweswin/Titan/releases/download/v0.4.4-beta.1/Titan-0.4.4-macos-arm64.app.tar.gz",
                "signature": signature,
            },
            "windows-x86_64": {
                "url": "https://github.com/Goodoweswin/Titan/releases/download/v0.4.4-beta.1/Titan-0.4.4-windows-x64-setup.exe",
                "signature": windows_signature,
            },
        },
    }
    assert checked == {"macos-arm64.app.tar.gz", "windows-x64-setup.exe"}


def test_release_refuses_an_asset_with_mismatched_signed_version(tmp_path, signed_update, monkeypatch):
    signed_update("0.4.4")
    signed_update("0.4.3", "windows-x64-setup.exe")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="signature version"):
        prepare_update(tmp_path, "0.4.4", "v0.4.4-beta.1", "cHVi", "")


def test_release_refuses_a_signature_minisign_cannot_verify(tmp_path, signed_update, monkeypatch):
    signed_update("0.4.4")
    signed_update("0.4.4", "windows-x64-setup.exe")

    def reject(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(subprocess, "run", reject)
    with pytest.raises(subprocess.CalledProcessError):
        prepare_update(tmp_path, "0.4.4", "v0.4.4-beta.1", "cHVi", "")


def test_release_requires_the_windows_signature(tmp_path, signed_update, monkeypatch):
    signed_update("0.4.4")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(FileNotFoundError, match="windows-x64-setup.exe.sig"):
        prepare_update(tmp_path, "0.4.4", "v0.4.4-beta.1", "cHVi", "")


def test_manifest_allows_exact_retry_but_rejects_older_or_replaced_version():
    active = {"version": "0.4.9", "platforms": {"darwin-aarch64": {"signature": "original"}}}
    require_forward_update(active, None)
    require_forward_update(active, active)
    require_forward_update({"version": "0.4.10"}, active)
    with pytest.raises(ValueError, match="already active"):
        require_forward_update({"version": "0.4.9"}, active)
    with pytest.raises(ValueError, match="older"):
        require_forward_update({"version": "0.4.8"}, active)
