"""SQLite persistence for profile/model-owned chat data."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from jarvis.chat.errors import ChatNotFoundError, ChatStorageError
from jarvis.chat.models import (
    LearningSnapshot,
    LearningStatus,
    MessageId,
    MessageRole,
    SessionId,
    StoredMessage,
    TurnId,
    TurnSnapshot,
    TurnState,
)
from jarvis.foundation.clock import format_utc
from jarvis.models.models import ModelId
from jarvis.profiles.models import ProfileId
from jarvis.storage.database import SQLiteDatabase


@dataclass(frozen=True, slots=True)
class AdmittedTurn:
    turn: TurnSnapshot
    learning: LearningSnapshot


class ConversationRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def admit(
        self,
        *,
        profile_id: ProfileId,
        model_id: ModelId,
        request_id: str,
        content: str,
        now: datetime,
        max_message_bytes: int,
        max_session_bytes: int,
        requested_session_id: SessionId | None = None,
        new_session: bool = False,
    ) -> AdmittedTurn:
        encoded = content.encode("utf-8")
        if not content or len(encoded) > max_message_bytes or "\x00" in content:
            raise ChatStorageError("invalid_user_message")
        session_id = SessionId.new()
        turn_id = TurnId.new()
        message_id = MessageId.new()
        timestamp = format_utc(now)
        try:
            with (
                SQLiteDatabase(self._database_path) as database,
                database.transaction(immediate=True),
            ):
                connection = database.connection()
                self._require_owners(connection, profile_id, model_id)
                existing = connection.execute(
                    "SELECT turn_id FROM chat_turns WHERE request_id = ?", (request_id,)
                ).fetchone()
                if existing is not None:
                    raise ChatStorageError("request_id_conflict")
                resolved = None
                if requested_session_id is not None:
                    resolved = connection.execute(
                        """SELECT session_id FROM chat_sessions
                           WHERE session_id = ? AND profile_id = ? AND model_id = ?
                             AND state = 'open'""",
                        (str(requested_session_id), str(profile_id), str(model_id)),
                    ).fetchone()
                    if resolved is None:
                        raise ChatNotFoundError("session_not_found")
                    session_id = requested_session_id
                elif not new_session:
                    resolved = connection.execute(
                        """SELECT session_id FROM chat_sessions
                           WHERE profile_id = ? AND model_id = ? AND state = 'open'
                           ORDER BY updated_at_utc DESC, session_id DESC LIMIT 1""",
                        (str(profile_id), str(model_id)),
                    ).fetchone()
                    if resolved is not None:
                        session_id = SessionId.parse(str(resolved[0]))
                if resolved is None:
                    connection.execute(
                        """INSERT INTO chat_sessions
                           (session_id, profile_id, model_id, state, next_message_ordinal,
                            created_at_utc, updated_at_utc) VALUES (?, ?, ?, 'open', 0, ?, ?)""",
                        (str(session_id), str(profile_id), str(model_id), timestamp, timestamp),
                    )
                used = int(
                    connection.execute(
                        """SELECT COALESCE(SUM(content_bytes),0) FROM chat_messages
                           WHERE session_id = ?""",
                        (str(session_id),),
                    ).fetchone()[0]
                )
                if used + len(encoded) > max_session_bytes:
                    raise ChatStorageError("session_quota_exhausted")
                ordinal = self._claim_ordinal(connection, session_id, timestamp)
                connection.execute(
                    """INSERT INTO chat_turns
                       (turn_id, request_id, session_id, profile_id, model_id, state,
                        created_at_utc) VALUES (?, ?, ?, ?, ?, 'queued', ?)""",
                    (
                        str(turn_id),
                        request_id,
                        str(session_id),
                        str(profile_id),
                        str(model_id),
                        timestamp,
                    ),
                )
                connection.execute(
                    """INSERT INTO chat_messages
                       (message_id, session_id, profile_id, model_id, turn_id, ordinal, role,
                        content, content_bytes, created_at_utc)
                       VALUES (?, ?, ?, ?, ?, ?, 'user', ?, ?, ?)""",
                    (
                        str(message_id),
                        str(session_id),
                        str(profile_id),
                        str(model_id),
                        str(turn_id),
                        ordinal,
                        content,
                        len(encoded),
                        timestamp,
                    ),
                )
                connection.execute(
                    """INSERT INTO learning_state
                       (profile_id, model_id, status, started_at_utc, updated_at_utc,
                        finished_at_utc, revision) VALUES (?, ?, 'ACTIVE', ?, ?, NULL, 1)
                       ON CONFLICT(profile_id, model_id) DO NOTHING""",
                    (str(profile_id), str(model_id), timestamp, timestamp),
                )
                turn = self._get_turn(connection, turn_id, profile_id)
                learning = self._get_learning(connection, profile_id, model_id)
                return AdmittedTurn(turn, learning)
        except sqlite3.Error as error:
            raise ChatStorageError("database_failure") from error

    @staticmethod
    def _require_owners(
        connection: sqlite3.Connection, profile_id: ProfileId, model_id: ModelId
    ) -> None:
        row = connection.execute(
            """SELECT 1 FROM profiles p JOIN models m
               WHERE p.profile_id = ? AND m.model_id = ?""",
            (str(profile_id), str(model_id)),
        ).fetchone()
        if row is None:
            raise ChatNotFoundError("profile_or_model_not_found")

    @staticmethod
    def _claim_ordinal(
        connection: sqlite3.Connection, session_id: SessionId, timestamp: str
    ) -> int:
        row = connection.execute(
            "SELECT next_message_ordinal FROM chat_sessions WHERE session_id = ?",
            (str(session_id),),
        ).fetchone()
        if row is None:
            raise ChatNotFoundError("session_not_found")
        ordinal = int(row[0])
        connection.execute(
            """UPDATE chat_sessions SET next_message_ordinal = ?, updated_at_utc = ?
               WHERE session_id = ?""",
            (ordinal + 1, timestamp, str(session_id)),
        )
        return ordinal

    def history(self, turn: TurnSnapshot) -> tuple[StoredMessage, ...]:
        with SQLiteDatabase(self._database_path) as database:
            rows = (
                database.connection()
                .execute(
                    """SELECT chat_messages.message_id, chat_messages.session_id,
                          chat_messages.profile_id, chat_messages.model_id,
                          chat_messages.turn_id, chat_messages.ordinal, chat_messages.role,
                          chat_messages.content, chat_messages.created_at_utc
                   FROM chat_messages
                   JOIN chat_turns USING (turn_id)
                   WHERE chat_messages.session_id = ? AND chat_messages.profile_id = ?
                     AND chat_messages.model_id = ? AND chat_turns.state = 'completed'
                   ORDER BY chat_messages.ordinal""",
                    (
                        str(turn.session_id),
                        str(turn.profile_id),
                        str(turn.model_id),
                    ),
                )
                .fetchall()
            )
        return tuple(self._message(row) for row in rows)

    def mark_generating(self, turn: TurnSnapshot, now: datetime) -> TurnSnapshot:
        timestamp = format_utc(now)
        with SQLiteDatabase(self._database_path) as database, database.transaction(immediate=True):
            connection = database.connection()
            changed = connection.execute(
                """UPDATE chat_turns SET state = 'generating', started_at_utc = ?
                   WHERE turn_id = ? AND profile_id = ? AND state = 'queued'""",
                (timestamp, str(turn.turn_id), str(turn.profile_id)),
            ).rowcount
            if changed != 1:
                raise ChatNotFoundError("turn_not_queued")
            return self._get_turn(connection, turn.turn_id, turn.profile_id)

    def store_partial(self, turn: TurnSnapshot, text: str, max_bytes: int) -> None:
        encoded = text.encode("utf-8")
        truncated = len(encoded) > max_bytes
        if truncated:
            encoded = encoded[:max_bytes]
            while True:
                try:
                    text = encoded.decode("utf-8")
                    break
                except UnicodeDecodeError as error:
                    encoded = encoded[: error.start]
        with SQLiteDatabase(self._database_path) as database, database.transaction(immediate=True):
            database.connection().execute(
                """UPDATE chat_turns SET partial_text = ?, partial_truncated = ?
                   WHERE turn_id = ? AND profile_id = ? AND state = 'generating'""",
                (text, int(truncated), str(turn.turn_id), str(turn.profile_id)),
            )

    def finalize(
        self,
        turn: TurnSnapshot,
        *,
        state: TurnState,
        partial_text: str,
        failure_code: str | None,
        now: datetime,
        max_message_bytes: int,
        max_session_bytes: int,
    ) -> TurnSnapshot:
        if state not in {TurnState.COMPLETED, TurnState.FAILED, TurnState.CANCELLED}:
            raise ValueError("turn must be terminal")
        timestamp = format_utc(now)
        with SQLiteDatabase(self._database_path) as database, database.transaction(immediate=True):
            connection = database.connection()
            if state is TurnState.COMPLETED:
                encoded = partial_text.encode("utf-8")
                used = int(
                    connection.execute(
                        """SELECT COALESCE(SUM(content_bytes),0) FROM chat_messages
                           WHERE session_id = ?""",
                        (str(turn.session_id),),
                    ).fetchone()[0]
                )
                if len(encoded) > max_message_bytes or used + len(encoded) > max_session_bytes:
                    raise ChatStorageError("assistant_message_quota_exhausted")
                ordinal = self._claim_ordinal(connection, turn.session_id, timestamp)
                connection.execute(
                    """INSERT INTO chat_messages
                       (message_id, session_id, profile_id, model_id, turn_id, ordinal, role,
                        content, content_bytes, created_at_utc) VALUES (?, ?, ?, ?, ?, ?,
                        'assistant', ?, ?, ?)""",
                    (
                        str(MessageId.new()),
                        str(turn.session_id),
                        str(turn.profile_id),
                        str(turn.model_id),
                        str(turn.turn_id),
                        ordinal,
                        partial_text,
                        len(encoded),
                        timestamp,
                    ),
                )
            changed = connection.execute(
                """UPDATE chat_turns SET state = ?, failure_code = ?, partial_text = ?,
                          completed_at_utc = ?
                   WHERE turn_id = ? AND profile_id = ? AND state IN ('queued','generating')""",
                (
                    state.value,
                    failure_code,
                    partial_text,
                    timestamp,
                    str(turn.turn_id),
                    str(turn.profile_id),
                ),
            ).rowcount
            if changed != 1:
                raise ChatNotFoundError("turn_already_terminal")
            return self._get_turn(connection, turn.turn_id, turn.profile_id)

    def get_turn(self, turn_id: TurnId, profile_id: ProfileId) -> TurnSnapshot:
        with SQLiteDatabase(self._database_path) as database:
            return self._get_turn(database.connection(), turn_id, profile_id)

    def resolve_session(self, profile_id: ProfileId, model_id: ModelId) -> SessionId | None:
        with SQLiteDatabase(self._database_path) as database:
            row = (
                database.connection()
                .execute(
                    """SELECT session_id FROM chat_sessions
                   WHERE profile_id = ? AND model_id = ? AND state = 'open'
                   ORDER BY updated_at_utc DESC, session_id DESC LIMIT 1""",
                    (str(profile_id), str(model_id)),
                )
                .fetchone()
            )
        return None if row is None else SessionId.parse(str(row[0]))

    @staticmethod
    def _get_turn(
        connection: sqlite3.Connection, turn_id: TurnId, profile_id: ProfileId
    ) -> TurnSnapshot:
        row = connection.execute(
            """SELECT turn_id, request_id, session_id, profile_id, model_id, state,
                      partial_text, partial_truncated, failure_code, created_at_utc,
                      started_at_utc, completed_at_utc
               FROM chat_turns WHERE turn_id = ? AND profile_id = ?""",
            (str(turn_id), str(profile_id)),
        ).fetchone()
        if row is None:
            raise ChatNotFoundError("turn_not_found")
        return TurnSnapshot(
            TurnId.parse(str(row[0])),
            str(row[1]),
            SessionId.parse(str(row[2])),
            ProfileId.parse(str(row[3])),
            ModelId.parse(str(row[4])),
            TurnState(str(row[5])),
            str(row[6]),
            bool(row[7]),
            None if row[8] is None else str(row[8]),
            str(row[9]),
            None if row[10] is None else str(row[10]),
            None if row[11] is None else str(row[11]),
        )

    def learning(self, profile_id: ProfileId, model_id: ModelId) -> LearningSnapshot:
        with SQLiteDatabase(self._database_path) as database:
            return self._get_learning(database.connection(), profile_id, model_id)

    @staticmethod
    def _get_learning(
        connection: sqlite3.Connection, profile_id: ProfileId, model_id: ModelId
    ) -> LearningSnapshot:
        row = connection.execute(
            """SELECT status, started_at_utc, updated_at_utc, finished_at_utc, revision
               FROM learning_state WHERE profile_id = ? AND model_id = ?""",
            (str(profile_id), str(model_id)),
        ).fetchone()
        if row is None:
            raise ChatNotFoundError("learning_not_initialized")
        return LearningSnapshot(
            profile_id,
            model_id,
            LearningStatus(str(row[0])),
            str(row[1]),
            str(row[2]),
            None if row[3] is None else str(row[3]),
            int(row[4]),
        )

    def set_learning(
        self, profile_id: ProfileId, model_id: ModelId, status: LearningStatus, now: datetime
    ) -> LearningSnapshot:
        timestamp = format_utc(now)
        with SQLiteDatabase(self._database_path) as database, database.transaction(immediate=True):
            connection = database.connection()
            self._require_owners(connection, profile_id, model_id)
            connection.execute(
                """INSERT INTO learning_state
                   (profile_id, model_id, status, started_at_utc, updated_at_utc,
                    finished_at_utc, revision) VALUES (?, ?, ?, ?, ?, ?, 1)
                   ON CONFLICT(profile_id, model_id) DO UPDATE SET
                    status = excluded.status,
                    started_at_utc = CASE WHEN excluded.status = 'ACTIVE'
                        THEN excluded.started_at_utc ELSE learning_state.started_at_utc END,
                    updated_at_utc = excluded.updated_at_utc,
                    finished_at_utc = excluded.finished_at_utc,
                    revision = learning_state.revision + 1""",
                (
                    str(profile_id),
                    str(model_id),
                    status.value,
                    timestamp,
                    timestamp,
                    timestamp if status is LearningStatus.FINISHED else None,
                ),
            )
            return self._get_learning(connection, profile_id, model_id)

    @staticmethod
    def _message(row: tuple[object, ...]) -> StoredMessage:
        return StoredMessage(
            MessageId.parse(str(row[0])),
            SessionId.parse(str(row[1])),
            ProfileId.parse(str(row[2])),
            ModelId.parse(str(row[3])),
            TurnId.parse(str(row[4])),
            cast(int, row[5]),
            MessageRole(str(row[6])),
            str(row[7]),
            str(row[8]),
        )
