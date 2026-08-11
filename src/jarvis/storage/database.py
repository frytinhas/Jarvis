"""Owned SQLite connections with secure local file and explicit transaction semantics."""

from __future__ import annotations

import fcntl
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from types import TracebackType
from typing import Self

from jarvis.foundation.errors import StorageError
from jarvis.storage.xdg import (
    PRIVATE_FILE_MODE,
    verify_private_directory,
    verify_private_file,
    verify_private_file_descriptor,
)

_DATABASE_OPEN_LOCK = threading.RLock()


class SQLiteDatabase:
    """One explicitly owned SQLite connection; instances are not shared across threads."""

    def __init__(self, path: Path, *, busy_timeout_ms: int = 5_000) -> None:
        if not path.is_absolute():
            raise StorageError(
                code="database.open_failed",
                message_key="error.database.open_failed",
                safe_details={"reason": "relative_path"},
            )
        if busy_timeout_ms <= 0 or busy_timeout_ms > 60_000:
            raise ValueError("busy_timeout_ms must be between 1 and 60000")
        self.path = path
        self.busy_timeout_ms = busy_timeout_ms
        self._connection: sqlite3.Connection | None = None

    @property
    def is_open(self) -> bool:
        return self._connection is not None

    def open(self) -> sqlite3.Connection:
        with _DATABASE_OPEN_LOCK:
            return self._open_locked()

    def _open_locked(self) -> sqlite3.Connection:
        if self._connection is not None:
            raise RuntimeError("database connection is already open")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        verify_private_directory(self.path.parent)
        created = False
        descriptor: int | None = None
        created_identity: tuple[int, int] | None = None
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(self.path, flags, PRIVATE_FILE_MODE)
        except FileExistsError:
            existing_flags = os.O_RDWR
            if hasattr(os, "O_CLOEXEC"):
                existing_flags |= os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                existing_flags |= os.O_NOFOLLOW
            try:
                descriptor = os.open(self.path, existing_flags)
            except OSError as error:
                raise StorageError(
                    code="database.open_failed",
                    message_key="error.database.open_failed",
                    internal_message=str(error),
                ) from error
        except OSError as error:
            raise StorageError(
                code="database.open_failed",
                message_key="error.database.open_failed",
                internal_message=str(error),
            ) from error
        else:
            created = True
        assert descriptor is not None
        locked = False
        connection: sqlite3.Connection | None = None
        try:
            opened_metadata = verify_private_file_descriptor(descriptor)
            path_metadata = verify_private_file(self.path)
            if (opened_metadata.st_dev, opened_metadata.st_ino) != (
                path_metadata.st_dev,
                path_metadata.st_ino,
            ):
                raise StorageError(
                    code="database.open_failed",
                    message_key="error.database.open_failed",
                    safe_details={"reason": "identity_changed"},
                )
            if created:
                created_identity = (opened_metadata.st_dev, opened_metadata.st_ino)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
            database_uri = f"file:/proc/self/fd/{descriptor}?mode=rw"
            connection = sqlite3.connect(
                database_uri,
                uri=True,
                timeout=self.busy_timeout_ms / 1000,
                isolation_level=None,
                check_same_thread=True,
            )
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms:d}")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            current_path = verify_private_file(self.path)
            if (current_path.st_dev, current_path.st_ino) != (
                opened_metadata.st_dev,
                opened_metadata.st_ino,
            ):
                raise StorageError(
                    code="database.open_failed",
                    message_key="error.database.open_failed",
                    safe_details={"reason": "identity_changed"},
                )
        except sqlite3.Error as error:
            if connection is not None:
                connection.close()
            if created:
                self._remove_unchanged_empty_file(created_identity)
            raise StorageError(
                code="database.open_failed",
                message_key="error.database.open_failed",
                internal_message=str(error),
            ) from error
        except StorageError:
            if connection is not None:
                connection.close()
            raise
        except OSError as error:
            if created:
                self._remove_unchanged_empty_file(created_identity)
            raise StorageError(
                code="database.open_failed",
                message_key="error.database.open_failed",
                internal_message=str(error),
            ) from error
        finally:
            if locked:
                with suppress(OSError):
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
        assert connection is not None
        self._connection = connection
        return connection

    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("database connection is not open")
        return self._connection

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        connection = self.connection()
        if connection.in_transaction:
            raise RuntimeError("nested transactions are not supported")
        connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        else:
            try:
                connection.commit()
            except BaseException:
                with suppress(sqlite3.Error):
                    connection.rollback()
                raise

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            if connection.in_transaction:
                connection.rollback()
            connection.close()

    def _remove_unchanged_empty_file(self, expected_identity: tuple[int, int] | None) -> None:
        try:
            metadata = verify_private_file(self.path)
            if (
                expected_identity is not None
                and (metadata.st_dev, metadata.st_ino) == expected_identity
                and metadata.st_size == 0
            ):
                self.path.unlink()
        except (OSError, StorageError):
            pass

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
