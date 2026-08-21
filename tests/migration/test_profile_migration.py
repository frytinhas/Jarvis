from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from jarvis.foundation.clock import FakeClock
from jarvis.foundation.errors import StorageError
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import (
    Migration,
    MigrationRunner,
    current_schema_version,
    load_packaged_migrations,
)

pytestmark = pytest.mark.migration

JARVIS_ID = "10000000-0000-4000-8000-000000000001"
STANDARD_ID = "10000000-0000-4000-8000-000000000002"
NOW = "2026-08-11T12:00:00.000000Z"


def _clock() -> FakeClock:
    return FakeClock(datetime(2026, 8, 11, 12, tzinfo=UTC))


def _database(tmp_path: Path) -> SQLiteDatabase:
    directory = tmp_path / "data" / "jarvis-cli"
    directory.mkdir(parents=True, mode=0o700)
    return SQLiteDatabase((directory / "jarvis.sqlite3").absolute())


def _insert_profile(connection: sqlite3.Connection, profile_id: str, kind: str, alias: str) -> None:
    connection.execute(
        "INSERT INTO profiles VALUES (?, ?, ?, 1, ?, ?)",
        (profile_id, kind, "Jarvis" if kind == "jarvis" else "Work", NOW, NOW),
    )
    connection.execute(
        "INSERT INTO profile_aliases VALUES (?, ?, ?, ?)", (profile_id, alias, NOW, NOW)
    )


def test_schema_one_upgrades_to_profile_schema_once(tmp_path: Path) -> None:
    packaged = load_packaged_migrations()
    database = _database(tmp_path)
    with database:
        first = MigrationRunner(database, _clock(), packaged[:1]).apply()
        upgrade = MigrationRunner(database, _clock()).apply()
        repeated = MigrationRunner(database, _clock()).apply()
        tables = {
            row[0]
            for row in database.connection()
            .execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
            .fetchall()
        }
    assert first.applied_versions == (1,)
    assert upgrade.applied_versions == (2, 3, 4)
    assert repeated.applied_versions == ()
    assert tables == {
        "schema_migrations",
        "profiles",
        "profile_aliases",
        "profile_configurations",
        "profile_configuration_sections",
        "profile_messages",
        "profile_permissions",
        "profile_operation_intents",
        "installation_runtime_config",
        "models",
        "model_paths",
        "profile_models",
        "runtime_events",
        "profile_runtime_last_valid",
        "installation_runtime_policy",
    }


def test_migration_0001_remains_byte_for_byte_immutable() -> None:
    migration = load_packaged_migrations()[0]
    assert migration.name == "migration_ledger"
    assert migration.checksum_sha256 == (
        "9ae711fc0da6cb744516130e94ef545754decbd78628d5f2a78ffcd495722a7e"
    )
    assert hashlib.sha256(migration.sql.encode()).hexdigest() == migration.checksum_sha256


def test_schema_two_upgrades_atomically_to_model_registry_without_backfill(tmp_path: Path) -> None:
    packaged = load_packaged_migrations()
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock(), packaged[:2]).apply()
        _insert_profile(database.connection(), JARVIS_ID, "jarvis", "jarvis")
        upgraded = MigrationRunner(database, _clock()).apply()
        assert upgraded.applied_versions == (3, 4)
        assert database.connection().execute("SELECT count(*) FROM models").fetchone()[0] == 0
        assert (
            database.connection().execute("SELECT count(*) FROM profile_models").fetchone()[0] == 0
        )


def test_failed_model_registry_migration_leaves_schema_two_intact(tmp_path: Path) -> None:
    packaged = load_packaged_migrations()
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock(), packaged[:2]).apply()
        broken = Migration.create(
            3,
            "model_registry",
            "CREATE TABLE models_partial (value TEXT); INVALID SQL;",
        )
        with pytest.raises(StorageError):
            MigrationRunner(database, _clock(), (*packaged[:2], broken)).apply()
        assert current_schema_version(database) == 2
        assert (
            database.connection()
            .execute("SELECT count(*) FROM sqlite_master WHERE name = 'models_partial'")
            .fetchone()[0]
            == 0
        )


