"""Thread-safe generic byte quotas and pre-write reservations."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from jarvis.foundation.clock import normalize_utc
from jarvis.foundation.errors import StorageError

MAX_ACCOUNTED_BYTES = (1 << 63) - 1
_CATEGORY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _bytes(value: int, *, allow_zero: bool = True) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("byte values must be integers")
    minimum = 0 if allow_zero else 1
    if value < minimum or value > MAX_ACCOUNTED_BYTES:
        raise ValueError("byte value is outside the supported range")
    return value


@dataclass(frozen=True, slots=True, order=True)
class QuotaCategory:
    value: str

    def __post_init__(self) -> None:
        if _CATEGORY_PATTERN.fullmatch(self.value) is None:
            raise ValueError("quota category must be a stable lowercase identifier")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class QuotaLimit:
    category: QuotaCategory
    maximum_bytes: int

    def __post_init__(self) -> None:
        _bytes(self.maximum_bytes, allow_zero=False)


@dataclass(frozen=True, slots=True)
class QuotaSnapshot:
    category: QuotaCategory
    maximum_bytes: int
    used_bytes: int
    reserved_bytes: int

    @property
    def available_bytes(self) -> int:
        return self.maximum_bytes - self.used_bytes - self.reserved_bytes


class ReservationState(StrEnum):
    PENDING = "pending"
    COMMITTED = "committed"
    RELEASED = "released"


@dataclass(frozen=True, slots=True)
class RotationRecord:
    stable_record_id: str
    size_bytes: int
    closed_at_utc: datetime | None
    active: bool = False
    reserved: bool = False

    def __post_init__(self) -> None:
        if not self.stable_record_id:
            raise ValueError("stable_record_id must not be empty")
        _bytes(self.size_bytes)
        if self.closed_at_utc is not None:
            object.__setattr__(self, "closed_at_utc", normalize_utc(self.closed_at_utc))


def rotation_eligible(records: Iterable[RotationRecord]) -> tuple[RotationRecord, ...]:
    """Return only closed inactive/unreserved records in deterministic oldest-first order."""

    eligible = (
        record
        for record in records
        if record.closed_at_utc is not None and not record.active and not record.reserved
    )
    return tuple(sorted(eligible, key=lambda item: (item.closed_at_utc, item.stable_record_id)))


@dataclass
class _Account:
    maximum_bytes: int
    used_bytes: int = 0
    reserved_bytes: int = 0


class QuotaAccountant:
    """Linearizable in-process accounting with one optional reconciliation attempt."""

    def __init__(self, limits: Iterable[QuotaLimit] = ()) -> None:
        self._lock = threading.RLock()
        self._accounts: dict[QuotaCategory, _Account] = {}
        self._reservations: dict[int, tuple[QuotaCategory, int]] = {}
        self._next_reservation_id = 1
        for limit in limits:
            self.register(limit)

    def register(self, limit: QuotaLimit) -> None:
        with self._lock:
            if limit.category in self._accounts:
                raise ValueError(f"quota category already registered: {limit.category}")
            self._accounts[limit.category] = _Account(limit.maximum_bytes)

    def set_authoritative_usage(self, category: QuotaCategory, used_bytes: int) -> None:
        used = _bytes(used_bytes)
        with self._lock:
            account = self._account(category)
            if used + account.reserved_bytes > account.maximum_bytes:
                raise StorageError(
                    code="storage.limit_exceeded",
                    message_key="error.storage.limit_exceeded",
                    safe_details={"category": str(category)},
                )
            account.used_bytes = used

    def snapshot(self, category: QuotaCategory) -> QuotaSnapshot:
        with self._lock:
            account = self._account(category)
            return QuotaSnapshot(
                category,
                account.maximum_bytes,
                account.used_bytes,
                account.reserved_bytes,
            )

    def reserve(
        self,
        category: QuotaCategory,
        requested_bytes: int,
        *,
        reconcile: Callable[[], int] | None = None,
    ) -> QuotaReservation:
        requested = _bytes(requested_bytes, allow_zero=False)
        with self._lock:
            account = self._account(category)
            if not self._has_capacity(account, requested) and reconcile is not None:
                authoritative = _bytes(reconcile())
                if authoritative + account.reserved_bytes <= account.maximum_bytes:
                    account.used_bytes = authoritative
            if not self._has_capacity(account, requested):
                raise StorageError(
                    code="storage.limit_exceeded",
                    message_key="error.storage.limit_exceeded",
                    safe_details={"category": str(category), "requested_bytes": requested},
                )
            reservation_id = self._next_reservation_id
            self._next_reservation_id += 1
            account.reserved_bytes += requested
            self._reservations[reservation_id] = (category, requested)
            return QuotaReservation(self, reservation_id, category, requested)

    @staticmethod
    def _has_capacity(account: _Account, requested: int) -> bool:
        return requested <= account.maximum_bytes - account.used_bytes - account.reserved_bytes

    def _account(self, category: QuotaCategory) -> _Account:
        try:
            return self._accounts[category]
        except KeyError as error:
            raise StorageError(
                code="storage.io_failed",
                message_key="error.storage.unknown_quota_category",
                safe_details={"category": str(category)},
            ) from error

    def _commit(self, reservation_id: int, actual_bytes: int) -> None:
        actual = _bytes(actual_bytes)
        with self._lock:
            category, reserved = self._pending(reservation_id)
            if actual > reserved:
                raise StorageError(
                    code="storage.limit_exceeded",
                    message_key="error.storage.additional_reservation_required",
                    safe_details={"category": str(category)},
                )
            account = self._account(category)
            if account.used_bytes > MAX_ACCOUNTED_BYTES - actual:
                raise StorageError(
                    code="storage.limit_exceeded",
                    message_key="error.storage.accounting_overflow",
                )
            account.reserved_bytes -= reserved
            account.used_bytes += actual
            del self._reservations[reservation_id]

    def _release(self, reservation_id: int) -> None:
        with self._lock:
            category, reserved = self._pending(reservation_id)
            account = self._account(category)
            account.reserved_bytes -= reserved
            del self._reservations[reservation_id]

    def _pending(self, reservation_id: int) -> tuple[QuotaCategory, int]:
        try:
            return self._reservations[reservation_id]
        except KeyError as error:
            raise StorageError(
                code="storage.io_failed",
                message_key="error.storage.invalid_reservation_state",
            ) from error


class QuotaReservation:
    """Single-use capacity claim returned by a QuotaAccountant."""

    def __init__(
        self,
        accountant: QuotaAccountant,
        reservation_id: int,
        category: QuotaCategory,
        reserved_bytes: int,
    ) -> None:
        self._accountant = accountant
        self._reservation_id = reservation_id
        self.category = category
        self.reserved_bytes = reserved_bytes
        self.state = ReservationState.PENDING
        self.committed_bytes: int | None = None

    def commit(self, actual_bytes: int) -> None:
        if self.state is not ReservationState.PENDING:
            raise StorageError(
                code="storage.io_failed",
                message_key="error.storage.invalid_reservation_state",
                safe_details={"state": self.state.value},
            )
        self._accountant._commit(self._reservation_id, actual_bytes)
        self.committed_bytes = actual_bytes
        self.state = ReservationState.COMMITTED

    def release(self) -> None:
        if self.state is ReservationState.RELEASED:
            return
        if self.state is not ReservationState.PENDING:
            raise StorageError(
                code="storage.io_failed",
                message_key="error.storage.invalid_reservation_state",
                safe_details={"state": self.state.value},
            )
        self._accountant._release(self._reservation_id)
        self.state = ReservationState.RELEASED
