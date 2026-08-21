from __future__ import annotations

import errno
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

from jarvis.foundation.bootstrap import initialize_foundation, inspect_foundation
from jarvis.foundation.clock import FakeClock
from jarvis.foundation.errors import StorageError
from jarvis.foundation.identifiers import DeterministicIdGenerator
from jarvis.storage.database import SQLiteDatabase

pytestmark = pytest.mark.integration


def _environment(tmp_path: Path) -> dict[str, str]:
    roots = {
        name: tmp_path / name for name in ("home", "config", "data", "state", "cache", "runtime")
    }
    for path in roots.values():
        path.mkdir(mode=0o700)
    return {
        "HOME": str(roots["home"]),
        "XDG_CONFIG_HOME": str(roots["config"]),
        "XDG_DATA_HOME": str(roots["data"]),
        "XDG_STATE_HOME": str(roots["state"]),
        "XDG_CACHE_HOME": str(roots["cache"]),
        "XDG_RUNTIME_DIR": str(roots["runtime"]),
    }


def _ids(start: int) -> DeterministicIdGenerator:
    return DeterministicIdGenerator(
        UUID(f"10000000-0000-4000-8000-{number:012d}") for number in range(start, start + 4)
    )


def test_initialization_is_idempotent_and_marker_is_written_last(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    clock = FakeClock(datetime(2026, 8, 10, 12, tzinfo=UTC))
    first = initialize_foundation(env, clock=clock, identifiers=_ids(1))
    second = initialize_foundation(env, clock=clock, identifiers=_ids(10))
    assert first["applied_migrations"] == [1, 2, 3, 4, 5]
    assert second["applied_migrations"] == []
    assert first["database_schema_version"] == second["database_schema_version"] == 5
    marker = Path(env["XDG_STATE_HOME"]) / "jarvis-cli" / "foundation-state.json"
    assert json.loads(marker.read_text())["foundation_state_version"] == 1
    assert marker.stat().st_mode & 0o777 == 0o600


def test_all_application_directories_and_files_are_private(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    initialize_foundation(env, identifiers=_ids(1))
    for variable in (
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_CACHE_HOME",
        "XDG_RUNTIME_DIR",
    ):
        application = Path(env[variable]) / "jarvis-cli"
        assert application.stat().st_mode & 0o777 == 0o700
    for root_name in ("data", "state", "runtime"):
        root = tmp_path / root_name / "jarvis-cli"
        for path in root.rglob("*"):
            if path.is_file():
                assert path.stat().st_mode & 0o777 == 0o600


def test_failed_final_marker_does_not_report_initialized_and_rerun_repairs(tmp_path: Path) -> None:
    env = _environment(tmp_path)

    def fail_marker(_path: Path, _payload: bytes, _suffix: str) -> None:
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.atomic_write_failed",
            internal_message=str(OSError(errno.ENOSPC, "synthetic")),
        )

    with pytest.raises(StorageError):
        initialize_foundation(env, identifiers=_ids(1), atomic_writer=fail_marker)
    marker = Path(env["XDG_STATE_HOME"]) / "jarvis-cli" / "foundation-state.json"
    assert not marker.exists()
    repaired = initialize_foundation(env, identifiers=_ids(10))
    assert repaired["applied_migrations"] == []
    assert marker.is_file()


def test_inspection_is_read_only_and_reports_foundation_only(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    initialize_foundation(env, identifiers=_ids(1))
    roots = [Path(env[name]) / "jarvis-cli" for name in env if name.startswith("XDG_")]
    before = {
        path: (path.stat().st_size, path.stat().st_mtime_ns)
        for root in roots
        for path in root.rglob("*")
        if path.is_file()
    }
    result = inspect_foundation(env)
    after = {
        path: (path.stat().st_size, path.stat().st_mtime_ns)
        for root in roots
        for path in root.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert result["foundation_state_version"] == 1
    assert result["database_schema_version"] == 5
    assert len(cast(list[object], result["migrations"])) == 5
    assert all(cast(dict[str, bool], result["directory_safety"]).values())
    assert "profiles" not in result
    assert "models" not in result


def test_inspection_fails_closed_while_wal_transaction_is_active(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    initialize_foundation(env, identifiers=_ids(1))
    path = Path(env["XDG_DATA_HOME"]) / "jarvis-cli" / "jarvis.sqlite3"
    with SQLiteDatabase(path) as database, database.transaction():
        assert inspect_foundation(env)["database_schema_version"] is None
    assert inspect_foundation(env)["database_schema_version"] == 5


def test_initializer_never_uses_real_process_xdg_when_explicit_environment_is_supplied(
    tmp_path: Path,
) -> None:
    env = _environment(tmp_path)
    result = initialize_foundation(env, identifiers=_ids(1))
    for path in cast(dict[str, str], result["paths"]).values():
        assert Path(path).is_relative_to(tmp_path)
