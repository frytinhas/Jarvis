"""Bounded profile/model chat diagnostics that are nominally human-only."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from jarvis.chat.errors import ChatStorageError
from jarvis.chat.models import DiagnosticId, TurnSnapshot
from jarvis.config.defaults import ChatDefaults, DiagnosticDefaults
from jarvis.diagnostics.redaction import Redactor
from jarvis.foundation.clock import Clock, format_utc
from jarvis.foundation.errors import StorageError
from jarvis.models.models import ModelId
from jarvis.profiles.models import ProfileId
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.quota import QuotaAccountant, QuotaCategory, QuotaLimit, QuotaReservation

CHAT_DIAGNOSTICS_CATEGORY = QuotaCategory("chat_diagnostics")


@dataclass(frozen=True, slots=True)
class HumanDiagnosticItem:
    event_kind: str
    severity: str
    summary: str
    occurred_at_utc: str


@dataclass(frozen=True, slots=True)
class HumanDiagnosticSummary:
    """IPC-only view; deliberately not a ContextContribution or model-input source."""

    turn_id: str
    items: tuple[HumanDiagnosticItem, ...]
    truncated: bool

    def to_safe_mapping(self) -> dict[str, object]:
        return {
            "turn_id": self.turn_id,
            "items": [
                {
                    "event_kind": item.event_kind,
                    "severity": item.severity,
                    "summary": item.summary,
                    "occurred_at_utc": item.occurred_at_utc,
                }
                for item in self.items
            ],
            "truncated": self.truncated,
        }


class ChatDiagnosticReservation:
    def __init__(self, reservation: QuotaReservation) -> None:
        self._reservation = reservation

    def release(self) -> None:
        self._reservation.release()


class ChatDiagnosticService:
    def __init__(
        self,
        database_path: Path,
        chat_defaults: ChatDefaults,
        diagnostic_defaults: DiagnosticDefaults,
        clock: Clock,
    ) -> None:
        self._database_path = database_path
        self._defaults = chat_defaults
        self._clock = clock
        self._redactor = Redactor(
            max_text_bytes=min(
                diagnostic_defaults.text_bytes,
                chat_defaults.minimum_diagnostic_reservation_bytes // 4,
            ),
            max_depth=diagnostic_defaults.max_depth,
            max_container_entries=diagnostic_defaults.max_container_entries,
        )
        self._quotas: dict[tuple[ProfileId, ModelId], QuotaAccountant] = {}

    def reserve(self, profile_id: ProfileId, model_id: ModelId) -> ChatDiagnosticReservation:
        requested = self._defaults.minimum_diagnostic_reservation_bytes
        quota = self._quotas.setdefault(
            (profile_id, model_id),
            QuotaAccountant(
                [QuotaLimit(CHAT_DIAGNOSTICS_CATEGORY, self._defaults.max_diagnostic_bytes)]
            ),
        )
        used = self._usage(profile_id, model_id)
        try:
            quota.set_authoritative_usage(CHAT_DIAGNOSTICS_CATEGORY, used)
            reservation = quota.reserve(CHAT_DIAGNOSTICS_CATEGORY, requested)
        except StorageError:
            self._rotate(
                profile_id,
                model_id,
                max(requested, used + requested - self._defaults.max_diagnostic_bytes),
            )
            try:
                quota.set_authoritative_usage(
                    CHAT_DIAGNOSTICS_CATEGORY, self._usage(profile_id, model_id)
                )
                reservation = quota.reserve(CHAT_DIAGNOSTICS_CATEGORY, requested)
            except StorageError as error:
                raise ChatStorageError("diagnostic_reservation_failed") from error
        return ChatDiagnosticReservation(reservation)

    def emit(
        self,
        turn: TurnSnapshot,
        event_kind: str,
        summary: str,
        *,
        severity: str = "info",
        closed: bool = False,
    ) -> None:
        sanitized = self._redactor.redact_text(summary).value
        assert isinstance(sanitized, str)
        timestamp = format_utc(self._clock.now())
        size = len(sanitized.encode("utf-8")) + 256
        try:
            with (
                SQLiteDatabase(self._database_path) as database,
                database.transaction(immediate=True),
            ):
                database.connection().execute(
                    """INSERT INTO chat_diagnostics
                       (diagnostic_id, profile_id, model_id, session_id, request_id, turn_id,
                        event_kind, severity, summary, size_bytes, closed, reserved,
                        occurred_at_utc, closed_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                    (
                        str(DiagnosticId.new()),
                        str(turn.profile_id),
                        str(turn.model_id),
                        str(turn.session_id),
                        turn.request_id,
                        str(turn.turn_id),
                        event_kind,
                        severity,
                        sanitized,
                        size,
                        int(closed),
                        timestamp,
                        timestamp if closed else None,
                    ),
                )
                if closed:
                    database.connection().execute(
                        """UPDATE chat_diagnostics SET closed = 1, closed_at_utc = ?
                           WHERE profile_id = ? AND model_id = ? AND turn_id = ?""",
                        (
                            timestamp,
                            str(turn.profile_id),
                            str(turn.model_id),
                            str(turn.turn_id),
                        ),
                    )
        except (sqlite3.Error, StorageError) as error:
            raise ChatStorageError("diagnostic_write_failed") from error

    def summary(self, turn: TurnSnapshot, *, maximum_items: int = 32) -> HumanDiagnosticSummary:
        maximum_items = max(1, min(maximum_items, 64))
        with SQLiteDatabase(self._database_path) as database:
            rows = (
                database.connection()
                .execute(
                    """SELECT event_kind, severity, summary, occurred_at_utc
                   FROM chat_diagnostics
                   WHERE profile_id = ? AND model_id = ? AND session_id = ? AND turn_id = ?
                   ORDER BY occurred_at_utc, diagnostic_id LIMIT ?""",
                    (
                        str(turn.profile_id),
                        str(turn.model_id),
                        str(turn.session_id),
                        str(turn.turn_id),
                        maximum_items + 1,
                    ),
                )
                .fetchall()
            )
        return HumanDiagnosticSummary(
            str(turn.turn_id),
            tuple(
                HumanDiagnosticItem(*(str(value) for value in row)) for row in rows[:maximum_items]
            ),
            len(rows) > maximum_items,
        )

    def _usage(self, profile_id: ProfileId, model_id: ModelId) -> int:
        try:
            with SQLiteDatabase(self._database_path) as database:
                return int(
                    database.connection()
                    .execute(
                        """SELECT COALESCE(SUM(size_bytes),0) FROM chat_diagnostics
                           WHERE profile_id = ? AND model_id = ?""",
                        (str(profile_id), str(model_id)),
                    )
                    .fetchone()[0]
                )
        except (sqlite3.Error, StorageError) as error:
            raise ChatStorageError("diagnostic_accounting_failed") from error

    def _rotate(self, profile_id: ProfileId, model_id: ModelId, required_bytes: int) -> None:
        freed = 0
        with SQLiteDatabase(self._database_path) as database, database.transaction(immediate=True):
            connection = database.connection()
            rows = connection.execute(
                """SELECT diagnostic_id, size_bytes FROM chat_diagnostics
                   WHERE profile_id = ? AND model_id = ? AND closed = 1 AND reserved = 0
                   ORDER BY closed_at_utc, diagnostic_id""",
                (str(profile_id), str(model_id)),
            ).fetchall()
            for diagnostic_id, size_bytes in rows:
                connection.execute(
                    """DELETE FROM chat_diagnostics
                       WHERE diagnostic_id = ? AND closed = 1 AND reserved = 0""",
                    (diagnostic_id,),
                )
                freed += int(size_bytes)
                if freed >= required_bytes:
                    break
