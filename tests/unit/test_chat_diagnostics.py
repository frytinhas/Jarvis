from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.chat.diagnostics import ChatDiagnosticService
from jarvis.chat.errors import ChatStorageError
from jarvis.chat.repository import ConversationRepository
from jarvis.config.defaults import DefaultsRegistry
from jarvis.foundation.clock import FakeClock
from jarvis.models.models import ModelId
from jarvis.profiles.models import ProfileId
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import MigrationRunner

pytestmark = pytest.mark.unit
NOW = datetime(2026, 8, 21, 12, tzinfo=UTC)
STAMP = "2026-08-21T12:00:00.000000Z"


def _seed(path: Path) -> tuple[ProfileId, ModelId]:
    profile_id, model_id = ProfileId(uuid4()), ModelId.new()
    with SQLiteDatabase(path) as database:
        MigrationRunner(database, FakeClock(NOW)).apply()
        with database.transaction(immediate=True):
            connection = database.connection()
            connection.execute(
                "INSERT INTO profiles VALUES (?, 'standard', 'Jarvis', 1, ?, ?)",
                (str(profile_id), STAMP, STAMP),
            )
            connection.execute(
                "INSERT INTO models VALUES (?, ?, 1, 2, 10, 3, '{}', 'available', NULL, ?)",
                (str(model_id), "a" * 64, STAMP),
            )
    return profile_id, model_id


def _turn(path: Path, profile_id: ProfileId, model_id: ModelId, content: str):  # type: ignore[no-untyped-def]
    return (
        ConversationRepository(path)
        .admit(
            profile_id=profile_id,
            model_id=model_id,
            request_id=str(uuid4()),
            content=content,
            now=NOW,
            max_message_bytes=1024,
            max_session_bytes=4096,
        )
        .turn
    )


def test_diagnostic_rotation_is_oldest_first_and_never_prunes_open_or_reserved(
    tmp_path: Path,
) -> None:
    path = tmp_path / "chat.sqlite3"
    profile_id, model_id = _seed(path)
    defaults = DefaultsRegistry.load_packaged().current()
    chat = replace(
        defaults.chat,
        max_diagnostic_bytes=1_100,
        minimum_diagnostic_reservation_bytes=400,
    )
    diagnostics = ChatDiagnosticService(path, chat, defaults.foundation_diagnostics, FakeClock(NOW))
    first = _turn(path, profile_id, model_id, "first")
    second = _turn(path, profile_id, model_id, "second")
    diagnostics.emit(first, "queued", "old-1")
    diagnostics.emit(first, "completed", "old-2", closed=True)
    diagnostics.emit(second, "generating", "must-remain-open")
    with SQLiteDatabase(path) as database, database.transaction(immediate=True):
        database.connection().execute(
            "UPDATE chat_diagnostics SET reserved = 1 WHERE summary = 'old-2'"
        )

    reservation = diagnostics.reserve(profile_id, model_id)
    reservation.release()
    with SQLiteDatabase(path) as database:
        rows = (
            database.connection()
            .execute("SELECT summary, closed, reserved FROM chat_diagnostics ORDER BY summary")
            .fetchall()
        )
    assert rows == [("must-remain-open", 0, 0), ("old-2", 1, 1)]


def test_diagnostic_quota_exhaustion_fails_when_only_open_records_exist(tmp_path: Path) -> None:
    path = tmp_path / "chat.sqlite3"
    profile_id, model_id = _seed(path)
    defaults = DefaultsRegistry.load_packaged().current()
    chat = replace(
        defaults.chat,
        max_diagnostic_bytes=700,
        minimum_diagnostic_reservation_bytes=400,
    )
    diagnostics = ChatDiagnosticService(path, chat, defaults.foundation_diagnostics, FakeClock(NOW))
    turn = _turn(path, profile_id, model_id, "active")
    diagnostics.emit(turn, "queued", "open-a")
    diagnostics.emit(turn, "generating", "open-b")

    with pytest.raises(ChatStorageError) as caught:
        diagnostics.reserve(profile_id, model_id)
    assert caught.value.safe_details["reason"] == "diagnostic_reservation_failed"
    with SQLiteDatabase(path) as database:
        assert (
            database.connection()
            .execute("SELECT COUNT(*) FROM chat_diagnostics WHERE closed = 0")
            .fetchone()[0]
            == 2
        )
