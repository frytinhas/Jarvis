from __future__ import annotations

import errno
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from jarvis.config.defaults import DiagnosticDefaults
from jarvis.diagnostics.events import InfrastructureEvent, Severity
from jarvis.diagnostics.sink import FOUNDATION_DIAGNOSTICS, InfrastructureDiagnosticSink
from jarvis.foundation.clock import FakeClock
from jarvis.foundation.errors import DiagnosticError, StorageError
from jarvis.foundation.identifiers import EventId
from jarvis.storage.quota import QuotaAccountant, QuotaLimit

pytestmark = pytest.mark.security


def _defaults() -> DiagnosticDefaults:
    return DiagnosticDefaults(2048, 1024, 768, 256, 4, 8, 4, 30)


def _sink(tmp_path: Path, writer: object) -> InfrastructureDiagnosticSink:
    state = tmp_path / "state-app"
    state.mkdir(mode=0o700)
    return InfrastructureDiagnosticSink(
        state,
        _defaults(),
        FakeClock(datetime(2026, 8, 10, tzinfo=UTC)),
        write_function=writer,  # type: ignore[arg-type]
    )


def _event() -> InfrastructureEvent:
    return InfrastructureEvent(
        EventId(UUID("10000000-0000-4000-8000-000000000001")),
        datetime(2026, 8, 10, tzinfo=UTC),
        "foundation.storage_failure",
        "foundation.diagnostics",
        Severity.ERROR,
        {"password": "synthetic-password"},
    )


@pytest.mark.parametrize("failure", ["partial", "enospc"])
def test_failed_diagnostic_append_never_commits_or_leaks_secret(
    tmp_path: Path, failure: str
) -> None:
    def writer(descriptor: int, payload: bytes) -> int:
        if failure == "enospc":
            raise OSError(errno.ENOSPC, "synthetic")
        return os.write(descriptor, payload[:-1])

    sink = _sink(tmp_path, writer)
    with pytest.raises(DiagnosticError):
        sink.emit(_event())
    sink.abandon()
    assert sink.usage_bytes() == 0
    persisted = b"".join(path.read_bytes() for path in sink.directory.iterdir())
    assert b"synthetic-password" not in persisted


def test_concurrent_quota_claims_cannot_over_reserve() -> None:
    accountant = QuotaAccountant((QuotaLimit(FOUNDATION_DIAGNOSTICS, 100),))
    barrier = threading.Barrier(8)
    outcomes: list[str] = []

    def reserve() -> None:
        barrier.wait()
        try:
            accountant.reserve(FOUNDATION_DIAGNOSTICS, 30)
            outcomes.append("reserved")
        except StorageError:
            outcomes.append("denied")

    threads = [threading.Thread(target=reserve) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert outcomes.count("reserved") == 3
    assert outcomes.count("denied") == 5
    assert accountant.snapshot(FOUNDATION_DIAGNOSTICS).reserved_bytes == 90
