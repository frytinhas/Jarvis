"""Collision-safe offline bootstrap into Jarvis's private production environment."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from jarvis.installation.assets import FIXED_COMMANDS, rendered_assets
from jarvis.installation.errors import InstallationError, installation_error
from jarvis.installation.manifest import (
    MANIFEST_SCHEMA_VERSION,
    InstallationManifestV1,
    InterpreterIdentity,
    ManagedAsset,
    load_manifest,
    verify_manifest,
)
from jarvis.installation.paths import InstallationPaths, resolve_installation_paths
from jarvis.security.filesystem_identity import has_symlinked_ancestor


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    outcome: str
    installation_root: Path
    manifest: Path
    path_action: str | None


def install_from_wheel(
    wheel: Path,
    *,
    paths: InstallationPaths | None = None,
    systemctl: tuple[str, ...] = ("systemctl", "--user"),
    env: dict[str, str] | None = None,
) -> BootstrapResult:
    """Install or narrowly repair a matching M006C installation from a local wheel."""

    active_paths = resolve_installation_paths(env) if paths is None else paths
    wheel = wheel.absolute()
    wheel_metadata = _safe_input_wheel(wheel)
    wheel_hash = _hash_descriptor(wheel, wheel_metadata)
    existing = _existing_manifest(active_paths)
    transaction = _load_transaction(active_paths)
    recovering = existing is None and transaction is not None
    _validate_roots(active_paths, existing is not None or recovering)
    if recovering:
        assert transaction is not None
        _validate_transaction(transaction, active_paths, wheel_hash)
        _verify_unfinished_environment(active_paths)
    _preflight_commands(active_paths, existing, env, recovering=recovering)
    if existing is None and not recovering:
        _write_transaction(active_paths, wheel_hash)
        transaction = {
            "installation_root": str(active_paths.installation_root),
            "wheel_sha256": wheel_hash,
        }
    if existing is None:
        if not recovering:
            _install_private_environment(wheel, active_paths, env)
        installation_id = str(uuid4())
        outcome = "repaired" if recovering else "installed"
    else:
        _verify_existing_identity(existing, active_paths, wheel_hash)
        installation_id = existing.installation_id
        outcome = "verified"
    desired = rendered_assets(active_paths)
    previous = {} if existing is None else {Path(item.path): item for item in existing.assets}
    repaired = False
    for destination, (_role, mode, body) in desired.items():
        expected = previous.get(destination)
        encoded = body.encode("utf-8")
        if destination.exists() or destination.is_symlink():
            if expected is None:
                if not recovering or not _matches_rendered_asset(destination, encoded, mode):
                    raise installation_error(
                        "installation.command_collision", path=str(destination)
                    )
                continue
            expected.verify()
            if _hash_bytes(encoded) != expected.sha256:
                raise installation_error(
                    "installation.asset_version_mismatch", path=str(destination)
                )
            continue
        if existing is not None:
            if expected is None or _hash_bytes(encoded) != expected.sha256:
                raise installation_error("installation.manifest_invalid", reason="asset_inventory")
            repaired = True
        _write_new_asset(destination, encoded, mode)
    assets = tuple(
        ManagedAsset.capture(role, destination, mode)
        for destination, (role, mode, _body) in sorted(
            desired.items(), key=lambda item: str(item[0])
        )
    )
    manifest = InstallationManifestV1(
        MANIFEST_SCHEMA_VERSION,
        installation_id,
        "jarvis-cli",
        _installed_version(active_paths.private_python),
        wheel_hash,
        str(active_paths.installation_root),
        InterpreterIdentity.capture(active_paths.private_python),
        _package_record(active_paths),
        assets,
    )
    _publish_manifest(active_paths, manifest, existing)
    _remove_transaction(active_paths, transaction)
    _activate_socket(systemctl, env)
    if repaired:
        outcome = "repaired"
    path_action = _path_action(active_paths, env)
    return BootstrapResult(
        outcome, active_paths.installation_root, active_paths.manifest, path_action
    )


def _existing_manifest(paths: InstallationPaths) -> InstallationManifestV1 | None:
    if not (paths.manifest.exists() or paths.manifest.is_symlink()):
        return None
    return load_manifest(paths.manifest)


def _validate_roots(paths: InstallationPaths, existing: bool) -> None:
    for directory in (
        paths.installation_root.parent,
        paths.installation_root,
        paths.dispatchers,
        paths.systemd_user,
        paths.manifest_directory.parent,
        paths.manifest_directory,
    ):
        if directory.exists() or directory.is_symlink():
            metadata = directory.lstat()
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o022
            ):
                raise installation_error("installation.unsafe_directory", path=str(directory))
        else:
            directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        if has_symlinked_ancestor(directory) is not False:
            raise installation_error("installation.unsafe_directory", path=str(directory))
    if not existing and any(paths.installation_root.iterdir()):
        raise installation_error("installation.unowned_root", path=str(paths.installation_root))


def _preflight_commands(
    paths: InstallationPaths,
    manifest: InstallationManifestV1 | None,
    env: dict[str, str] | None,
    *,
    recovering: bool = False,
) -> None:
    owned = set() if manifest is None else {Path(item.path) for item in manifest.assets}
    search_path = (os.environ if env is None else env).get("PATH", os.defpath)
    for command in FIXED_COMMANDS:
        destination = paths.dispatchers / command
        resolved = shutil.which(command, path=search_path)
        if resolved is not None and Path(resolved).absolute() != destination.absolute():
            raise installation_error(
                "installation.path_collision", command=command, path=str(Path(resolved))
            )
        if (destination.exists() or destination.is_symlink()) and destination not in owned:
            rendered = rendered_assets(paths).get(destination)
            if (
                not recovering
                or rendered is None
                or not _matches_rendered_asset(
                    destination, rendered[2].encode("utf-8"), rendered[1]
                )
            ):
                raise installation_error("installation.command_collision", path=str(destination))


def _install_private_environment(
    wheel: Path, paths: InstallationPaths, env: dict[str, str] | None
) -> None:
    if paths.venv.exists() or paths.venv.is_symlink():
        raise installation_error("installation.unowned_environment")
    stage = paths.installation_root / f".venv-stage-{uuid4()}"
    try:
        subprocess.run([sys.executable, "-m", "venv", "--copies", str(stage)], check=True, env=env)
        stage_python = stage / "bin" / "python"
        subprocess.run(
            [
                str(stage_python),
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-index",
                str(wheel),
            ],
            check=True,
            env=env,
        )
        os.replace(stage, paths.venv)
        _fsync_directory(paths.installation_root)
    except (OSError, subprocess.CalledProcessError) as error:
        if stage.exists():
            shutil.rmtree(stage)
        raise installation_error("installation.private_environment_failed") from error


def _verify_existing_identity(
    manifest: InstallationManifestV1, paths: InstallationPaths, wheel_hash: str
) -> None:
    if (
        manifest.installation_root != str(paths.installation_root)
        or manifest.interpreter.path != str(paths.private_python)
        or manifest.wheel_sha256 != wheel_hash
    ):
        raise installation_error("installation.identity_mismatch")
    manifest.interpreter.verify()
    verify_manifest(manifest)
    desired_paths = set(rendered_assets(paths))
    if {Path(item.path) for item in manifest.assets} != desired_paths:
        raise installation_error("installation.manifest_invalid", reason="asset_inventory")
    for item in manifest.assets:
        path = Path(item.path)
        if path.exists() or path.is_symlink():
            item.verify()


def _write_new_asset(path: Path, content: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    directory = _open_safe_directory(path.parent)
    try:
        descriptor = os.open(path.name, flags, mode, dir_fd=directory)
        try:
            offset = 0
            while offset < len(content):
                count = os.write(descriptor, content[offset:])
                if count <= 0:
                    raise OSError("short installation asset write")
                offset += count
            os.fchmod(descriptor, mode)
            os.fsync(descriptor)
            created = os.fstat(descriptor)
            published = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
            if (created.st_dev, created.st_ino) != (published.st_dev, published.st_ino):
                raise installation_error("installation.asset_identity_changed", path=str(path))
        finally:
            os.close(descriptor)
        os.fsync(directory)
    finally:
        os.close(directory)


def _matches_rendered_asset(path: Path, content: bytes, mode: int) -> bool:
    try:
        asset = ManagedAsset.capture("unfinished", path, mode)
    except InstallationError:
        return False
    return asset.sha256 == _hash_bytes(content)


def _write_transaction(paths: InstallationPaths, wheel_hash: str) -> None:
    payload = json.dumps(
        {"installation_root": str(paths.installation_root), "wheel_sha256": wheel_hash},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    _write_new_asset(paths.transaction, payload, 0o600)


def _load_transaction(paths: InstallationPaths) -> dict[str, object] | None:
    if not (paths.transaction.exists() or paths.transaction.is_symlink()):
        return None
    try:
        metadata = paths.transaction.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size > 1024
        ):
            raise ValueError
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(paths.transaction, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                raise ValueError
            value = json.loads(os.read(descriptor, 1025))
        finally:
            os.close(descriptor)
        if not isinstance(value, dict) or set(value) != {"installation_root", "wheel_sha256"}:
            raise ValueError
        return value
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise installation_error("installation.transaction_invalid") from error


def _validate_transaction(
    transaction: dict[str, object], paths: InstallationPaths, wheel_hash: str
) -> None:
    if (
        transaction.get("installation_root") != str(paths.installation_root)
        or transaction.get("wheel_sha256") != wheel_hash
    ):
        raise installation_error("installation.transaction_invalid")


def _verify_unfinished_environment(paths: InstallationPaths) -> None:
    if set(paths.installation_root.iterdir()) != {paths.venv}:
        raise installation_error("installation.unowned_root", path=str(paths.installation_root))
    InterpreterIdentity.capture(paths.private_python).verify()
    record = _package_record(paths)
    provisional = InstallationManifestV1(
        MANIFEST_SCHEMA_VERSION,
        "unfinished",
        "jarvis-cli",
        _installed_version(paths.private_python),
        "unfinished",
        str(paths.installation_root),
        InterpreterIdentity.capture(paths.private_python),
        record,
        (),
    )
    verify_manifest(provisional)


def _remove_transaction(paths: InstallationPaths, expected: dict[str, object] | None) -> None:
    if expected is None:
        return
    current = _load_transaction(paths)
    if current != expected:
        raise installation_error("installation.transaction_invalid")
    directory = _open_safe_directory(paths.manifest_directory)
    try:
        os.unlink(paths.transaction.name, dir_fd=directory)
        os.fsync(directory)
    finally:
        os.close(directory)


def _publish_manifest(
    paths: InstallationPaths,
    manifest: InstallationManifestV1,
    previous: InstallationManifestV1 | None,
) -> None:
    temporary = paths.manifest_directory / f".manifest-v1-{uuid4()}.tmp"
    _write_new_asset(temporary, manifest.to_bytes(), 0o600)
    directory = _open_safe_directory(paths.manifest_directory)
    try:
        if previous is not None:
            before = os.stat(paths.manifest.name, dir_fd=directory, follow_symlinks=False)
            load_manifest(paths.manifest)
            after = os.stat(paths.manifest.name, dir_fd=directory, follow_symlinks=False)
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                raise installation_error("installation.manifest_changed")
        elif paths.manifest.exists() or paths.manifest.is_symlink():
            raise installation_error("installation.manifest_collision")
        os.replace(
            temporary.name,
            paths.manifest.name,
            src_dir_fd=directory,
            dst_dir_fd=directory,
        )
        os.fsync(directory)
    except BaseException:
        with suppress(OSError):
            os.unlink(temporary.name, dir_fd=directory)
        raise
    finally:
        os.close(directory)


def _activate_socket(systemctl: tuple[str, ...], env: dict[str, str] | None) -> None:
    try:
        subprocess.run([*systemctl, "daemon-reload"], check=True, env=env)
        subprocess.run([*systemctl, "enable", "--now", "jarvisd.socket"], check=True, env=env)
    except (OSError, subprocess.CalledProcessError) as error:
        raise installation_error("installation.socket_activation_failed") from error


def _safe_input_wheel(path: Path) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise installation_error("installation.wheel_unavailable") from error
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or path.suffix != ".whl":
        raise installation_error("installation.wheel_unsafe")
    return metadata


def _hash_descriptor(path: Path, expected: os.stat_result) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
            raise installation_error("installation.wheel_changed")
        while chunk := os.read(descriptor, 128 * 1024):
            digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _installed_version(python: Path) -> str:
    command = [
        str(python),
        "-c",
        "from importlib.metadata import version; print(version('jarvis-cli'))",
    ]
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise installation_error("installation.private_environment_invalid") from error


def _package_record(paths: InstallationPaths) -> ManagedAsset:
    records = tuple(paths.venv.glob("lib/python*/site-packages/jarvis_cli-*.dist-info/RECORD"))
    if len(records) != 1:
        raise installation_error("installation.private_environment_invalid")
    try:
        mode = stat.S_IMODE(records[0].lstat().st_mode)
    except OSError as error:
        raise installation_error("installation.private_environment_invalid") from error
    return ManagedAsset.capture("wheel-record", records[0], mode)


def _path_action(paths: InstallationPaths, env: dict[str, str] | None) -> str | None:
    active = os.environ if env is None else env
    entries = [Path(item).absolute() for item in active.get("PATH", "").split(os.pathsep) if item]
    if paths.dispatchers.absolute() in entries:
        return None
    return f'Add {paths.dispatchers} to PATH (for example: export PATH="{paths.dispatchers}:$PATH")'


def _fsync_directory(path: Path) -> None:
    descriptor = _open_safe_directory(path)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _open_safe_directory(path: Path) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
        current = path.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o022
            or (metadata.st_dev, metadata.st_ino) != (current.st_dev, current.st_ino)
        ):
            raise installation_error("installation.unsafe_directory", path=str(path))
        return descriptor
    except BaseException:
        if "descriptor" in locals():
            os.close(descriptor)
        raise