def test_model_registry_constraints_allow_path_history_and_enforce_profile_selection(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        connection = database.connection()
        _insert_profile(connection, STANDARD_ID, "standard", "work")
        for suffix in (1, 2):
            model_id = f"30000000-0000-4000-8000-{suffix:012d}"
            connection.execute(
                "INSERT INTO models VALUES (?, ?, 1, ?, 64, 1, '{}', 'available', NULL, ?)",
                (model_id, str(suffix) * 64, suffix, NOW),
            )
            connection.execute(
                "INSERT INTO model_paths (model_id, canonical_path) "
                "VALUES (?, '/models/shared.gguf')",
                (model_id,),
            )
        first = "30000000-0000-4000-8000-000000000001"
        second = "30000000-0000-4000-8000-000000000002"
        connection.execute(
            "INSERT INTO profile_models VALUES (?, ?, 1, 1, 1, '{}', ?, ?)",
            (STANDARD_ID, first, NOW, NOW),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO profile_models VALUES (?, ?, 1, 1, 0, '{}', ?, ?)",
                (STANDARD_ID, second, NOW, NOW),
            )
        connection.execute("DELETE FROM profiles WHERE profile_id = ?", (STANDARD_ID,))
        assert connection.execute("SELECT count(*) FROM profile_models").fetchone()[0] == 0


def test_profile_foreign_keys_indexes_and_cascade(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        connection = database.connection()
        _insert_profile(connection, STANDARD_ID, "standard", "work")
        connection.execute(
            """
            INSERT INTO profile_configurations VALUES
                (?, 1, 1, '', '', '#000000', '#111111', '#222222',
                 'essential-minimum', 0, ?, ?)
            """,
            (STANDARD_ID, NOW, NOW),
        )
        connection.execute(
            "INSERT INTO profile_permissions VALUES (?, 'read', 'allow')", (STANDARD_ID,)
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO profile_configuration_sections VALUES (?, 'persona', 1, 1)",
                (STANDARD_ID,),
            )
        connection.execute("DELETE FROM profiles WHERE profile_id = ?", (STANDARD_ID,))
        owned_counts = [
            connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in (
                "profile_aliases",
                "profile_configurations",
                "profile_permissions",
            )
        ]
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
    assert owned_counts == [0, 0, 0]
    assert "one_jarvis_profile" in indexes
    assert "profile_operation_intents_expiry" in indexes


def test_narrow_jarvis_triggers_protect_kind_alias_and_delete(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        connection = database.connection()
        _insert_profile(connection, JARVIS_ID, "jarvis", "jarvis")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE profiles SET profile_kind = 'standard' WHERE profile_id = ?", (JARVIS_ID,)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE profile_aliases SET command_alias = 'other' WHERE profile_id = ?",
                (JARVIS_ID,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM profile_aliases WHERE profile_id = ?", (JARVIS_ID,))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM profiles WHERE profile_id = ?", (JARVIS_ID,))


def test_jarvis_triggers_block_replace_upsert_and_primary_key_bypasses(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        connection = database.connection()
        _insert_profile(connection, JARVIS_ID, "jarvis", "jarvis")
        _insert_profile(connection, STANDARD_ID, "standard", "work")
        replacement_id = "10000000-0000-4000-8000-000000000099"

        statements = (
            (
                "INSERT OR REPLACE INTO profiles VALUES (?, 'standard', 'Replacement', 1, ?, ?)",
                (JARVIS_ID, NOW, NOW),
            ),
            (
                "INSERT OR REPLACE INTO profiles VALUES (?, 'jarvis', 'Replacement', 1, ?, ?)",
                (replacement_id, NOW, NOW),
            ),
            (
                "INSERT INTO profiles VALUES (?, 'standard', 'Replacement', 1, ?, ?) "
                "ON CONFLICT(profile_id) DO UPDATE SET profile_kind = excluded.profile_kind",
                (JARVIS_ID, NOW, NOW),
            ),
            (
                "UPDATE OR REPLACE profiles SET profile_id = ? WHERE profile_id = ?",
                (JARVIS_ID, STANDARD_ID),
            ),
            (
                "UPDATE profiles SET profile_id = ? WHERE profile_id = ?",
                (replacement_id, JARVIS_ID),
            ),
            (
                "INSERT OR REPLACE INTO profile_aliases VALUES (?, 'jarvis', ?, ?)",
                (JARVIS_ID, NOW, NOW),
            ),
            (
                "UPDATE OR REPLACE profile_aliases "
                "SET profile_id = ?, command_alias = 'jarvis' WHERE profile_id = ?",
                (JARVIS_ID, STANDARD_ID),
            ),
        )
        for sql, parameters in statements:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(sql, parameters)

        assert connection.execute(
            "SELECT profile_id, profile_kind, display_name "
            "FROM profiles WHERE profile_kind = 'jarvis'"
        ).fetchall() == [(JARVIS_ID, "jarvis", "Jarvis")]
        assert connection.execute(
            "SELECT profile_id, command_alias FROM profile_aliases WHERE command_alias = 'jarvis'"
        ).fetchall() == [(JARVIS_ID, "jarvis")]


@pytest.mark.parametrize(
    ("kind", "scope"),
    [
        ("delete-profile", "persona"),
        ("reset-configuration", "unknown"),
        ("unknown", "whole-profile"),
    ],
)
def test_invalid_operation_scope_combinations_fail_at_database_boundary(
    tmp_path: Path, kind: str, scope: str
) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        connection = database.connection()
        _insert_profile(connection, STANDARD_ID, "standard", "work")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO profile_operation_intents VALUES
                    (?, ?, ?, ?, 1, 1, ?, ?, ?, ?)
                """,
                (
                    "20000000-0000-4000-8000-000000000001",
                    STANDARD_ID,
                    kind,
                    scope,
                    "a" * 64,
                    "b" * 64,
                    NOW,
                    "2026-08-11T12:05:00.000000Z",
                ),
            )


@pytest.mark.parametrize(
    "alias",
    ["UPPER", "-edge", "edge-", "two--hyphens", "path/name", "x" * 64],
)
def test_invalid_alias_shapes_fail_at_database_boundary(tmp_path: Path, alias: str) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        connection = database.connection()
        connection.execute(
            "INSERT INTO profiles VALUES (?, 'standard', 'Work', 1, ?, ?)",
            (STANDARD_ID, NOW, NOW),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO profile_aliases VALUES (?, ?, ?, ?)",
                (STANDARD_ID, alias, NOW, NOW),
            )


def test_future_milestone_tables_are_absent(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        names = {
            row[0]
            for row in database.connection()
            .execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            .fetchall()
        }
    forbidden = {
        "sessions",
        "messages",
        "memories",
        "private_notes",
        "learning_state",
        "tool_calls",
        "approvals",
        "audit_events",
        "ipc_requests",
    }
    assert names.isdisjoint(forbidden)
