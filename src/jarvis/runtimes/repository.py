"""Metadata-only SQLite persistence for runtime lifecycle evidence."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from jarvis.foundation.clock import format_utc
from jarvis.models.models import ModelId
from jarvis.profiles.models import ProfileId
from jarvis.runtimes.errors import RuntimePolicyConflictError
from jarvis.runtimes.models import RuntimeEventKind, RuntimeId, RuntimePolicy, RuntimeState


class RuntimeRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def policy(self, default_capacity: int, now: datetime) -> RuntimePolicy:
        self._connection.execute(
            """INSERT OR IGNORE INTO installation_runtime_policy
               (singleton, max_concurrent_runtimes, revision, updated_at_utc)
               VALUES (1, ?, 1, ?)""",
            (default_capacity, format_utc(now)),
        )
        row = self._connection.execute(
            "SELECT max_concurrent_runtimes, revision, updated_at_utc "
            "FROM installation_runtime_policy WHERE singleton = 1"
        ).fetchone()
        assert row is not None
        return RuntimePolicy(int(row[0]), int(row[1]), str(row[2]))

    def update_policy(self, capacity: int, expected_revision: int, now: datetime) -> RuntimePolicy:
        if not 1 <= capacity <= 16:
            raise ValueError("capacity must be between 1 and 16")
        cursor = self._connection.execute(
            """UPDATE installation_runtime_policy
               SET max_concurrent_runtimes = ?, revision = revision + 1, updated_at_utc = ?
               WHERE singleton = 1 AND revision = ?""",
            (capacity, format_utc(now), expected_revision),
        )
        if cursor.rowcount != 1:
            raise RuntimePolicyConflictError()
        return self.policy(capacity, now)

    def add_event(
        self,
        *,
        event_id: str,
        profile_id: ProfileId,
        model_id: ModelId,
        runtime_id: RuntimeId,
        state: RuntimeState,
        event_kind: RuntimeEventKind,
        reason_class: str | None,
        occurred_at: datetime,
        retention_count: int,
    ) -> None:
        self._connection.execute(
            """INSERT INTO runtime_events
               (event_id, profile_id, model_id, runtime_id, state, event_kind,
                reason_class, occurred_at_utc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                str(profile_id),
                str(model_id),
                str(runtime_id),
                state.value,
                event_kind.value,
                reason_class,
                format_utc(occurred_at),
            ),
        )
        self._connection.execute(
            """DELETE FROM runtime_events WHERE event_id IN (
                   SELECT event_id FROM runtime_events WHERE profile_id = ?
                   ORDER BY occurred_at_utc DESC, event_id DESC LIMIT -1 OFFSET ?
               )""",
            (str(profile_id), retention_count),
        )

    def set_last_valid(
        self,
        *,
        profile_id: ProfileId,
        model_id: ModelId,
        profile_model_revision: int,
        runtime_id: RuntimeId,
        ready_at: datetime,
    ) -> None:
        self._connection.execute(
            """INSERT INTO profile_runtime_last_valid
               (profile_id, model_id, profile_model_revision, runtime_id, ready_at_utc)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(profile_id) DO UPDATE SET model_id = excluded.model_id,
                 profile_model_revision = excluded.profile_model_revision,
                 runtime_id = excluded.runtime_id, ready_at_utc = excluded.ready_at_utc""",
            (
                str(profile_id),
                str(model_id),
                profile_model_revision,
                str(runtime_id),
                format_utc(ready_at),
            ),
        )

    def clear_profile(self, profile_id: ProfileId) -> None:
        self._connection.execute(
            "DELETE FROM runtime_events WHERE profile_id = ?", (str(profile_id),)
        )
        self._connection.execute(
            "DELETE FROM profile_runtime_last_valid WHERE profile_id = ?", (str(profile_id),)
        )
