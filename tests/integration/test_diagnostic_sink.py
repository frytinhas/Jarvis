from __future__ import annotations

import errno
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from jarvis.config.defaults import DiagnosticDefaults
from jarvis.diagnostics.events import InfrastructureEvent, Severity
from jarvis.diagnostics.sink import InfrastructureDiagnosticSink
from jarvis.foundation.clock import FakeClock
from jarvis.foundation.errors import DiagnosticError, StorageError
from jarvis.foundation.identifiers import EventId

pytestmark = pytest.mark.integration


def _defaults(**changes: int) -> DiagnosticDefaults:
    values = {
        "total_bytes": 4096,
        "file_bytes": 1024,
        "event_bytes": 768,
        "text_bytes": 256,
        "max_depth": 4,
        "max_container_entries": 8,
        "max_closed_files": 2,
        "retention_days": 30,
    }
    values.update(changes)
    return DiagnosticDefaults(**values)


def _state(tmp_path: Path) -> Path:
    state = tmp_path / "state" / "jarvis-cli"
    state.mkdir(parents=True, mode=0o700)
    return state


def _clock() -> FakeClock:
    return FakeClock(datetime(2026, 8, 10, 12, tzinfo=UTC))


def _event(number: int, fields: dict[str, object] | None = None) -> InfrastructureEvent:
    return InfrastructureEvent(
        event_id=EventId(UUID(f"10000000-0000-4000-8000-{number:012d}")),
        timestamp_utc=datetime(2026, 8, 10, 12, tzinfo=UTC),
        event_type="foundation.test_event",
        subsystem="foundation.diagnostics",
        severity=Severity.INFO,
        fields=fields or {"number": number},
    )


def test_sink_serializes_deterministically_and_redacts_before_persistence(tmp_path: Path) -> None:
    sink = InfrastructureDiagnosticSink(_state(tmp_path), _defaults(), _clock())
    written = sink.emit(
        _event(
            1,
            {
                "password": "synthetic-password",
                "message": "Authorization: Bearer synthetic-bearer",
            },
        )
    )
    sink.close()
    files = list(sink.directory.glob("*.jsonl"))
    assert len(files) == 1
    content = files[0].read_bytes()
    assert len(content) == written
    assert content.endswith(b"\n")
    assert b"synthetic-password" not in content
    assert b"synthetic-bearer" not in content
    decoded = json.loads(content)
    assert decoded["schema_version"] == 1
    assert decoded["timestamp_utc"] == "2026-08-10T12:00:00.000000Z"
    assert decoded["fields"]["password"] == "[REDACTED]"
    assert decoded["sanitization"]["redacted_values"] == 2
    assert files[0].stat().st_mode & 0o777 == 0o600


def test_rotation_happens_before_file_bound_is_exceeded(tmp_path: Path) -> None:
    sink = InfrastructureDiagnosticSink(_state(tmp_path), _defaults(file_bytes=600), _clock())
    sink.emit(_event(1, {"message": "a" * 180}))
    sink.emit(_event(2, {"message": "b" * 180}))
    sink.close()
    files = sorted(sink.directory.glob("*.jsonl"))
    assert len(files) == 2
    assert all(path.stat().st_size <= 600 for path in files)


def test_abandoned_open_file_is_truncated_validated_and_recovered(tmp_path: Path) -> None:
    state = _state(tmp_path)
    directory = state / "diagnostics"
    directory.mkdir(mode=0o700)
    abandoned = directory / "infrastructure-old.jsonl.open"
    abandoned.write_bytes(b'{"valid":true}\n{"partial"')
    abandoned.chmod(0o600)
    sink = InfrastructureDiagnosticSink(state, _defaults(), _clock())
    assert not abandoned.exists()
    recovered = list(directory.glob("*.recovered.jsonl"))
    assert len(recovered) == 1
    assert recovered[0].read_bytes() == b'{"valid":true}\n'
    sink.close()


