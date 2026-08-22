"""Bounded installation identity and immutable managed-asset manifest."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from base64 import urlsafe_b64decode
from csv import reader
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Self

from jarvis.installation.errors import installation_error

MANIFEST_SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 128 * 1024


@dataclass(frozen=True, slots=True)
class ManagedAsset:
    role: str
    path: str
    mode: int
    sha256: str
    device: int
    inode: int

    @classmethod
    def capture(cls, role: str, path: Path, expected_mode: int) -> Self:
        metadata = _safe_regular(path, expected_mode)
        return cls(
            role,
            str(path),
            expected_mode,
            _hash_file(path),
            metadata.st_dev,
            metadata.st_ino,
        )

    def verify(self) -> None:
        path = Path(self.path)
        metadata = _safe_regular(path, self.mode)
        if (metadata.st_dev, metadata.st_ino) != (self.device, self.inode):
            raise installation_error("installation.asset_identity_changed", path=str(path))
        if _hash_file(path) != self.sha256:
            raise installation_error("installation.asset_changed", path=str(path))


@dataclass(frozen=True, slots=True)
class InterpreterIdentity:
    path: str
    device: int
    inode: int
    sha256: str

    @classmethod
    def capture(cls, path: Path) -> Self:
        metadata = _safe_regular(path, None)
        return cls(
            str(path),
            metadata.st_dev,
            metadata.st_ino,
            _hash_file(path, expected=metadata),
        )

    def verify(self) -> None:
        metadata = _safe_regular(Path(self.path), None)
        if (metadata.st_dev, metadata.st_ino) != (self.device, self.inode):
            raise installation_error("installation.interpreter_identity_changed")
        if _hash_file(Path(self.path), expected=metadata) != self.sha256:
            raise installation_error("installation.interpreter_changed")


@dataclass(frozen=True, slots=True)
class InstallationManifestV1:
    schema_version: int
    installation_id: str
    distribution_name: str
    distribution_version: str
    wheel_sha256: str
    installation_root: str
    interpreter: InterpreterIdentity
    package_record: ManagedAsset
    assets: tuple[ManagedAsset, ...]

    def to_bytes(self) -> bytes:
        value = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")) + "\n"
        encoded = value.encode("utf-8")
        if len(encoded) > MAX_MANIFEST_BYTES:
            raise installation_error("installation.manifest_too_large")
        return encoded

    @classmethod
    def from_bytes(cls, raw: bytes) -> Self:
        if not raw or len(raw) > MAX_MANIFEST_BYTES:
            raise installation_error("installation.manifest_invalid", reason="size")
        try:
            value = json.loads(raw)
            if not isinstance(value, dict) or set(value) != {
                "schema_version",
                "installation_id",
                "distribution_name",
                "distribution_version",
                "wheel_sha256",
                "installation_root",
                "interpreter",
                "package_record",
                "assets",
            }:
                raise ValueError
            interpreter = value["interpreter"]
            package_record = value["package_record"]
            assets = value["assets"]
            if (
                not isinstance(interpreter, dict)
                or not isinstance(package_record, dict)
                or not isinstance(assets, list)
            ):
                raise ValueError
            result = cls(
                schema_version=int(value["schema_version"]),
                installation_id=str(value["installation_id"]),
                distribution_name=str(value["distribution_name"]),
                distribution_version=str(value["distribution_version"]),
                wheel_sha256=str(value["wheel_sha256"]),
                installation_root=str(value["installation_root"]),
                interpreter=InterpreterIdentity(**interpreter),
                package_record=ManagedAsset(**package_record),
                assets=tuple(ManagedAsset(**item) for item in assets),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise installation_error("installation.manifest_invalid", reason="schema") from error
        if (
            result.schema_version != MANIFEST_SCHEMA_VERSION
            or not result.installation_id
            or len(result.assets) > 32
            or len({item.path for item in result.assets}) != len(result.assets)
        ):
            raise installation_error("installation.manifest_invalid", reason="values")
        return result


def load_manifest(path: Path) -> InstallationManifestV1:
    metadata = _safe_regular(path, 0o600)
    if metadata.st_size > MAX_MANIFEST_BYTES:
        raise installation_error("installation.manifest_invalid", reason="size")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise installation_error("installation.manifest_changed")
        raw = os.read(descriptor, MAX_MANIFEST_BYTES + 1)
    finally:
        os.close(descriptor)
    return InstallationManifestV1.from_bytes(raw)


def verify_manifest(manifest: InstallationManifestV1) -> None:
    manifest.interpreter.verify()
    manifest.package_record.verify()
    _verify_package_record(Path(manifest.package_record.path), Path(manifest.installation_root))
    manifest.package_record.verify()
    for asset in manifest.assets:
        asset.verify()


def hash_path(path: Path) -> str:
    return _hash_file(path)


def _safe_regular(path: Path, mode: int | None) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise installation_error("installation.asset_unavailable", path=str(path)) from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
        or (mode is not None and stat.S_IMODE(metadata.st_mode) != mode)
    ):
        raise installation_error("installation.asset_unsafe", path=str(path))
    return metadata


def _hash_file(path: Path, *, expected: os.stat_result | None = None) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or (
                expected is not None
                and (metadata.st_dev, metadata.st_ino) != (expected.st_dev, expected.st_ino)
            )
        ):
            raise installation_error("installation.asset_unsafe", path=str(path))
        while chunk := os.read(descriptor, 128 * 1024):
            digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _verify_package_record(record_path: Path, installation_root: Path) -> None:
    """Verify wheel-owned code without executing metadata from the private venv."""

    try:
        site_packages = record_path.parent.parent.resolve(strict=True)
        root = installation_root.resolve(strict=True)
        rows = list(reader(record_path.read_text(encoding="utf-8").splitlines()))
    except (OSError, UnicodeError) as error:
        raise installation_error("installation.package_record_invalid") from error
    if not rows:
        raise installation_error("installation.package_record_invalid")
    seen: set[str] = set()
    for row in rows:
        if len(row) != 3 or not row[0] or row[0] in seen:
            raise installation_error("installation.package_record_invalid")
        seen.add(row[0])
        candidate = (site_packages / row[0]).resolve(strict=False)
        if not candidate.is_relative_to(root):
            raise installation_error("installation.package_record_invalid")
        digest, _size = row[1], row[2]
        if not digest:
            continue
        if candidate == record_path:
            raise installation_error("installation.package_record_invalid")
        if not digest.startswith("sha256="):
            raise installation_error("installation.package_record_invalid")
        try:
            expected = urlsafe_b64decode(digest.removeprefix("sha256=") + "===")
            actual = bytes.fromhex(_hash_file(candidate))
        except (ValueError, OSError) as error:
            raise installation_error("installation.package_record_invalid") from error
        if actual != expected:
            raise installation_error("installation.package_changed", path=str(candidate))
