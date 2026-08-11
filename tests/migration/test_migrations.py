from __future__ import annotations

import multiprocessing
import sqlite3
import threading
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


def _clock() -> FakeClock:
    return FakeClock(datetime(2026, 8, 10, 12, 0, tzinfo=UTC))


def _database(tmp_path: Path) -> SQLiteDatabase:
    data = tmp_path / "data" / "jarvis-cli"
    data.mkdir(parents=True, mode=0o700)
    return SQLiteDatabase((data / "jarvis.sqlite3").absolute())


def test_initial_migration_creates_only_ledger_and_is_idempotent(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        first = MigrationRunner(database, _clock()).apply()
        second = MigrationRunner(database, _clock()).apply()
        tables = (
            database.connection()
            .execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
            .fetchall()
        )
        rows = (
            database.connection()
            .execute("SELECT version, name, applied_at_utc FROM schema_migrations")
            .fetchall()
        )
    assert first.applied_versions == (1,)
    assert second.applied_versions == ()
    assert tables == [("schema_migrations",)]
    assert rows == [(1, "migration_ledger", "2026-08-10T12:00:00.000000Z")]


def test_connection_pragmas_lifecycle_and_file_permissions(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        connection = database.connection()
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert database.is_open
        assert database.path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(RuntimeError, match="not open"):
        database.connection()
    assert not database.is_open


def test_database_rejects_hardlinks_symlinks_and_unsafe_parent(tmp_path: Path) -> None:
    database = _database(tmp_path)
    victim = database.path.with_name("external-private-file")
    original = b"external-content"
    victim.write_bytes(original)
    victim.chmod(0o600)
    try:
        database.path.hardlink_to(victim)
    except OSError as error:
        pytest.skip(f"hardlinks unavailable: {error}")
    with pytest.raises(StorageError):
        database.open()
    assert victim.read_bytes() == original
    database.path.unlink()
    database.path.symlink_to(victim)
    with pytest.raises(StorageError):
        database.open()
    database.path.unlink()
    database.path.parent.chmod(0o755)
    with pytest.raises(StorageError):
        database.open()


def test_complete_pending_set_rolls_back_on_failure(tmp_path: Path) -> None:
    migrations = (
        load_packaged_migrations()[0],
        Migration.create(2, "broken", "CREATE TABLE partial (value TEXT); INVALID SQL;"),
    )
    database = _database(tmp_path)
    with database, pytest.raises(StorageError) as caught:
        MigrationRunner(database, _clock(), migrations).apply()
    assert caught.value.code == "database.migration_failed"
    with sqlite3.connect(database.path) as connection:
        names = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    assert names == []


def test_changed_checksum_fails_closed(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        original = load_packaged_migrations()[0]
        changed = Migration.create(original.version, original.name, original.sql + "\n-- changed\n")
        with pytest.raises(StorageError) as caught:
            MigrationRunner(database, _clock(), (changed,)).apply()
    assert caught.value.code == "database.incompatible_schema"


def test_packaged_or_supplied_version_gap_is_rejected(tmp_path: Path) -> None:
    migrations = (
        load_packaged_migrations()[0],
        Migration.create(3, "gap", "CREATE TABLE gap (value TEXT);"),
    )
    with pytest.raises(StorageError) as caught:
        MigrationRunner(_database(tmp_path), _clock(), migrations)
    assert caught.value.code == "database.migration_failed"


def test_unknown_higher_database_version_fails_closed(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        connection = database.connection()
        connection.execute(
            "INSERT INTO schema_migrations VALUES (2, 'future', ?, ?)",
            ("0" * 64, "2026-08-10T12:00:00.000000Z"),
        )
        with pytest.raises(StorageError) as caught:
            MigrationRunner(database, _clock()).apply()
    assert caught.value.code == "database.incompatible_schema"


def test_noncontiguous_database_ledger_fails_closed(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        MigrationRunner(database, _clock()).apply()
        connection = database.connection()
        connection.execute("UPDATE schema_migrations SET version = 2 WHERE version = 1")
        with pytest.raises(StorageError) as caught:
            MigrationRunner(database, _clock()).apply()
    assert caught.value.code == "database.incompatible_schema"


def test_explicit_transaction_rolls_back_and_rejects_nesting(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database:
        connection = database.connection()
        connection.execute("CREATE TABLE values_table (value TEXT)")
        with pytest.raises(RuntimeError, match="synthetic"), database.transaction():
            connection.execute("INSERT INTO values_table VALUES ('partial')")
            raise RuntimeError("synthetic")
        assert connection.execute("SELECT * FROM values_table").fetchall() == []
        with (
            database.transaction(),
            pytest.raises(RuntimeError, match="nested"),
            database.transaction(),
        ):
            pass


def test_concurrent_initializers_serialize_and_apply_once(tmp_path: Path) -> None:
    path = _database(tmp_path).path
    barrier = threading.Barrier(2)
    results: list[tuple[int, ...]] = []
    failures: list[BaseException] = []

    def run() -> None:
        try:
            barrier.wait()
            with SQLiteDatabase(path) as database:
                results.append(MigrationRunner(database, _clock()).apply().applied_versions)
        except BaseException as error:
            failures.append(error)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not failures
    assert sorted(results) == [(), (1,)]
    with SQLiteDatabase(path) as database:
        assert current_schema_version(database) == 1


def test_cross_process_connection_initialization_is_serialized(tmp_path: Path) -> None:
    path = _database(tmp_path).path
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(4)

    def run() -> None:
        barrier.wait()
        with SQLiteDatabase(path) as database:
            MigrationRunner(database, _clock()).apply()

    processes = [context.Process(target=run) for _ in range(4)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
    assert [process.exitcode for process in processes] == [0, 0, 0, 0]
    with SQLiteDatabase(path) as database:
        assert current_schema_version(database) == 1


def test_migration_sql_rejects_transaction_control() -> None:
    with pytest.raises(ValueError, match="control transactions"):
        Migration.create(1, "unsafe", "BEGIN; CREATE TABLE unsafe (value TEXT); COMMIT;")
