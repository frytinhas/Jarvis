"""Quota-bounded, redacted JSON Lines infrastructure diagnostic persistence."""

from __future__ import annotations

import errno
import json
import os
import stat
import threading
from collections.abc import Callable
from contextlib import suppress
from datetime import timedelta
from pathlib import Path
from typing import Final

from jarvis.config.defaults import DiagnosticDefaults
from jarvis.diagnostics.events import InfrastructureEvent
from jarvis.diagnostics.redaction import RedactionMetadata, Redactor
from jarvis.foundation.clock import Clock, format_utc
from jarvis.foundation.errors import DiagnosticError, StorageError
from jarvis.storage.quota import QuotaAccountant, QuotaCategory, QuotaLimit, QuotaReservation
from jarvis.storage.xdg import (
    PRIVATE_DIRECTORY_MODE,
    PRIVATE_FILE_MODE,
    verify_private_directory,
    verify_private_file,
    verify_private_file_descriptor,
)

FOUNDATION_DIAGNOSTICS: Final = QuotaCategory("foundation_diagnostics")
WriteFunction = Callable[[int, bytes], int]


class InfrastructureDiagnosticSink:
    """Owns sanitization, serialization, append recovery, rotation, and retention."""

    def __init__(
        self,
        state_directory: Path,
        defaults: DiagnosticDefaults,
        clock: Clock,
        *,
        write_function: WriteFunction = os.write,
    ) -> None:
        self._defaults = defaults
        self._clock = clock
        self._write = write_function
        self._lock = threading.RLock()
        verify_private_directory(state_directory)
        self.directory = state_directory / "diagnostics"
        self.directory.mkdir(mode=PRIVATE_DIRECTORY_MODE, parents=False, exist_ok=True)
        metadata = self.directory.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            raise DiagnosticError(
                code="diagnostics.persistence_failed",
                message_key="error.diagnostics.unsafe_directory",
            )
        self._redactor = Redactor(
            max_text_bytes=defaults.text_bytes,
            max_depth=defaults.max_depth,
            max_container_entries=defaults.max_container_entries,
        )
        self._active_path: Path | None = None
        self._active_descriptor: int | None = None
        self._healthy = True
        self._recover_abandoned_files()
        initial_usage = self._prune_closed(required_capacity=0)
        self._accountant = QuotaAccountant(
            (QuotaLimit(FOUNDATION_DIAGNOSTICS, defaults.total_bytes),)
        )
        self._accountant.set_authoritative_usage(FOUNDATION_DIAGNOSTICS, initial_usage)

    @property
    def healthy(self) -> bool:
        return self._healthy

    def usage_bytes(self) -> int:
        return self._accountant.snapshot(FOUNDATION_DIAGNOSTICS).used_bytes

    def ensure_evidence_capacity(self, required_bytes: int) -> QuotaReservation:
        """Reserve required local diagnostic evidence before later work begins."""

        with self._lock:
            self._require_healthy()
            return self._accountant.reserve(
                FOUNDATION_DIAGNOSTICS,
                required_bytes,
                reconcile=lambda: self._prune_closed(required_capacity=required_bytes),
            )

    def emit(self, event: InfrastructureEvent) -> int:
        """Sanitize, bound, and durably append one event; return encoded byte count."""

        with self._lock:
            self._require_healthy()
            encoded = self._encode(event)
            if len(encoded) > self._defaults.event_bytes:
                raise DiagnosticError(
                    code="diagnostics.invalid_event",
                    message_key="error.diagnostics.event_too_large",
                    safe_details={"maximum_bytes": self._defaults.event_bytes},
                )
            self._rotate_if_needed(len(encoded))
            if self._active_descriptor is None:
                self._open_active(event)
            reservation = self.ensure_evidence_capacity(len(encoded))
            descriptor = self._active_descriptor
            if descriptor is None:
                reservation.release()
                raise AssertionError("diagnostic descriptor was not opened")
            previous_offset = os.lseek(descriptor, 0, os.SEEK_END)
            try:
                written = self._write(descriptor, encoded)
                if written != len(encoded):
                    raise OSError(errno.ENOSPC, "partial diagnostic write")
                os.fsync(descriptor)
            except OSError as error:
                try:
                    os.ftruncate(descriptor, previous_offset)
                    os.fsync(descriptor)
                except OSError:
                    pass
                reservation.release()
                self._healthy = False
                raise DiagnosticError(
                    code="diagnostics.persistence_failed",
                    message_key="error.diagnostics.persistence_failed",
                    safe_details={
                        "reason": "storage_exhausted" if error.errno == errno.ENOSPC else "io"
                    },
                    internal_message=str(error),
                ) from error
            reservation.commit(len(encoded))
            return len(encoded)

    def close(self) -> None:
        with self._lock:
            self._close_active()
            if self._healthy:
                usage = self._prune_closed(required_capacity=0)
                self._accountant.set_authoritative_usage(FOUNDATION_DIAGNOSTICS, usage)

    def abandon(self) -> None:
        """Close an active descriptor after failure while retaining `.open` recovery evidence."""

        with self._lock:
            descriptor = self._active_descriptor
            self._active_descriptor = None
            self._active_path = None
            if descriptor is not None:
                with suppress(OSError):
                    os.close(descriptor)

    def _encode(self, event: InfrastructureEvent) -> bytes:
        redacted = self._redactor.redact_value(event.fields)
        metadata = redacted.metadata
        envelope: dict[str, object] = {
            "schema_version": event.schema_version,
            "event_id": str(event.event_id),
            "timestamp_utc": format_utc(event.timestamp_utc),
            "event_type": event.event_type,
            "subsystem": event.subsystem,
            "severity": event.severity.value,
            "fields": redacted.value,
            "sanitization": self._metadata_dict(metadata),
        }
        if event.correlation_id is not None:
            envelope["correlation_id"] = str(event.correlation_id)
        try:
            payload = (
                json.dumps(
                    envelope,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
                + b"\n"
            )
        except (TypeError, ValueError) as error:
            raise DiagnosticError(
                code="diagnostics.invalid_event",
                message_key="error.diagnostics.serialization_failed",
                internal_message=str(error),
            ) from error
        return payload

    @staticmethod
    def _metadata_dict(metadata: RedactionMetadata) -> dict[str, int]:
        return {
            "redacted_values": metadata.redacted_values,
            "truncated_values": metadata.truncated_values,
            "dropped_items": metadata.dropped_items,
            "depth_limited_values": metadata.depth_limited_values,
        }

    def _open_active(self, event: InfrastructureEvent) -> None:
        path = self.directory / f"infrastructure-{event.event_id}.jsonl.open"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor: int | None = None
        opened_identity: tuple[int, int] | None = None
        try:
            descriptor = os.open(path, flags, PRIVATE_FILE_MODE)
            opened = verify_private_file_descriptor(descriptor)
            opened_identity = (opened.st_dev, opened.st_ino)
            self._fsync_directory()
        except (OSError, StorageError) as error:
            if descriptor is not None:
                with suppress(OSError):
                    os.close(descriptor)
                with suppress(OSError, StorageError):
                    current = verify_private_file(path)
                    if (current.st_dev, current.st_ino) == opened_identity:
                        path.unlink()
            self._healthy = False
            raise DiagnosticError(
                code="diagnostics.persistence_failed",
                message_key="error.diagnostics.open_failed",
                internal_message=str(error),
            ) from error
        assert descriptor is not None
        self._active_path = path
        self._active_descriptor = descriptor

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if self._active_descriptor is None:
            return
        size = os.fstat(self._active_descriptor).st_size
        if size + incoming_bytes > self._defaults.file_bytes:
            self._close_active()
            usage = self._prune_closed(required_capacity=incoming_bytes)
            self._accountant.set_authoritative_usage(FOUNDATION_DIAGNOSTICS, usage)

    def _close_active(self) -> None:
        descriptor = self._active_descriptor
        path = self._active_path
        self._active_descriptor = None
        self._active_path = None
        if descriptor is None or path is None:
            return
        try:
            opened = verify_private_file_descriptor(descriptor)
            current = verify_private_file(path)
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise OSError(errno.ESTALE, "active diagnostic identity changed")
            os.fsync(descriptor)
            os.close(descriptor)
            closed = path.with_suffix("")
            if closed.exists() or closed.is_symlink():
                raise FileExistsError(closed)
            os.replace(path, closed)
            self._fsync_directory()
        except (OSError, StorageError) as error:
            self._healthy = False
            with suppress(OSError):
                os.close(descriptor)
            raise DiagnosticError(
                code="diagnostics.persistence_failed",
                message_key="error.diagnostics.close_failed",
                internal_message=str(error),
            ) from error

    def _recover_abandoned_files(self) -> None:
        for path in sorted(self.directory.glob("*.open")):
            try:
                metadata = verify_private_file(path)
                if metadata.st_size > self._defaults.file_bytes:
                    raise OSError(errno.EFBIG, "abandoned diagnostic file exceeds limit")
                flags = os.O_RDWR
                if hasattr(os, "O_CLOEXEC"):
                    flags |= os.O_CLOEXEC
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                descriptor = os.open(path, flags)
                try:
                    opened = verify_private_file_descriptor(descriptor)
                    if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                        raise OSError(errno.ESTALE, "diagnostic identity changed")
                    content = bytearray()
                    while chunk := os.read(descriptor, 64 * 1024):
                        content.extend(chunk)
                    if content and not content.endswith(b"\n"):
                        boundary = content.rfind(b"\n") + 1
                        os.ftruncate(descriptor, boundary)
                        del content[boundary:]
                    for line in bytes(content).splitlines():
                        decoded = json.loads(line)
                        if not isinstance(decoded, dict):
                            raise ValueError("diagnostic line is not an object")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                recovered = path.with_name(
                    path.name.removesuffix(".jsonl.open") + ".recovered.jsonl"
                )
                if recovered.exists() or recovered.is_symlink():
                    raise FileExistsError(recovered)
                os.replace(path, recovered)
                self._fsync_directory()
            except (OSError, ValueError, json.JSONDecodeError, StorageError) as error:
                self._healthy = False
                raise DiagnosticError(
                    code="diagnostics.persistence_failed",
                    message_key="error.diagnostics.recovery_failed",
                    internal_message=str(error),
                ) from error

    def _prune_closed(self, *, required_capacity: int) -> int:
        closed: list[tuple[Path, os.stat_result]] = []
        for path in sorted(self.directory.glob("*.jsonl")):
            metadata = verify_private_file(path)
            closed.append((path, metadata))
        closed.sort(key=lambda item: (item[1].st_mtime_ns, item[0].name))

        cutoff = self._clock.now() - timedelta(days=self._defaults.retention_days)
        retained: list[tuple[Path, os.stat_result]] = []
        for path, metadata in closed:
            closed_at = self._clock.now().fromtimestamp(
                metadata.st_mtime, tz=self._clock.now().tzinfo
            )
            if closed_at < cutoff:
                path.unlink()
            else:
                retained.append((path, metadata))
        while len(retained) > self._defaults.max_closed_files:
            path, _ = retained.pop(0)
            path.unlink()

        active_size = 0
        for path in self.directory.glob("*.open"):
            active_size += verify_private_file(path).st_size
        total = active_size + sum(metadata.st_size for _, metadata in retained)
        target = self._defaults.total_bytes - required_capacity
        while total > target and retained:
            path, metadata = retained.pop(0)
            path.unlink()
            total -= metadata.st_size
        return total

    def _require_healthy(self) -> None:
        if not self._healthy:
            raise DiagnosticError(
                code="diagnostics.persistence_failed",
                message_key="error.diagnostics.sink_unhealthy",
            )

    def _fsync_directory(self) -> None:
        flags = os.O_RDONLY | os.O_DIRECTORY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.directory, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
