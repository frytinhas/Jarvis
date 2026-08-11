from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from jarvis.foundation.clock import FakeClock, SystemClock, format_utc, normalize_utc
from jarvis.foundation.identifiers import DeterministicIdGenerator, RandomIdGenerator

pytestmark = pytest.mark.unit


def test_format_utc_is_fixed_rfc3339_with_microseconds() -> None:
    source = datetime(2026, 8, 10, 9, 30, 4, 12, tzinfo=timezone(timedelta(hours=-3)))
    assert format_utc(source) == "2026-08-10T12:30:04.000012Z"


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        normalize_utc(datetime(2026, 8, 10))


def test_fake_clock_normalizes_and_advances_monotonically() -> None:
    clock = FakeClock(datetime(2026, 8, 10, 9, tzinfo=timezone(timedelta(hours=-3))))
    assert clock.now() == datetime(2026, 8, 10, 12, tzinfo=UTC)
    assert clock.advance(timedelta(seconds=2)) == datetime(2026, 8, 10, 12, 0, 2, tzinfo=UTC)
    with pytest.raises(ValueError, match="backwards"):
        clock.advance(timedelta(microseconds=-1))


def test_system_clock_returns_aware_utc() -> None:
    current = SystemClock().now()
    assert current.tzinfo is UTC


def test_deterministic_ids_preserve_type_and_order() -> None:
    values = [
        UUID("10000000-0000-4000-8000-000000000001"),
        UUID("20000000-0000-4000-8000-000000000002"),
    ]
    generator = DeterministicIdGenerator(values)
    assert generator.new_event_id().value == values[0]
    assert generator.new_correlation_id().value == values[1]
    with pytest.raises(RuntimeError, match="exhausted"):
        generator.new_event_id()


def test_random_ids_are_uuid4_and_distinct() -> None:
    generator = RandomIdGenerator()
    first = generator.new_event_id()
    second = generator.new_event_id()
    assert first.value.version == 4
    assert second.value.version == 4
    assert first != second
