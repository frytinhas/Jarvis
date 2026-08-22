from __future__ import annotations

import os
import stat
from base64 import urlsafe_b64encode
from hashlib import sha256
from pathlib import Path

import pytest

from jarvis.installation.assets import FIXED_COMMANDS, rendered_assets
from jarvis.installation.bootstrap import install_from_wheel
from jarvis.installation.errors import InstallationError
from jarvis.installation.manifest import (
    InstallationManifestV1,
    InterpreterIdentity,
    ManagedAsset,
    load_manifest,
    verify_manifest,
)
from jarvis.installation.paths import resolve_installation_paths

pytestmark = pytest.mark.unit


def test_paths_and_assets_are_permanent_user_local_foundation() -> None:
    paths = resolve_installation_paths()
    assert paths.installation_root.name == "installation"
    assert paths.private_python == paths.installation_root / "venv/bin/python"
    assert paths.dispatchers == paths.home / ".local/bin"
    assets = rendered_assets(paths)
    assert {path.name for path in assets if path.parent == paths.dispatchers} == set(FIXED_COMMANDS)
    socket = assets[paths.systemd_user / "jarvisd.socket"][2]
    service = assets[paths.systemd_user / "jarvisd.service"][2]
    assert "ListenStream=%t/jarvis-cli/core.sock" in socket
    assert "SocketMode=0600" in socket
    assert "FileDescriptorName=jarvis-core" in socket
    assert "--socket-activation" in service
    assert "Restart=on-failure" in service
    assert "jarvisd &" not in service


def test_manifest_verifies_hash_mode_identity_and_refuses_alteration(tmp_path: Path) -> None:
    interpreter = tmp_path / "python"
    interpreter.write_text("python")
    interpreter.chmod(0o700)
    asset = tmp_path / "jarvis"
    asset.write_text("launcher")
    asset.chmod(0o755)
    site_packages = tmp_path / "site-packages"
    record = site_packages / "jarvis_cli-0.0.0.dist-info" / "RECORD"
    record.parent.mkdir(parents=True)
    package_file = tmp_path / "package.py"
    package_file.write_text("package")
    digest = urlsafe_b64encode(sha256(package_file.read_bytes()).digest()).rstrip(b"=").decode()
    record.write_text(f"../package.py,sha256={digest},7\njarvis_cli-0.0.0.dist-info/RECORD,,\n")
    record.chmod(0o644)
    manifest = InstallationManifestV1(
        1,
        "installation-id",
        "jarvis-cli",
        "0.0.0",
        "0" * 64,
        str(tmp_path),
        InterpreterIdentity.capture(interpreter),
        ManagedAsset.capture("wheel-record", record, 0o644),
        (ManagedAsset.capture("dispatcher:jarvis", asset, 0o755),),
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(manifest.to_bytes())
    manifest_path.chmod(0o600)
    loaded = load_manifest(manifest_path)
    verify_manifest(loaded)
    asset.write_text("altered")
    with pytest.raises(InstallationError, match="installation.asset_changed"):
        verify_manifest(loaded)


def test_manifest_detects_private_interpreter_and_wheel_code_tampering(tmp_path: Path) -> None:
    interpreter = tmp_path / "python"
    interpreter.write_text("private-python")
    interpreter.chmod(0o700)
    package = tmp_path / "site-packages" / "jarvis" / "module.py"
    package.parent.mkdir(parents=True)
    package.write_text("trusted")
    record = tmp_path / "site-packages" / "jarvis_cli-0.0.0.dist-info" / "RECORD"
    record.parent.mkdir()
    digest = urlsafe_b64encode(sha256(package.read_bytes()).digest()).rstrip(b"=").decode()
    record.write_text(f"jarvis/module.py,sha256={digest},7\njarvis_cli-0.0.0.dist-info/RECORD,,\n")
    record.chmod(0o644)
    manifest = InstallationManifestV1(
        1,
        "installation-id",
        "jarvis-cli",
        "0.0.0",
        "0" * 64,
        str(tmp_path),
        InterpreterIdentity.capture(interpreter),
        ManagedAsset.capture("wheel-record", record, 0o644),
        (),
    )
    interpreter.write_text("altered")
    with pytest.raises(InstallationError, match="installation.interpreter_changed"):
        verify_manifest(manifest)
    interpreter.write_text("private-python")
    package.write_text("altered")
    with pytest.raises(InstallationError, match="installation.package_changed"):
        verify_manifest(manifest)


def test_manifest_refuses_symlink_and_hardlink_assets(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.write_text("asset")
    target.chmod(0o600)
    linked = tmp_path / "linked"
    os.link(target, linked)
    with pytest.raises(InstallationError, match="installation.asset_unsafe"):
        ManagedAsset.capture("asset", target, 0o600)
    target.unlink()
    symlink = tmp_path / "symlink"
    symlink.symlink_to(linked)
    with pytest.raises(InstallationError, match="installation.asset_unsafe"):
        ManagedAsset.capture("asset", symlink, 0o600)


def test_bootstrap_refuses_foreign_fixed_command_without_overwrite(tmp_path: Path) -> None:
    paths = resolve_installation_paths()
    foreign_bin = tmp_path / "foreign-bin"
    foreign_bin.mkdir()
    foreign = foreign_bin / "jarvis"
    foreign.write_text("foreign")
    foreign.chmod(0o755)
    wheel = tmp_path / "jarvis_cli-0.0.0-py3-none-any.whl"
    wheel.write_bytes(b"not reached")
    environment = dict(os.environ)
    environment["PATH"] = str(foreign_bin)
    with pytest.raises(InstallationError, match="installation.path_collision"):
        install_from_wheel(wheel, paths=paths, env=environment)
    assert foreign.read_text() == "foreign"
    assert stat.S_IMODE(paths.installation_root.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(paths.manifest_directory.parent.stat().st_mode) == 0o700
