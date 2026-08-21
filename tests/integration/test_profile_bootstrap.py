from __future__ import annotations

import multiprocessing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from jarvis.config.defaults import DefaultsRegistry
from jarvis.foundation.bootstrap import initialize_foundation
from jarvis.foundation.clock import FakeClock
from jarvis.profiles.errors import ProfileInvariantError
from jarvis.profiles.models import (
    ConfigurationSection,
    DeterministicProfileIdGenerator,
    ProfileId,
)
from jarvis.profiles.service import ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import MigrationRunner

pytestmark = pytest.mark.integration

JARVIS_UUID = UUID("10000000-0000-4000-8000-000000000001")


def _clock() -> FakeClock:
    return FakeClock(datetime(2026, 8, 11, 12, tzinfo=UTC))


def _database_path(tmp_path: Path) -> Path:
    directory = tmp_path / "data" / "jarvis-cli"
    directory.mkdir(parents=True, mode=0o700)
    return (directory / "jarvis.sqlite3").absolute()


def _migrate(path: Path) -> None:
    with SQLiteDatabase(path) as database:
        MigrationRunner(database, _clock()).apply()


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


def test_jarvis_bootstrap_is_complete_idempotent_and_stable(tmp_path: Path) -> None:
    path = _database_path(tmp_path)
    _migrate(path)
    first = ProfileService(
        path,
        clock=_clock(),
        profile_ids=DeterministicProfileIdGenerator([JARVIS_UUID]),
    ).ensure_jarvis()
    second = ProfileService(path, clock=_clock()).ensure_jarvis()
    assert first == second
    assert first.profile.profile_id == ProfileId(JARVIS_UUID)
    assert first.profile.display_name == "Jarvis"
    assert first.profile.command_alias == "jarvis"
    assert first.configuration.configuration_revision == 1
    assert {
        section: revision.defaults_version
        for section, revision in first.configuration.section_revisions.items()
    } == dict.fromkeys(ConfigurationSection, 3)
    assert first.configuration.values.persona_text == (
        DefaultsRegistry.load_packaged().current().profile_defaults.persona_text
    )
    with SQLiteDatabase(path) as database:
        connection = database.connection()
        assert connection.execute("SELECT count(*) FROM profiles").fetchone()[0] == 1
        assert (
            connection.execute("SELECT count(*) FROM profile_configuration_sections").fetchone()[0]
            == 8
        )
        assert connection.execute("SELECT count(*) FROM profile_permissions").fetchone()[0] == 9


def test_existing_incomplete_jarvis_fails_closed_without_replacement(tmp_path: Path) -> None:
    path = _database_path(tmp_path)
    _migrate(path)
    with SQLiteDatabase(path) as database:
        database.connection().execute(
            "INSERT INTO profiles VALUES (?, 'jarvis', 'Jarvis', 1, ?, ?)",
            (
                str(JARVIS_UUID),
                "2026-08-11T12:00:00.000000Z",
                "2026-08-11T12:00:00.000000Z",
            ),
        )
    with pytest.raises(ProfileInvariantError) as caught:
        ProfileService(path, clock=_clock()).ensure_jarvis()
    assert caught.value.safe_details["reason"] == "jarvis_missing_from_nonempty_domain"
    with SQLiteDatabase(path) as database:
        rows = database.connection().execute("SELECT profile_id FROM profiles").fetchall()
    assert rows == [(str(JARVIS_UUID),)]


def test_profile_bootstrap_failure_never_publishes_initialization_marker(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    application_data = Path(env["XDG_DATA_HOME"]) / "jarvis-cli"
    application_data.mkdir(mode=0o700)
    path = application_data / "jarvis.sqlite3"
    _migrate(path)
    with SQLiteDatabase(path) as database:
        database.connection().execute(
            "INSERT INTO profiles VALUES (?, 'jarvis', 'Jarvis', 1, ?, ?)",
            (
                str(JARVIS_UUID),
                "2026-08-11T12:00:00.000000Z",
                "2026-08-11T12:00:00.000000Z",
            ),
        )
    with pytest.raises(ProfileInvariantError):
        initialize_foundation(env, clock=_clock())
    marker = Path(env["XDG_STATE_HOME"]) / "jarvis-cli" / "foundation-state.json"
    assert not marker.exists()


def test_concurrent_profile_bootstrap_publishes_one_stable_identity(tmp_path: Path) -> None:
    path = _database_path(tmp_path)
    _migrate(path)
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()

    def run(candidate: str) -> None:
        barrier.wait()
        aggregate = ProfileService(
            path,
            clock=_clock(),
            profile_ids=DeterministicProfileIdGenerator([UUID(candidate)]),
        ).ensure_jarvis()
        results.put(str(aggregate.profile.profile_id))

    candidates = [
        "10000000-0000-4000-8000-000000000010",
        "10000000-0000-4000-8000-000000000020",
    ]
    processes = [context.Process(target=run, args=(candidate,)) for candidate in candidates]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
    assert [process.exitcode for process in processes] == [0, 0]
    returned = [results.get(timeout=1), results.get(timeout=1)]
    assert returned[0] == returned[1]
    assert returned[0] in candidates


def test_injected_configuration_failure_rolls_back_new_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database_path(tmp_path)
    _migrate(path)

    def fail_insert(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("synthetic configuration failure")

    monkeypatch.setattr(
        "jarvis.profiles.repository.ProfileConfigurationRepository.insert", fail_insert
    )
    with pytest.raises(RuntimeError, match="synthetic configuration failure"):
        ProfileService(
            path,
            clock=_clock(),
            profile_ids=DeterministicProfileIdGenerator([JARVIS_UUID]),
        ).ensure_jarvis()
    with SQLiteDatabase(path) as database:
        connection = database.connection()
        assert connection.execute("SELECT count(*) FROM profiles").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM profile_aliases").fetchone()[0] == 0
