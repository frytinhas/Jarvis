"""UTC clock abstractions used by persistent foundation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol


def normalize_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC and reject ambiguous naive values."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC)


def format_utc(value: datetime) -> str:
    """Format an aware time as fixed RFC 3339 UTC with microseconds."""

    return normalize_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


class Clock(Protocol):
    """Source of timezone-aware UTC time."""

    def now(self) -> datetime:
        """Return the current instant normalized to UTC."""


class SystemClock:
    """Production wall clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass
class FakeClock:
    """Deterministic manually advanced clock for tests."""

    _current: datetime

    def __post_init__(self) -> None:
        self._current = normalize_utc(self._current)

    def now(self) -> datetime:
        return self._current

    def advance(self, delta: timedelta) -> datetime:
        if delta.total_seconds() < 0:
            raise ValueError("fake clock cannot move backwards")
        self._current += delta
        return self._current
