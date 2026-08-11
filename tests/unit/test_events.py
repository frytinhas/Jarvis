from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from jarvis.diagnostics.events import InfrastructureEvent, Severity
from jarvis.foundation.errors import DiagnosticError
from jarvis.foundation.identifiers import EventId

pytestmark = pytest.mark.unit


def _event(**changes: object) -> InfrastructureEvent:
    values: dict[str, object] = {
        "event_id": EventId(UUID("10000000-0000-4000-8000-000000000001")),
        "timestamp_utc": datetime(2026, 8, 10, 12, tzinfo=UTC),
        "event_type": "foundation.initialized",
        "subsystem": "foundation.bootstrap",
        "severity": Severity.INFO,
        "fields": {"ok": True},
    }
    values.update(changes)
    return InfrastructureEvent(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["Upper.case", "missing-dot-grammar", ".leading", "trailing."])
def test_event_names_are_stable_dotted_lowercase(name: str) -> None:
    with pytest.raises(DiagnosticError):
        _event(event_type=name)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), b"bytes", object()])
def test_event_fields_accept_only_finite_json_values(value: object) -> None:
    with pytest.raises(DiagnosticError) as caught:
        _event(fields={"value": value})
    assert caught.value.code == "diagnostics.invalid_event"


def test_non_string_keys_and_cycles_are_rejected() -> None:
    with pytest.raises(DiagnosticError):
        _event(fields={1: "value"})
    cyclic: list[object] = []
    cyclic.append(cyclic)
    with pytest.raises(DiagnosticError):
        _event(fields={"value": cyclic})


def test_event_timestamp_is_normalized_to_utc() -> None:
    event = _event()
    assert event.timestamp_utc.tzinfo is UTC


def test_excessive_nesting_is_a_typed_bounded_error() -> None:
    nested: object = 0
    for _ in range(100):
        nested = [nested]
    with pytest.raises(DiagnosticError) as caught:
        _event(fields={"nested": nested})
    assert caught.value.code == "diagnostics.invalid_event"
