"""Forward-only immutable SQLite migrations with a checksum ledger."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import files

from jarvis.foundation.clock import Clock, format_utc
from jarvis.foundation.errors import StorageError
from jarvis.storage.database import SQLiteDatabase

_MIGRATION_NAME = re.compile(r"^(?P<version>[0-9]{4})_(?P<name>[a-z0-9_]+)\.sql$")
_TRANSACTION_CONTROL_AT_STATEMENT_START = re.compile(
    r"^\s*(?:BEGIN(?:\s+(?:DEFERRED|IMMEDIATE|EXCLUSIVE|TRANSACTION))?"
    r"|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|END\s+TRANSACTION)\b",
    re.IGNORECASE,
)


def _contains_transaction_control(sql: str) -> bool:
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            if _TRANSACTION_CONTROL_AT_STATEMENT_START.search(buffer):
                return True
            buffer = ""
    return bool(buffer.strip() and _TRANSACTION_CONTROL_AT_STATEMENT_START.search(buffer))


def _execute_migration_sql(connection: sqlite3.Connection, sql: str) -> None:
    """Execute complete statements without sqlite3.executescript's implicit commit."""

    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                connection.execute(statement)
            buffer = ""
    if buffer.strip():
        raise sqlite3.OperationalError("incomplete migration SQL statement")


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str
    checksum_sha256: str

    @classmethod
    def create(cls, version: int, name: str, sql: str) -> Migration:
        if version <= 0 or not name or not re.fullmatch(r"[a-z0-9_]+", name):
            raise ValueError("invalid migration identity")
        if _contains_transaction_control(sql):
            raise ValueError("migration SQL must not control transactions")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        return cls(version, name, sql, checksum)


@dataclass(frozen=True, slots=True)
class MigrationResult:
    applied_versions: tuple[int, ...]
    current_version: int


def load_packaged_migrations() -> tuple[Migration, ...]:
    root = files("jarvis.storage").joinpath("migration_files")
    loaded: list[Migration] = []
    for resource in sorted(root.iterdir(), key=lambda item: item.name):
        if not resource.is_file():
            continue
        match = _MIGRATION_NAME.fullmatch(resource.name)
        if match is None:
            raise StorageError(
                code="database.migration_failed",
                message_key="error.database.invalid_migration_resource",
                safe_details={"resource": resource.name},
            )
        loaded.append(
            Migration.create(
                int(match.group("version")),
                match.group("name"),
                resource.read_text(encoding="utf-8"),
            )
        )
    _validate_migration_sequence(loaded)
    return tuple(loaded)


def _validate_migration_sequence(migrations: Sequence[Migration]) -> None:
    if not migrations:
        raise StorageError(
            code="database.migration_failed",
            message_key="error.database.no_migrations",
        )
    expected = list(range(1, len(migrations) + 1))
    actual = [migration.version for migration in migrations]
    if actual != expected or len({migration.name for migration in migrations}) != len(migrations):
        raise StorageError(
            code="database.migration_failed",
            message_key="error.database.migration_gap",
            safe_details={"versions": ",".join(str(version) for version in actual)},
        )


class MigrationRunner:
    """Applies every pending migration in one immediate transaction."""

    def __init__(
        self,
        database: SQLiteDatabase,
        clock: Clock,
        migrations: Sequence[Migration] | None = None,
    ) -> None:
        self._database = database
        self._clock = clock
        self._migrations = (
            tuple(migrations) if migrations is not None else load_packaged_migrations()
        )
        _validate_migration_sequence(self._migrations)

    def apply(self) -> MigrationResult:
        connection = self._database.connection()
        try:
            with self._database.transaction(immediate=True):
                applied = self._read_ledger(connection)
                self._validate_applied(applied)
                pending = self._migrations[len(applied) :]
                for migration in pending:
                    _execute_migration_sql(connection, migration.sql)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations
                            (version, name, checksum_sha256, applied_at_utc)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            migration.version,
                            migration.name,
                            migration.checksum_sha256,
                            format_utc(self._clock.now()),
                        ),
                    )
        except StorageError:
            raise
        except sqlite3.Error as error:
            raise StorageError(
                code="database.migration_failed",
                message_key="error.database.migration_failed",
                internal_message=str(error),
            ) from error
        return MigrationResult(tuple(item.version for item in pending), len(self._migrations))

    @staticmethod
    def _read_ledger(connection: sqlite3.Connection) -> tuple[Migration, ...]:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone()
        if exists is None:
            return ()
        try:
            rows = connection.execute(
                """
                SELECT version, name, checksum_sha256, ''
                FROM schema_migrations
                ORDER BY version
                """
            ).fetchall()
        except sqlite3.Error as error:
            raise StorageError(
                code="database.incompatible_schema",
                message_key="error.database.invalid_migration_ledger",
                internal_message=str(error),
            ) from error
        return tuple(Migration(int(row[0]), str(row[1]), str(row[3]), str(row[2])) for row in rows)

    def _validate_applied(self, applied: Sequence[Migration]) -> None:
        versions = [migration.version for migration in applied]
        if versions != list(range(1, len(applied) + 1)):
            raise StorageError(
                code="database.incompatible_schema",
                message_key="error.database.noncontiguous_schema",
            )
        if len(applied) > len(self._migrations):
            raise StorageError(
                code="database.incompatible_schema",
                message_key="error.database.newer_schema",
                safe_details={"database_version": len(applied)},
            )
        for recorded, packaged in zip(applied, self._migrations, strict=False):
            if (
                recorded.version != packaged.version
                or recorded.name != packaged.name
                or recorded.checksum_sha256 != packaged.checksum_sha256
            ):
                raise StorageError(
                    code="database.incompatible_schema",
                    message_key="error.database.migration_checksum_mismatch",
                    safe_details={"version": recorded.version},
                )


def current_schema_version(database: SQLiteDatabase) -> int:
    connection = database.connection()
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    if exists is None:
        return 0
    row = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    return int(row[0])
