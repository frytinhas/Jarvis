"""Crash-safe Milestone 000 initialization and strictly read-only inspection."""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import stat
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path

from jarvis.config.defaults import DefaultsRegistry
from jarvis.diagnostics.events import InfrastructureEvent, Severity
from jarvis.diagnostics.sink import InfrastructureDiagnosticSink
from jarvis.foundation.clock import Clock, SystemClock, format_utc
from jarvis.foundation.errors import StorageError
from jarvis.foundation.identifiers import IdGenerator, RandomIdGenerator
from jarvis.security.installation import discover_active_installation
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import MigrationRunner
from jarvis.storage.xdg import (
    PRIVATE_FILE_MODE,
    XdgPaths,
    initialize_xdg_directories,
    resolve_xdg_paths,
    verify_private_directory,
    verify_private_file,
    verify_private_file_descriptor,
)

FOUNDATION_STATE_VERSION = 1
DATABASE_FILENAME = "jarvis.sqlite3"
MARKER_FILENAME = "foundation-state.json"
LOCK_FILENAME = "foundation-initialize.lock"

AtomicWriter = Callable[[Path, bytes, str], None]


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("zero-length write")
        offset += written


def _atomic_private_write(path: Path, payload: bytes, suffix: str) -> None:
    verify_private_directory(path.parent)
    temporary = path.with_name(f".{path.name}.tmp-{suffix}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    created_identity: tuple[int, int] | None = None
    try:
        if path.exists() or path.is_symlink():
            verify_private_file(path)
        descriptor = os.open(temporary, flags, PRIVATE_FILE_MODE)
        created_metadata = os.fstat(descriptor)
        created_identity = (created_metadata.st_dev, created_metadata.st_ino)
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        verify_private_file(path)
    except OSError as error:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        try:
            temporary_metadata = temporary.lstat()
            if (
                created_identity is not None
                and (temporary_metadata.st_dev, temporary_metadata.st_ino) == created_identity
            ):
                temporary.unlink()
        except OSError:
            pass
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.atomic_write_failed",
            internal_message=str(error),
        ) from error


@contextmanager
def _initialization_lock(runtime_directory: Path) -> Iterator[None]:
    verify_private_directory(runtime_directory)
    path = runtime_directory / LOCK_FILENAME
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags, PRIVATE_FILE_MODE)
        verify_private_file(path)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except (OSError, StorageError) as error:
        if descriptor is not None:
            os.close(descriptor)
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.initialization_lock_failed",
            internal_message=str(error),
        ) from error
    try:
        yield
    finally:
        assert descriptor is not None
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def initialize_foundation(
    env: Mapping[str, str] | None = None,
    *,
    clock: Clock | None = None,
    identifiers: IdGenerator | None = None,
    atomic_writer: AtomicWriter = _atomic_private_write,
) -> dict[str, object]:
    """Initialize every foundation component and publish the completion marker last."""

    active_clock = SystemClock() if clock is None else clock
    id_generator = RandomIdGenerator() if identifiers is None else identifiers
    paths = resolve_xdg_paths(env)
    initialize_xdg_directories(paths)
    defaults = DefaultsRegistry.load_packaged().current()
    with _initialization_lock(paths.runtime):
        database_path = paths.data / DATABASE_FILENAME
        with SQLiteDatabase(database_path) as database:
            migration = MigrationRunner(database, active_clock).apply()

        sink = InfrastructureDiagnosticSink(
            paths.state, defaults.foundation_diagnostics, active_clock
        )
        event = InfrastructureEvent(
            event_id=id_generator.new_event_id(),
            timestamp_utc=active_clock.now(),
            event_type="foundation.initialized",
            subsystem="foundation.bootstrap",
            severity=Severity.INFO,
            fields={
                "foundation_state_version": FOUNDATION_STATE_VERSION,
                "defaults_schema_version": defaults.defaults_schema_version,
                "product_defaults_version": defaults.product_defaults_version,
                "database_schema_version": migration.current_version,
                "applied_migrations": list(migration.applied_versions),
            },
        )
        try:
            sink.emit(event)
            sink.close()
        except BaseException:
            sink.abandon()
            raise
        diagnostic_usage = sink.usage_bytes()

        completed_at = format_utc(active_clock.now())
        marker = {
            "foundation_state_version": FOUNDATION_STATE_VERSION,
            "defaults_schema_version": defaults.defaults_schema_version,
            "product_defaults_version": defaults.product_defaults_version,
            "database_schema_version": migration.current_version,
            "completed_at_utc": completed_at,
        }
        marker_payload = (
            json.dumps(marker, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
                "utf-8"
            )
            + b"\n"
        )
        marker_suffix = str(id_generator.new_event_id())
        atomic_writer(paths.state / MARKER_FILENAME, marker_payload, marker_suffix)

    return {
        "status": "initialized",
        "paths": _path_dict(paths),
        "foundation_state_version": FOUNDATION_STATE_VERSION,
        "defaults_schema_version": defaults.defaults_schema_version,
        "product_defaults_version": defaults.product_defaults_version,
        "database_schema_version": migration.current_version,
        "applied_migrations": list(migration.applied_versions),
        "diagnostics": {"healthy": sink.healthy, "usage_bytes": diagnostic_usage},
        "completed_at_utc": completed_at,
    }


