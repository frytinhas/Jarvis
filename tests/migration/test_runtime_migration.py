from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.foundation.clock import FakeClock
from jarvis.models.models import ModelId
from jarvis.profiles.models import ProfileId
from jarvis.runtimes.errors import RuntimePolicyConflictError
from jarvis.runtimes.models import RuntimeEventKind, RuntimeId, RuntimeState
from jarvis.runtimes.repository import RuntimeRepository
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import (
    MigrationRunner,
    current_schema_version,
    load_packaged_migrations,
)

pytestmark = pytest.mark.migration


def _clock() -> FakeClock:
    return FakeClock(datetime(2026, 8, 21, 12, tzinfo=UTC))


def _database(tmp_path: Path) -> SQLiteDatabase:
    root = tmp_path / "data"
    root.mkdir(mode=0o700)
    return SQLiteDatabase((root / "jarvis.sqlite3").absolute())


def _seed(connection: sqlite3.Connection) -> tuple[ProfileId, ModelId]:
    profile_id = ProfileId(uuid4())
    model_id = ModelId.new()
    timestamp = "2026-08-21T12:00:00.000000Z"
    connection.execute(
        "INSERT INTO profiles VALUES (?, 'standard', 'Test', 1, ?, ?)",
        (str(profile_id), timestamp, timestamp),
    )
    connection.execute(
        "INSERT INTO models VALUES (?, ?, 1, 2, 10, 3, '{}', 'available', NULL, ?)",
        (str(model_id), "a" * 64, timestamp),
    )
    return profile_id, model_id


def test_schema_three_upgrades_to_four_without_runtime_side_effect(tmp_path: Path) -> None:
    migrations = load_packaged_migrations()
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock(), migrations[:3]).apply()
        assert current_schema_version(database) == 3
        result = MigrationRunner(database, _clock(), migrations[:4]).apply()
        assert result.applied_versions == (4,)
        assert current_schema_version(database) == 4
        connection = database.connection()
        assert connection.execute("SELECT COUNT(*) FROM runtime_events").fetchone()[0] == 0
        assert (
            connection.execute("SELECT COUNT(*) FROM profile_runtime_last_valid").fetchone()[0] == 0
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM installation_runtime_policy").fetchone()[0]
            == 0
        )


def test_policy_lazy_seed_revision_conflict_and_capacity_constraints(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        with database.transaction(immediate=True):
            repository = RuntimeRepository(database.connection())
            initial = repository.policy(2, _clock().now())
            assert (initial.max_concurrent_runtimes, initial.revision) == (2, 1)
            changed = repository.update_policy(4, 1, _clock().now())
            assert (changed.max_concurrent_runtimes, changed.revision) == (4, 2)
        with database.transaction(immediate=True), pytest.raises(RuntimePolicyConflictError):
            RuntimeRepository(database.connection()).update_policy(3, 1, _clock().now())
        with pytest.raises(sqlite3.IntegrityError):
            database.connection().execute(
                "UPDATE installation_runtime_policy SET max_concurrent_runtimes = 17"
            )


def test_runtime_event_retention_and_profile_delete_cascade(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        with database.transaction(immediate=True):
            profile_id, model_id = _seed(database.connection())
            repository = RuntimeRepository(database.connection())
            runtime_id = RuntimeId.new()
            for _ in range(5):
                repository.add_event(
                    event_id=str(uuid4()),
                    profile_id=profile_id,
                    model_id=model_id,
                    runtime_id=runtime_id,
                    state=RuntimeState.READY,
                    event_kind=RuntimeEventKind.HEALTH_CHECKED,
                    reason_class=None,
                    occurred_at=_clock().now(),
                    retention_count=2,
                )
            repository.set_last_valid(
                profile_id=profile_id,
                model_id=model_id,
                profile_model_revision=1,
                runtime_id=runtime_id,
                ready_at=_clock().now(),
            )
        assert (
            database.connection().execute("SELECT COUNT(*) FROM runtime_events").fetchone()[0] == 2
        )
        database.connection().execute(
            "DELETE FROM profiles WHERE profile_id = ?", (str(profile_id),)
        )
        assert (
            database.connection().execute("SELECT COUNT(*) FROM runtime_events").fetchone()[0] == 0
        )
        assert (
            database.connection()
            .execute("SELECT COUNT(*) FROM profile_runtime_last_valid")
            .fetchone()[0]
            == 0
        )
