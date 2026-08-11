"""Opaque correlation identifiers and injectable generators."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class EventId:
    value: UUID

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class CorrelationId:
    value: UUID

    def __str__(self) -> str:
        return str(self.value)


class IdGenerator(Protocol):
    """Generates opaque version-4 identifiers."""

    def new_event_id(self) -> EventId:
        """Return a new event identifier."""

    def new_correlation_id(self) -> CorrelationId:
        """Return a new correlation identifier."""


class RandomIdGenerator:
    """Standard-library UUID4 generator."""

    def new_event_id(self) -> EventId:
        return EventId(uuid4())

    def new_correlation_id(self) -> CorrelationId:
        return CorrelationId(uuid4())


class DeterministicIdGenerator:
    """Consumes a supplied UUID sequence for deterministic tests."""

    def __init__(self, values: Iterable[UUID]) -> None:
        self._values = deque(values)

    def _next(self) -> UUID:
        try:
            return self._values.popleft()
        except IndexError as error:
            raise RuntimeError("deterministic identifier sequence exhausted") from error

    def new_event_id(self) -> EventId:
        return EventId(self._next())

    def new_correlation_id(self) -> CorrelationId:
        return CorrelationId(self._next())