def test_abandoned_hardlink_is_rejected_without_modifying_external_file(tmp_path: Path) -> None:
    state = _state(tmp_path)
    directory = state / "diagnostics"
    directory.mkdir(mode=0o700)
    victim = tmp_path / "external-private-file"
    original = b"external-content-without-newline"
    victim.write_bytes(original)
    victim.chmod(0o600)
    try:
        os.link(victim, directory / "attack.jsonl.open")
    except OSError as error:
        pytest.skip(f"hardlinks unavailable: {error}")
    with pytest.raises(DiagnosticError):
        InfrastructureDiagnosticSink(state, _defaults(), _clock())
    assert victim.read_bytes() == original


def test_active_path_replacement_is_rejected_without_modifying_external_file(
    tmp_path: Path,
) -> None:
    sink = InfrastructureDiagnosticSink(_state(tmp_path), _defaults(), _clock())
    sink.emit(_event(1))
    active = next(sink.directory.glob("*.open"))
    active.unlink()
    victim = tmp_path / "external-private-file"
    original = b"external-content"
    victim.write_bytes(original)
    victim.chmod(0o600)
    try:
        os.link(victim, active)
    except OSError as error:
        pytest.skip(f"hardlinks unavailable: {error}")
    with pytest.raises(DiagnosticError):
        sink.close()
    assert not sink.healthy
    assert victim.read_bytes() == original


def test_partial_write_restores_previous_offset_and_marks_sink_unhealthy(tmp_path: Path) -> None:
    def partial(descriptor: int, data: bytes) -> int:
        return os.write(descriptor, data[:-1])

    sink = InfrastructureDiagnosticSink(
        _state(tmp_path), _defaults(), _clock(), write_function=partial
    )
    with pytest.raises(DiagnosticError) as caught:
        sink.emit(_event(1))
    assert caught.value.code == "diagnostics.persistence_failed"
    assert not sink.healthy
    active = next(sink.directory.glob("*.open"))
    assert active.stat().st_size == 0
    with pytest.raises(DiagnosticError):
        sink.emit(_event(2))


def test_enospc_releases_reservation_and_marks_sink_unhealthy(tmp_path: Path) -> None:
    def no_space(_descriptor: int, _data: bytes) -> int:
        raise OSError(errno.ENOSPC, "synthetic ENOSPC")

    sink = InfrastructureDiagnosticSink(
        _state(tmp_path), _defaults(), _clock(), write_function=no_space
    )
    with pytest.raises(DiagnosticError) as caught:
        sink.emit(_event(1))
    assert caught.value.safe_details["reason"] == "storage_exhausted"
    assert sink.usage_bytes() == 0
    assert not sink.healthy


def test_event_and_total_capacity_fail_before_unbounded_persistence(tmp_path: Path) -> None:
    sink = InfrastructureDiagnosticSink(
        _state(tmp_path),
        _defaults(total_bytes=300, file_bytes=300, event_bytes=250),
        _clock(),
    )
    with pytest.raises(DiagnosticError) as event_error:
        sink.emit(_event(1, {"message": "x" * 500}))
    assert event_error.value.code == "diagnostics.invalid_event"
    with pytest.raises(StorageError):
        sink.ensure_evidence_capacity(301)
    sink.close()


def test_age_and_count_retention_remove_only_closed_files(tmp_path: Path) -> None:
    state = _state(tmp_path)
    directory = state / "diagnostics"
    directory.mkdir(mode=0o700)
    now = datetime(2026, 8, 10, 12, tzinfo=UTC)
    for index, age in enumerate((40, 3, 2, 1), start=1):
        path = directory / f"old-{index}.jsonl"
        path.write_text('{"ok":true}\n', encoding="utf-8")
        path.chmod(0o600)
        timestamp = (now - timedelta(days=age)).timestamp()
        os.utime(path, (timestamp, timestamp))
    active = directory / "active.jsonl.open"
    active.write_bytes(b"")
    active.chmod(0o600)
    sink = InfrastructureDiagnosticSink(state, _defaults(max_closed_files=2), FakeClock(now))
    assert active.exists() is False  # recovered, never pruned as an active write
    assert len(list(directory.glob("*.jsonl"))) == 2
    sink.close()
