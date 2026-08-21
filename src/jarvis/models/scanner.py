"""Descriptor-relative, bounded, read-only GGUF discovery."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from jarvis.models.errors import InvalidGgufError, ScanLimitExceededError, UnreadableModelError
from jarvis.models.gguf import read_gguf_fd
from jarvis.models.models import ModelAvailability, ModelId, ModelRecord

MAX_DIRECTORIES = 32
MAX_PATH_BYTES = 4096
MAX_DEPTH = 16
MAX_DIRECTORY_ENTRIES = 100_000
MAX_CANDIDATES = 100_000

_DIRECTORY_FLAGS = (
    os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
)
_FILE_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
)


@dataclass(frozen=True, slots=True)
class ScanResult:
    records: tuple[ModelRecord, ...]
    partial_reason: str | None


@dataclass(frozen=True, slots=True)
class ScanHooks:
    """Deterministic race barriers used by adversarial tests; production uses no hooks."""

    before_directory_read: Callable[[Path], None] | None = None
    before_candidate_open: Callable[[Path], None] | None = None
    after_candidate_open: Callable[[Path, int], None] | None = None
    after_candidate_parse: Callable[[Path, int], None] | None = None


def _fingerprint(path: Path, metadata: os.stat_result, header_digest: str) -> str:
    digest = hashlib.sha256()
    digest.update(os.fsencode(path))
    digest.update(b"\0")
    digest.update(
        f"{metadata.st_dev}:{metadata.st_ino}:{metadata.st_size}:{metadata.st_mtime_ns}".encode(
            "ascii"
        )
    )
    digest.update(b"\0")
    digest.update(header_digest.encode("ascii"))
    return digest.hexdigest()


def _safe_record_path(path: Path) -> Path:
    try:
        str(path).encode("utf-8")
    except UnicodeEncodeError:
        return Path(os.fsencode(path).decode("utf-8", errors="backslashreplace"))
    return path


def _record_failure(
    path: Path, metadata: os.stat_result, availability: ModelAvailability, reason: str
) -> ModelRecord:
    safe_path = _safe_record_path(path)
    digest = hashlib.sha256(reason.encode("ascii")).hexdigest()
    return ModelRecord(
        ModelId.new(),
        safe_path,
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        {},
        _fingerprint(safe_path, metadata, digest),
        availability,
        reason,
        "",
    )


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino, stat.S_IFMT(left.st_mode)) == (
        right.st_dev,
        right.st_ino,
        stat.S_IFMT(right.st_mode),
    )


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    return _same_identity(left, right) and (left.st_size, left.st_mtime_ns) == (
        right.st_size,
        right.st_mtime_ns,
    )


def _path_matches(path: Path, expected: os.stat_result) -> bool:
    try:
        current = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    return _same_identity(current, expected)


def _entry_matches(directory_fd: int, name: str, expected: os.stat_result) -> bool:
    try:
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError:
        return False
    return _same_identity(current, expected)


def scan_directories(roots: tuple[Path, ...], *, hooks: ScanHooks | None = None) -> ScanResult:
    """Discover candidate files without reopening a mutable path after validation."""
    active_hooks = hooks or ScanHooks()
    records: list[ModelRecord] = []
    seen: set[tuple[int, int]] = set()
    entries = candidates = 0
    stack: list[tuple[int, Path, int]] = []
    active_roots = roots[:MAX_DIRECTORIES]
    partial_reason: str | None = "directories" if len(roots) > MAX_DIRECTORIES else None
    try:
        for root in reversed(active_roots):
            try:
                descriptor = os.open(root, _DIRECTORY_FLAGS)
            except OSError:
                partial_reason = partial_reason or "root_unavailable"
                continue
            stack.append((descriptor, root, 0))
        while stack:
            directory_fd, display_directory, depth = stack.pop()
            first_record = len(records)
            try:
                initial_directory = os.fstat(directory_fd)
                if not stat.S_ISDIR(initial_directory.st_mode) or not _path_matches(
                    display_directory, initial_directory
                ):
                    partial_reason = partial_reason or "directory_unavailable"
                    continue
                if active_hooks.before_directory_read is not None:
                    active_hooks.before_directory_read(display_directory)
                directory_changed = not _path_matches(display_directory, initial_directory)
                if directory_changed:
                    partial_reason = partial_reason or "directory_changed_during_scan"
                    continue
                with os.scandir(directory_fd) as iterator:
                    names: list[str] = []
                    for entry in iterator:
                        entries += 1
                        if entries > MAX_DIRECTORY_ENTRIES:
                            raise ScanLimitExceededError("directory_entries")
                        names.append(entry.name)
                    names.sort()
                    for name in names:
                        if not _path_matches(display_directory, initial_directory):
                            directory_changed = True
                            partial_reason = partial_reason or "directory_changed_during_scan"
                            break
                        try:
                            entry_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                        except OSError:
                            continue
                        if stat.S_ISDIR(entry_stat.st_mode):
                            if depth < MAX_DEPTH:
                                try:
                                    child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=directory_fd)
                                except OSError:
                                    continue
                                opened_child = os.fstat(child_fd)
                                if not _same_identity(entry_stat, opened_child):
                                    os.close(child_fd)
                                    continue
                                stack.append((child_fd, display_directory / name, depth + 1))
                            else:
                                # There may be candidates beyond the configured scan domain.
                                # Do not let reconciliation treat an intentionally bounded walk
                                # as authoritative for records that were not visited.
                                partial_reason = partial_reason or "depth"
                            continue
                        if not stat.S_ISREG(entry_stat.st_mode) or not name.lower().endswith(
                            ".gguf"
                        ):
                            continue
                        candidates += 1
                        if candidates > MAX_CANDIDATES:
                            raise ScanLimitExceededError("candidates")
                        identity = (entry_stat.st_dev, entry_stat.st_ino)
                        if identity in seen:
                            continue
                        seen.add(identity)
                        # This path is presentation/persistence metadata only. Execution must
                        # revalidate from a descriptor in M005; the read itself is descriptor-bound.
                        path = display_directory / name
                        try:
                            str(path).encode("utf-8")
                        except UnicodeEncodeError:
                            records.append(
                                _record_failure(
                                    path,
                                    entry_stat,
                                    ModelAvailability.UNREADABLE,
                                    "path_encoding",
                                )
                            )
                            continue
                        if active_hooks.before_candidate_open is not None:
                            active_hooks.before_candidate_open(path)
                        try:
                            file_fd = os.open(name, _FILE_FLAGS, dir_fd=directory_fd)
                        except OSError:
                            reason = (
                                "candidate_changed_before_open"
                                if not _entry_matches(directory_fd, name, entry_stat)
                                else "open_failed"
                            )
                            records.append(
                                _record_failure(
                                    path, entry_stat, ModelAvailability.UNREADABLE, reason
                                )
                            )
                            continue
                        try:
                            opened = os.fstat(file_fd)
                            if not stat.S_ISREG(opened.st_mode) or not _same_identity(
                                entry_stat, opened
                            ):
                                records.append(
                                    _record_failure(
                                        path,
                                        opened,
                                        ModelAvailability.UNREADABLE,
                                        "candidate_changed_before_open",
                                    )
                                )
                                continue
                            if active_hooks.after_candidate_open is not None:
                                active_hooks.after_candidate_open(path, file_fd)
                            parsed = read_gguf_fd(file_fd)
                            if active_hooks.after_candidate_parse is not None:
                                active_hooks.after_candidate_parse(path, file_fd)
                        except InvalidGgufError as error:
                            if not _same_snapshot(opened, os.fstat(file_fd)):
                                records.append(
                                    _record_failure(
                                        path,
                                        opened,
                                        ModelAvailability.UNREADABLE,
                                        "changed_during_scan",
                                    )
                                )
                            elif not _entry_matches(directory_fd, name, opened):
                                records.append(
                                    _record_failure(
                                        path,
                                        opened,
                                        ModelAvailability.UNREADABLE,
                                        "path_identity_mismatch",
                                    )
                                )
                            else:
                                records.append(
                                    _record_failure(
                                        path,
                                        opened,
                                        ModelAvailability.INVALID,
                                        str(error.safe_details["reason"]),
                                    )
                                )
                            continue
                        except UnreadableModelError as error:
                            records.append(
                                _record_failure(
                                    path,
                                    opened,
                                    ModelAvailability.UNREADABLE,
                                    str(error.safe_details["reason"]),
                                )
                            )
                            continue
                        finally:
                            os.close(file_fd)
                        if not _entry_matches(directory_fd, name, opened):
                            records.append(
                                _record_failure(
                                    path,
                                    opened,
                                    ModelAvailability.UNREADABLE,
                                    "path_identity_mismatch",
                                )
                            )
                            continue
                        final_directory = os.fstat(directory_fd)
                        if not _same_identity(
                            initial_directory, final_directory
                        ) or not _path_matches(display_directory, initial_directory):
                            directory_changed = True
                            partial_reason = partial_reason or "directory_changed_during_scan"
                            records.append(
                                _record_failure(
                                    path,
                                    opened,
                                    ModelAvailability.UNREADABLE,
                                    "directory_changed_during_scan",
                                )
                            )
                            continue
                        records.append(
                            ModelRecord(
                                ModelId.new(),
                                path,
                                parsed.device,
                                parsed.inode,
                                parsed.size,
                                parsed.mtime_ns,
                                parsed.metadata,
                                _fingerprint(path, opened, parsed.header_digest),
                                ModelAvailability.AVAILABLE,
                                None,
                                "",
                            )
                        )
                if directory_changed:
                    records[first_record:] = [
                        replace(
                            record,
                            metadata={},
                            availability=ModelAvailability.UNREADABLE,
                            availability_reason="directory_changed_during_scan",
                        )
                        for record in records[first_record:]
                    ]
            finally:
                os.close(directory_fd)
    except ScanLimitExceededError as error:
        partial_reason = str(error.safe_details["reason"])
    finally:
        for descriptor, _path, _depth in stack:
            os.close(descriptor)
    return ScanResult(tuple(records), partial_reason)
