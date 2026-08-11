"""Typed version-1 infrastructure diagnostic events."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from jarvis.foundation.clock import normalize_utc
from jarvis.foundation.errors import DiagnosticError
from jarvis.foundation.identifiers import CorrelationId, EventId

EVENT_SCHEMA_VERSION = 1
_DOTTED_NAME = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_MAX_VALIDATION_DEPTH = 64
_MAX_VALIDATION_VALUES = 10_000


class Severity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


def _validate_json_value(
    value: object,
    active_containers: set[int],
    *,
    depth: int = 0,
    visited: list[int] | None = None,
) -> None:
    counter = [0] if visited is None else visited
    counter[0] += 1
    if counter[0] > _MAX_VALIDATION_VALUES or depth > _MAX_VALIDATION_DEPTH:
        raise DiagnosticError(
            code="diagnostics.invalid_event",
            message_key="error.diagnostics.value_too_complex",
        )
    if value is None or isinstance(value, str | bool | int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DiagnosticError(
                code="diagnostics.invalid_event",
                message_key="error.diagnostics.nonfinite_value",
            )
        return
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in active_containers:
            raise DiagnosticError(
                code="diagnostics.invalid_event",
                message_key="error.diagnostics.cyclic_value",
            )
        active_containers.add(identity)
        try:
            for key, child in value.items():
                if not isinstance(key, str):
                    raise DiagnosticError(
                        code="diagnostics.invalid_event",
                        message_key="error.diagnostics.non_string_key",
                    )
                _validate_json_value(child, active_containers, depth=depth + 1, visited=counter)
        finally:
            active_containers.remove(identity)
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray | memoryview):
        identity = id(value)
        if identity in active_containers:
            raise DiagnosticError(
                code="diagnostics.invalid_event",
                message_key="error.diagnostics.cyclic_value",
            )
        active_containers.add(identity)
        try:
            for child in value:
                _validate_json_value(child, active_containers, depth=depth + 1, visited=counter)
        finally:
            active_containers.remove(identity)
        return
    raise DiagnosticError(
        code="diagnostics.invalid_event",
        message_key="error.diagnostics.non_json_value",
    )


@dataclass(frozen=True, slots=True)
class InfrastructureEvent:
    event_id: EventId
    timestamp_utc: datetime
    event_type: str
    subsystem: str
    severity: Severity
    fields: Mapping[str, object]
    correlation_id: CorrelationId | None = None
    schema_version: int = EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EVENT_SCHEMA_VERSION:
            raise DiagnosticError(
                code="diagnostics.invalid_event",
                message_key="error.diagnostics.unsupported_schema",
            )
        object.__setattr__(self, "timestamp_utc", normalize_utc(self.timestamp_utc))
        for value, field_name in (
            (self.event_type, "event_type"),
            (self.subsystem, "subsystem"),
        ):
            if _DOTTED_NAME.fullmatch(value) is None:
                raise DiagnosticError(
                    code="diagnostics.invalid_event",
                    message_key="error.diagnostics.invalid_name",
                    safe_details={"field": field_name},
                )
        _validate_json_value(self.fields, set())
