from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest

from jarvis.chat.errors import ChatNotFoundError
from jarvis.chat.models import TurnState
from jarvis.chat.repository import ConversationRepository
from jarvis.foundation.clock import FakeClock
from jarvis.models.models import ModelId
from jarvis.profiles.models import ProfileId
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import (
    MigrationRunner,
    current_schema_version,
    load_packaged_migrations,
)

pytestmark = pytest.mark.migration
NOW = datetime(2026, 8, 21, 12, tzinfo=UTC)
STAMP = "2026-08-21T12:00:00.000000Z"


def _database(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    root.mkdir(mode=0o700)
    return (root / "jarvis.sqlite3").absolute()


def _seed(path: Path) -> tuple[ProfileId, ProfileId, ModelId]:
    first, second, model = ProfileId(uuid4()), ProfileId(uuid4()), ModelId.new()
    with SQLiteDatabase(path) as database, database.transaction(immediate=True):
        connection = database.connection()
        for profile, name in ((first, "First"), (second, "Second")):
            connection.execute(
                "INSERT INTO profiles VALUES (?, 'standard', ?, 1, ?, ?)",
                (str(profile), name, STAMP, STAMP),
            )
        connection.execute(
            "INSERT INTO models VALUES (?, ?, 1, 2, 10, 3, '{}', 'available', NULL, ?)",
            (str(model), "a" * 64, STAMP),
        )
    return first, second, model


def test_v4_to_v5_is_exact_and_chat_ownership_is_enforced(tmp_path: Path) -> None:
    path = _database(tmp_path)
    migrations = load_packaged_migrations()
    with SQLiteDatabase(path) as database:
        MigrationRunner(database, FakeClock(NOW), migrations[:4]).apply()
        assert current_schema_version(database) == 4
        result = MigrationRunner(database, FakeClock(NOW)).apply()
        assert result.applied_versions == (5,)
        assert current_schema_version(database) == 5
    first, second, model = _seed(path)
    repository = ConversationRepository(path)
    admitted = repository.admit(
        profile_id=first,
        model_id=model,
        request_id=str(uuid4()),
        content="hello",
        now=NOW,
        max_message_bytes=1024,
        max_session_bytes=4096,
    )
    assert admitted.learning.status.value == "ACTIVE"
    with pytest.raises(ChatNotFoundError) as caught:
        repository.get_turn(admitted.turn.turn_id, second)
    assert getattr(caught.value, "code", "") == "chat.not_found"
    generating = repository.mark_generating(admitted.turn, NOW)
    completed = repository.finalize(
        generating,
        state=TurnState.COMPLETED,
        partial_text="world",
        failure_code=None,
        now=NOW,
        max_message_bytes=1024,
        max_session_bytes=4096,
    )
    assert completed.state is TurnState.COMPLETED
    with SQLiteDatabase(path) as database:
        assert database.connection().execute(
            "SELECT role, ordinal FROM chat_messages ORDER BY ordinal"
        ).fetchall() == [("user", 0), ("assistant", 1)]


def test_profile_delete_cascades_all_chat_state(tmp_path: Path) -> None:
    path = _database(tmp_path)
    with SQLiteDatabase(path) as database:
        MigrationRunner(database, FakeClock(NOW)).apply()
    profile, _other, model = _seed(path)
    repository = ConversationRepository(path)
    repository.admit(
        profile_id=profile,
        model_id=model,
        request_id=str(uuid4()),
        content="hello",
        now=NOW,
        max_message_bytes=1024,
        max_session_bytes=4096,
    )
    with SQLiteDatabase(path) as database, database.transaction(immediate=True):
        database.connection().execute("DELETE FROM profiles WHERE profile_id = ?", (str(profile),))
    with SQLiteDatabase(path) as database:
        connection = database.connection()
        for table in ("chat_sessions", "chat_turns", "chat_messages", "learning_state"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_migration_0005_is_packaged_once_and_predecessors_are_unchanged() -> None:
    migrations = load_packaged_migrations()
    assert [migration.version for migration in migrations] == [1, 2, 3, 4, 5]
    assert migrations[-1].name == "chat_pipeline"


def test_first_learning_initialization_is_atomic_under_concurrent_admission(
    tmp_path: Path,
) -> None:
    path = _database(tmp_path)
    with SQLiteDatabase(path) as database:
        MigrationRunner(database, FakeClock(NOW)).apply()
    profile, _other, model = _seed(path)
    repository = ConversationRepository(path)
    barrier = Barrier(8)

    def admit(index: int) -> None:
        barrier.wait()
        repository.admit(
            profile_id=profile,
            model_id=model,
            request_id=str(uuid4()),
            content=f"request-{index}",
            now=NOW,
            max_message_bytes=1024,
            max_session_bytes=4096,
            new_session=True,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(admit, index) for index in range(8)]
        for future in futures:
            future.result(timeout=10)
    with SQLiteDatabase(path) as database:
        connection = database.connection()
        assert connection.execute("SELECT COUNT(*) FROM learning_state").fetchone()[0] == 1
        assert connection.execute("SELECT status, revision FROM learning_state").fetchone() == (
            "ACTIVE",
            1,
        )


def test_message_ordinals_are_unique_under_same_session_admission_race(tmp_path: Path) -> None:
    path = _database(tmp_path)
    with SQLiteDatabase(path) as database:
        MigrationRunner(database, FakeClock(NOW)).apply()
    profile, _other, model = _seed(path)
    repository = ConversationRepository(path)
    initial = repository.admit(
        profile_id=profile,
        model_id=model,
        request_id=str(uuid4()),
        content="initial",
        now=NOW,
        max_message_bytes=1024,
        max_session_bytes=4096,
    )
    barrier = Barrier(8)

    def admit(index: int) -> None:
        barrier.wait()
        repository.admit(
            profile_id=profile,
            model_id=model,
            request_id=str(uuid4()),
            content=f"request-{index}",
            now=NOW,
            max_message_bytes=1024,
            max_session_bytes=4096,
            requested_session_id=initial.turn.session_id,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(admit, index) for index in range(8)]
        for future in futures:
            future.result(timeout=10)
    with SQLiteDatabase(path) as database:
        ordinals = [
            row[0]
            for row in database.connection().execute(
                "SELECT ordinal FROM chat_messages WHERE session_id = ? ORDER BY ordinal",
                (str(initial.turn.session_id),),
            )
        ]
    assert ordinals == list(range(9))
