"""Typed runtime state and safe public snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import RFC_4122, UUID, uuid4

from jarvis.models.models import ModelId


class RuntimeId:
    def __init__(self, value: UUID) -> None:
        if value.version != 4 or value.variant != RFC_4122:
            raise ValueError("runtime ID must be an RFC 4122 version-4 UUID")
        self.value = value

    @classmethod
    def new(cls) -> RuntimeId:
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> RuntimeId:
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError("runtime ID must use canonical lowercase UUID text")
        return cls(parsed)

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, RuntimeId) and self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)


class RuntimeState(StrEnum):
    STARTING = "STARTING"
    READY = "READY"
    BUSY = "BUSY"
    ERROR = "ERROR"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


class RuntimeHealthClass(StrEnum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


class RuntimeEventKind(StrEnum):
    START_REQUESTED = "start_requested"
    READY = "ready"
    BUSY = "busy"
    HEALTH_CHECKED = "health_checked"
    STOP_REQUESTED = "stop_requested"
    STOPPED = "stopped"
    ERROR = "error"
    RECOVERED = "recovered"
    SWITCH_REQUESTED = "switch_requested"
    QUIESCED = "quiesced"


_ALLOWED_TRANSITIONS: dict[RuntimeState | None, frozenset[RuntimeState]] = {
    None: frozenset({RuntimeState.STARTING}),
    RuntimeState.STARTING: frozenset(
        {RuntimeState.READY, RuntimeState.STOPPING, RuntimeState.ERROR}
    ),
    RuntimeState.READY: frozenset({RuntimeState.BUSY, RuntimeState.STOPPING, RuntimeState.ERROR}),
    RuntimeState.BUSY: frozenset({RuntimeState.READY, RuntimeState.STOPPING, RuntimeState.ERROR}),
    RuntimeState.STOPPING: frozenset({RuntimeState.STOPPED, RuntimeState.ERROR}),
    RuntimeState.STOPPED: frozenset({RuntimeState.STARTING}),
    RuntimeState.ERROR: frozenset({RuntimeState.STARTING, RuntimeState.STOPPING}),
}


def is_legal_transition(previous: RuntimeState | None, current: RuntimeState) -> bool:
    return current in _ALLOWED_TRANSITIONS[previous]


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    runtime_id: RuntimeId | None
    model_id: ModelId | None
    state: RuntimeState
    health: RuntimeHealthClass
    started_at_utc: str | None = None
    ready_at_utc: str | None = None
    stopped_at_utc: str | None = None

    def to_safe_mapping(self) -> dict[str, object]:
        return {
            "runtime_id": None if self.runtime_id is None else str(self.runtime_id),
            "model_id": None if self.model_id is None else str(self.model_id),
            "state": self.state.value,
            "health": self.health.value,
            "started_at_utc": self.started_at_utc,
            "ready_at_utc": self.ready_at_utc,
            "stopped_at_utc": self.stopped_at_utc,
        }


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    max_concurrent_runtimes: int
    revision: int
    updated_at_utc: str

    def __post_init__(self) -> None:
        if not 1 <= self.max_concurrent_runtimes <= 16 or self.revision <= 0:
            raise ValueError("invalid runtime policy")
