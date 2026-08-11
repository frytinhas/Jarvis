"""Immutable Linux path snapshots that keep link and followed identities separate."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class FileType(StrEnum):
    REGULAR = "regular"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    SPECIAL = "special"


def _file_type(mode: int) -> FileType:
    if stat.S_ISREG(mode):
        return FileType.REGULAR
    if stat.S_ISDIR(mode):
        return FileType.DIRECTORY
    if stat.S_ISLNK(mode):
        return FileType.SYMLINK
    return FileType.SPECIAL


@dataclass(frozen=True, slots=True)
class FileIdentity:
    device: int
    inode: int
    file_type: FileType
    mode: int
    uid: int
    gid: int
    size: int
    modified_ns: int

    @classmethod
    def from_stat(cls, metadata: os.stat_result) -> FileIdentity:
        return cls(
            metadata.st_dev,
            metadata.st_ino,
            _file_type(metadata.st_mode),
            stat.S_IMODE(metadata.st_mode),
            metadata.st_uid,
            metadata.st_gid,
            metadata.st_size,
            metadata.st_mtime_ns,
        )

    @property
    def inode_key(self) -> tuple[int, int]:
        return (self.device, self.inode)

    def same_object(self, other: FileIdentity) -> bool:
        return self.inode_key == other.inode_key and self.file_type is other.file_type


class SnapshotStatus(StrEnum):
    COMPLETE = "complete"
    MISSING = "missing"
    BROKEN_LINK = "broken_link"
    INACCESSIBLE = "inaccessible"


@dataclass(frozen=True, slots=True)
class PathSnapshot:
    path: Path
    link_identity: FileIdentity | None
    target_identity: FileIdentity | None
    canonical_path: Path | None
    status: SnapshotStatus


def capture_path(path: Path) -> PathSnapshot:
    """Capture lstat and followed stat independently without treating strings as authority."""

    absolute = path.absolute()
    try:
        link_metadata = absolute.lstat()
    except FileNotFoundError:
        return PathSnapshot(absolute, None, None, None, SnapshotStatus.MISSING)
    except OSError:
        return PathSnapshot(absolute, None, None, None, SnapshotStatus.INACCESSIBLE)
    link_identity = FileIdentity.from_stat(link_metadata)
    try:
        target_metadata = absolute.stat()
        canonical = absolute.resolve(strict=True)
    except FileNotFoundError:
        status = (
            SnapshotStatus.BROKEN_LINK
            if link_identity.file_type is FileType.SYMLINK
            else SnapshotStatus.MISSING
        )
        return PathSnapshot(absolute, link_identity, None, None, status)
    except OSError:
        return PathSnapshot(absolute, link_identity, None, None, SnapshotStatus.INACCESSIBLE)
    return PathSnapshot(
        absolute,
        link_identity,
        FileIdentity.from_stat(target_metadata),
        canonical,
        SnapshotStatus.COMPLETE,
    )


def has_symlinked_ancestor(path: Path) -> bool | None:
    """Inspect path components descriptor-relatively; None means traversal was ambiguous."""

    absolute = path.absolute()
    parts = absolute.parts
    if not parts or parts[0] != os.sep:
        return None
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(os.sep, flags)
    except OSError:
        return None
    try:
        for part in parts[1:-1]:
            try:
                metadata = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
            except OSError:
                return None
            if stat.S_ISLNK(metadata.st_mode):
                return True
            if not stat.S_ISDIR(metadata.st_mode):
                return None
            child_flags = flags
            if hasattr(os, "O_NOFOLLOW"):
                child_flags |= os.O_NOFOLLOW
            try:
                child = os.open(part, child_flags, dir_fd=descriptor)
            except OSError:
                return None
            os.close(descriptor)
            descriptor = child
        return False
    finally:
        os.close(descriptor)
