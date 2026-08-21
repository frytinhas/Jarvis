"""Core-owned model registry service; it never executes model/runtime paths."""

from __future__ import annotations

import os
import sqlite3
import stat
import threading
import time
from pathlib import Path

from jarvis.config.defaults import DefaultsRegistry
from jarvis.diagnostics.events import InfrastructureEvent, Severity
from jarvis.diagnostics.sink import InfrastructureDiagnosticSink
from jarvis.foundation.clock import Clock, SystemClock
from jarvis.foundation.identifiers import IdGenerator
from jarvis.models.errors import (
    InvalidRuntimeLocationError,
    ModelDatabaseError,
)
from jarvis.models.gguf import read_gguf_fd
from jarvis.models.models import (
    ModelAvailability,
    ModelId,
    ModelRecord,
    ModelRuntimeConfig,
    RuntimeLocationConfig,
)
from jarvis.models.repository import ModelRepository
from jarvis.models.scanner import (
    MAX_DIRECTORIES,
    MAX_PATH_BYTES,
    ScanResult,
    model_fingerprint,
    scan_directories,
)
from jarvis.profiles.models import ProfileId
from jarvis.storage.database import SQLiteDatabase


class ModelRegistryService:
    def __init__(
        self,
        path: Path,
        clock: Clock | None = None,
        *,
        diagnostics: InfrastructureDiagnosticSink | None = None,
        event_ids: IdGenerator | None = None,
        defaults: DefaultsRegistry | None = None,
    ) -> None:
        self.path = path
        self.clock = clock or SystemClock()
        self.lock = threading.Lock()
        self._diagnostics = diagnostics
        self._event_ids = event_ids
        active_defaults = DefaultsRegistry.load_packaged() if defaults is None else defaults
        self._default_runtime_config = ModelRuntimeConfig.from_mapping(
            dict(active_defaults.current().model_defaults.runtime_config)
        )

    def _diagnose(
        self, event_type: str, fields: dict[str, object], severity: Severity = Severity.INFO
    ) -> None:
        if self._diagnostics is None or self._event_ids is None:
            return
        self._diagnostics.emit(
            InfrastructureEvent(
                self._event_ids.new_event_id(),
                self.clock.now(),
                event_type,
                "models.registry",
                severity,
                fields,
            )
        )

    def runtime_location(self) -> RuntimeLocationConfig:
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=False):
                return ModelRepository(database.connection()).get_runtime_location()
        except sqlite3.Error as error:
            raise ModelDatabaseError("database") from error

    def update_runtime_location(
        self, directories: tuple[str, ...], runtime_path: str | None
    ) -> RuntimeLocationConfig:
        if len(directories) > MAX_DIRECTORIES:
            raise InvalidRuntimeLocationError("directory_limit")
        cleaned: list[Path] = []
        try:
            for raw in directories:
                path = _validated_location(Path(raw), directory=True)
                if len(os.fsencode(path)) > MAX_PATH_BYTES:
                    raise InvalidRuntimeLocationError("directory")
                if path not in cleaned:
                    cleaned.append(path)
            requested_runtime = None if runtime_path is None else Path(runtime_path)
            runtime = (
                None
                if requested_runtime is None
                else _validated_location(requested_runtime, directory=False)
            )
        except OSError as error:
            raise InvalidRuntimeLocationError("unavailable") from error
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=True):
                result = ModelRepository(database.connection()).update_runtime_location(
                    RuntimeLocationConfig(tuple(cleaned), runtime), self.clock.now()
                )
        except sqlite3.Error as error:
            raise ModelDatabaseError("database") from error
        self._diagnose(
            "models.runtime_location_updated",
            {
                "directory_count": len(cleaned),
                "runtime_path_configured": runtime is not None,
                "revision": result.revision,
            },
        )
        return result

    def refresh(self) -> ScanResult:
        with self.lock:
            started = time.monotonic()
            locations = self.runtime_location()
            scanned = scan_directories(locations.model_directories)
            try:
                with SQLiteDatabase(self.path) as database, database.transaction(immediate=True):
                    repository = ModelRepository(database.connection())
                    existing = {
                        record.fingerprint_sha256: record.model_id
                        for record in repository.records()
                    }
                    records = tuple(
                        type(record)(
                            existing.get(record.fingerprint_sha256, record.model_id),
                            record.canonical_path,
                            record.device,
                            record.inode,
                            record.size_bytes,
                            record.mtime_ns,
                            record.metadata,
                            record.fingerprint_sha256,
                            record.availability,
                            record.availability_reason,
                            "",
                        )
                        for record in scanned.records
                    )
                    repository.reconcile(
                        records,
                        self.clock.now(),
                        complete_scan=scanned.partial_reason is None,
                    )
                    result = repository.records()
            except sqlite3.Error as error:
                self._diagnose("models.refresh_failed", {"reason": "database_busy"}, Severity.ERROR)
                raise ModelDatabaseError("busy") from error
            counts = {
                availability.value: sum(record.availability is availability for record in result)
                for availability in ModelAvailability
            }
            self._diagnose(
                "models.refreshed",
                {
                    "directory_count": len(locations.model_directories),
                    "record_count": len(result),
                    "available_count": counts["available"],
                    "missing_count": counts["missing"],
                    "invalid_count": counts["invalid"],
                    "unreadable_count": counts["unreadable"],
                    "partial_reason": scanned.partial_reason,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                },
            )
            return ScanResult(result, scanned.partial_reason)

    def list(self) -> tuple[ModelRecord, ...]:
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=False):
                return ModelRepository(database.connection()).records()
        except sqlite3.Error as error:
            raise ModelDatabaseError("database") from error

    def get(self, model_id: ModelId) -> ModelRecord:
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=False):
                return ModelRepository(database.connection()).get_record(model_id)
        except sqlite3.Error as error:
            raise ModelDatabaseError("database") from error

    def associations(self, profile_id: ProfileId) -> tuple[dict[str, object], ...]:
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=False):
                return ModelRepository(database.connection()).associations(profile_id)
        except sqlite3.Error as error:
            raise ModelDatabaseError("database") from error

    def select(self, profile_id: ProfileId, model_id: ModelId, expected_revision: int) -> None:
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=True):
                ModelRepository(database.connection()).select(
                    profile_id,
                    model_id,
                    expected_revision,
                    self.clock.now(),
                    self._default_runtime_config,
                )
        except sqlite3.Error as error:
            raise ModelDatabaseError("conflict") from error

    def get_config(self, profile_id: ProfileId, model_id: ModelId) -> dict[str, object]:
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=False):
                return ModelRepository(database.connection()).get_config(profile_id, model_id)
        except sqlite3.Error as error:
            raise ModelDatabaseError("database") from error

    def update_config(
        self,
        profile_id: ProfileId,
        model_id: ModelId,
        config: ModelRuntimeConfig,
        expected_revision: int,
    ) -> None:
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=True):
                ModelRepository(database.connection()).update_config(
                    profile_id, model_id, config, expected_revision, self.clock.now()
                )
        except sqlite3.Error as error:
            raise ModelDatabaseError("conflict") from error

    def ensure_runtime_association(self, profile_id: ProfileId, model_id: ModelId) -> int:
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=True):
                return ModelRepository(database.connection()).ensure_association(
                    profile_id, model_id, self._default_runtime_config, self.clock.now()
                )
        except sqlite3.Error as error:
            raise ModelDatabaseError("conflict") from error

    def runtime_association(
        self, profile_id: ProfileId, model_id: ModelId | None = None
    ) -> tuple[ModelRecord, ModelRuntimeConfig, int]:
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=False):
                return ModelRepository(database.connection()).runtime_association(
                    profile_id, model_id
                )
        except sqlite3.Error as error:
            raise ModelDatabaseError("database") from error

    def promote_runtime_selection(
        self, profile_id: ProfileId, model_id: ModelId, expected_revision: int
    ) -> int:
        try:
            with SQLiteDatabase(self.path) as database, database.transaction(immediate=True):
                return ModelRepository(database.connection()).promote_selection(
                    profile_id, model_id, expected_revision, self.clock.now()
                )
        except sqlite3.Error as error:
            raise ModelDatabaseError("conflict") from error

    def open_revalidated_model(self, record: ModelRecord) -> int:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            descriptor = os.open(record.canonical_path, flags)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
            ) != (record.device, record.inode, record.size_bytes, record.mtime_ns):
                raise InvalidRuntimeLocationError("model_identity_changed")
            parsed = read_gguf_fd(descriptor)
            if (
                model_fingerprint(record.canonical_path, metadata, parsed.header_digest)
                != record.fingerprint_sha256
            ):
                raise InvalidRuntimeLocationError("model_fingerprint_changed")
            final = os.fstat(descriptor)
            if (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) != (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
            ):
                raise InvalidRuntimeLocationError("model_changed_during_validation")
            return descriptor
        except BaseException:
            if "descriptor" in locals():
                os.close(descriptor)
            raise


def _validated_location(requested: Path, *, directory: bool) -> Path:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    if directory:
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(requested, flags)
    except OSError as error:
        reason = "directory_symlink" if directory and requested.is_symlink() else "unavailable"
        if not directory and requested.is_symlink():
            reason = "runtime_symlink"
        raise InvalidRuntimeLocationError(reason) from error
    try:
        opened = os.fstat(descriptor)
        if (directory and not stat.S_ISDIR(opened.st_mode)) or (
            not directory and not stat.S_ISREG(opened.st_mode)
        ):
            raise InvalidRuntimeLocationError("directory" if directory else "runtime_path")
        canonical = requested.resolve(strict=True)
        resolved = os.stat(canonical, follow_symlinks=False)
        current = os.stat(requested, follow_symlinks=False)
        identities = {
            (opened.st_dev, opened.st_ino),
            (resolved.st_dev, resolved.st_ino),
            (current.st_dev, current.st_ino),
        }
        if len(identities) != 1 or stat.S_ISLNK(current.st_mode):
            raise InvalidRuntimeLocationError("identity_changed")
        return canonical
    finally:
        os.close(descriptor)
