import base64
from pathlib import Path
import subprocess

import pytest

from scripts.prepare_beta_update import prepare_update, require_forward_update


@pytest.fixture
def macos_update(tmp_path):
    archive = tmp_path / "Titan-0.4.4-macos-arm64.app.tar.gz"
    archive.write_bytes(b"candidate app")

    def write_signature(version):
        signature = base64.b64encode(
            f"untrusted comment: signature\nfirst\ntrusted comment: file:app\tversion:{version}\nlast\n".encode()
        ).decode()
        archive.with_suffix(".gz.sig").write_text(signature + "\n")
        return signature

    return write_signature


def test_manifest_uses_the_verified_mac_asset_at_the_exact_beta_tag(tmp_path, macos_update, monkeypatch):
    signature = macos_update("0.4.4")
    public_key = base64.b64encode(b"public key").decode()

    def verify(command, *, check):
        assert check is True
        assert command[:2] == ["minisign", "-Vm"]
        assert Path(command[2]).read_bytes() == b"candidate app"
        assert Path(command[4]).read_bytes() == b"public key"
        assert b"version:0.4.4" in Path(command[6]).read_bytes()

    monkeypatch.setattr(subprocess, "run", verify)
    assert prepare_update(tmp_path, "0.4.4", "v0.4.4-beta.1", public_key, "更新完成") == {
        "version": "0.4.4",
        "notes": "更新完成",
        "platforms": {
            "darwin-aarch64": {
                "url": "https://github.com/Goodoweswin/Titan/releases/download/v0.4.4-beta.1/Titan-0.4.4-macos-arm64.app.tar.gz",
                "signature": signature,
            }
        },
    }


def test_release_refuses_an_asset_with_mismatched_signed_version(tmp_path, macos_update, monkeypatch):
    macos_update("0.4.3")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="signature version"):
        prepare_update(tmp_path, "0.4.4", "v0.4.4-beta.1", "cHVi", "")


def test_release_refuses_a_signature_minisign_cannot_verify(tmp_path, macos_update, monkeypatch):
    macos_update("0.4.4")

    def reject(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(subprocess, "run", reject)
    with pytest.raises(subprocess.CalledProcessError):
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
