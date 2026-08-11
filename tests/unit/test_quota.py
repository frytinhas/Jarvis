from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest

from jarvis.foundation.errors import StorageError
from jarvis.storage.quota import (
    MAX_ACCOUNTED_BYTES,
    QuotaAccountant,
    QuotaCategory,
    QuotaLimit,
    ReservationState,
    RotationRecord,
    rotation_eligible,
)

pytestmark = pytest.mark.unit
DIAGNOSTICS = QuotaCategory("foundation_diagnostics")


def _accountant(limit: int = 100) -> QuotaAccountant:
    return QuotaAccountant((QuotaLimit(DIAGNOSTICS, limit),))


def test_exact_boundary_commit_and_unused_capacity_release() -> None:
    accountant = _accountant()
    reservation = accountant.reserve(DIAGNOSTICS, 100)
    assert accountant.snapshot(DIAGNOSTICS).available_bytes == 0
    reservation.commit(60)
    snapshot = accountant.snapshot(DIAGNOSTICS)
    assert reservation.state is ReservationState.COMMITTED
    assert snapshot.used_bytes == 60
    assert snapshot.reserved_bytes == 0
    assert snapshot.available_bytes == 40


def test_exhaustion_and_unknown_category_are_typed() -> None:
    accountant = _accountant()
    accountant.reserve(DIAGNOSTICS, 80)
    with pytest.raises(StorageError) as exhausted:
        accountant.reserve(DIAGNOSTICS, 21)
    assert exhausted.value.code == "storage.limit_exceeded"
    with pytest.raises(StorageError) as unknown:
        accountant.snapshot(QuotaCategory("future_writer"))
    assert unknown.value.code == "storage.io_failed"


def test_release_is_idempotent_but_other_terminal_transitions_fail() -> None:
    accountant = _accountant()
    released = accountant.reserve(DIAGNOSTICS, 50)
    released.release()
    released.release()
    assert accountant.snapshot(DIAGNOSTICS).available_bytes == 100
    with pytest.raises(StorageError):
        released.commit(1)

    committed = accountant.reserve(DIAGNOSTICS, 50)
    committed.commit(10)
    with pytest.raises(StorageError):
        committed.commit(10)
    with pytest.raises(StorageError):
        committed.release()


def test_over_commit_requires_another_reservation_and_remains_pending() -> None:
    accountant = _accountant()
    reservation = accountant.reserve(DIAGNOSTICS, 20)
    with pytest.raises(StorageError) as caught:
        reservation.commit(21)
    assert caught.value.code == "storage.limit_exceeded"
    assert reservation.state is ReservationState.PENDING
    assert accountant.snapshot(DIAGNOSTICS).reserved_bytes == 20
    reservation.release()


def test_one_reconciliation_attempt_can_restore_authoritative_capacity() -> None:
    accountant = _accountant()
    accountant.set_authoritative_usage(DIAGNOSTICS, 90)
    calls = 0

    def reconcile() -> int:
        nonlocal calls
        calls += 1
        return 20

    reservation = accountant.reserve(DIAGNOSTICS, 50, reconcile=reconcile)
    assert calls == 1
    reservation.commit(50)
    assert accountant.snapshot(DIAGNOSTICS).used_bytes == 70


def test_rotation_eligibility_excludes_active_open_and_reserved_records() -> None:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    records = [
        RotationRecord("b", 1, now - timedelta(days=2)),
        RotationRecord("a", 1, now - timedelta(days=2)),
        RotationRecord("open", 1, None),
        RotationRecord("active", 1, now - timedelta(days=3), active=True),
        RotationRecord("reserved", 1, now - timedelta(days=4), reserved=True),
    ]
    assert [item.stable_record_id for item in rotation_eligible(records)] == ["a", "b"]


@pytest.mark.parametrize("value", [-1, MAX_ACCOUNTED_BYTES + 1, True, 1.5])
def test_invalid_accounting_values_are_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        QuotaLimit(DIAGNOSTICS, value)  # type: ignore[arg-type]


def test_concurrent_reservations_are_linearizable() -> None:
    accountant = _accountant()
    barrier = threading.Barrier(2)
    successes: list[object] = []
    failures: list[StorageError] = []

    def reserve() -> None:
        barrier.wait()
        try:
            successes.append(accountant.reserve(DIAGNOSTICS, 60))
        except StorageError as error:
            failures.append(error)

    threads = [threading.Thread(target=reserve) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].code == "storage.limit_exceeded"
    assert accountant.snapshot(DIAGNOSTICS).reserved_bytes == 60


def test_category_is_extensible_without_a_closed_enum() -> None:
    future = QuotaCategory("future_writer_owned_category")
    accountant = QuotaAccountant((QuotaLimit(future, 1),))
    accountant.reserve(future, 1).commit(1)
    assert accountant.snapshot(future).used_bytes == 1