def inspect_foundation(env: Mapping[str, str] | None = None) -> dict[str, object]:
    """Inspect foundation state without creating directories, files, WALs, or diagnostics."""

    paths = resolve_xdg_paths(env)
    defaults = DefaultsRegistry.load_packaged().current()
    directory_safety = {name: _directory_is_safe(path) for name, path in _path_items(paths)}
    database_version, migration_rows = _inspect_database(paths.data / DATABASE_FILENAME)
    diagnostic_health, diagnostic_usage, diagnostic_files = _inspect_diagnostics(paths.state)
    marker = _inspect_marker(paths.state / MARKER_FILENAME)
    installation = discover_active_installation()
    return {
        "status": "inspected",
        "paths": _path_dict(paths),
        "directory_safety": directory_safety,
        "foundation_state_version": marker.get("foundation_state_version"),
        "defaults_schema_version": defaults.defaults_schema_version,
        "product_defaults_version": defaults.product_defaults_version,
        "database_schema_version": database_version,
        "migrations": migration_rows,
        "diagnostics": {
            "healthy": diagnostic_health,
            "usage_bytes": diagnostic_usage,
            "file_count": diagnostic_files,
        },
        "installation": {
            "identity_version": installation.identity_version,
            "mode": installation.mode.value,
            "complete": installation.complete,
            "active_import_anchor": str(installation.active_import_anchor),
            "protected_roots": [str(root.path) for root in installation.protected_roots],
        },
        "marker": marker,
    }


def _path_items(paths: XdgPaths) -> tuple[tuple[str, Path], ...]:
    return (
        ("config", paths.config),
        ("data", paths.data),
        ("state", paths.state),
        ("cache", paths.cache),
        ("runtime", paths.runtime),
    )


def _path_dict(paths: XdgPaths) -> dict[str, str]:
    return {name: str(path) for name, path in _path_items(paths)}


def _directory_is_safe(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISDIR(metadata.st_mode)
        and metadata.st_uid == os.getuid()
        and stat.S_IMODE(metadata.st_mode) == 0o700
    )


def _inspect_database(path: Path) -> tuple[int | None, list[dict[str, object]]]:
    descriptor: int | None = None
    try:
        expected = verify_private_file(path)
        for sidecar_suffix in ("-wal", "-shm"):
            sidecar = path.with_name(path.name + sidecar_suffix)
            if sidecar.exists() or sidecar.is_symlink():
                verify_private_file(sidecar)
                return None, []
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        opened = verify_private_file_descriptor(descriptor)
        if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
            return None, []
        uri = f"file:/proc/self/fd/{descriptor}?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True)
        try:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
            ).fetchone()
            if exists is None:
                return 0, []
            rows = connection.execute(
                "SELECT version, name, checksum_sha256, applied_at_utc "
                "FROM schema_migrations ORDER BY version"
            ).fetchall()
        finally:
            connection.close()
    except (OSError, sqlite3.Error, StorageError):
        return None, []
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
    return int(rows[-1][0]) if rows else 0, [
        {
            "version": int(row[0]),
            "name": str(row[1]),
            "checksum_sha256": str(row[2]),
            "applied_at_utc": str(row[3]),
        }
        for row in rows
    ]


def _inspect_diagnostics(state: Path) -> tuple[bool, int, int]:
    directory = state / "diagnostics"
    if not _directory_is_safe(directory):
        return False, 0, 0
    total = 0
    count = 0
    try:
        for path in directory.iterdir():
            if not path.name.endswith((".jsonl", ".open")):
                continue
            total += verify_private_file(path).st_size
            count += 1
    except (OSError, StorageError):
        return False, total, count
    return True, total, count


def _inspect_marker(path: Path) -> dict[str, object]:
    descriptor: int | None = None
    try:
        expected = verify_private_file(path)
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        metadata = verify_private_file_descriptor(descriptor)
        if (metadata.st_dev, metadata.st_ino) != (expected.st_dev, expected.st_ino):
            return {}
        if metadata.st_size > 64 * 1024:
            return {}
        payload = os.read(descriptor, 64 * 1024 + 1)
        if len(payload) > 64 * 1024:
            return {}
        parsed = json.loads(payload.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError, StorageError):
        return {}
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
