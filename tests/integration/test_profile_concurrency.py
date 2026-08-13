from __future__ import annotations

import multiprocessing
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty
from typing import Any
from uuid import UUID

import pytest

from jarvis.foundation.clock import FakeClock
from jarvis.profiles.configuration import UpdateProfileConfiguration
from jarvis.profiles.destructive import (
    ConfirmDestructiveOperation,
    ProfileDestructiveCoordinator,
    ProfileDestructiveIntentService,
    ResetScope,
)
from jarvis.profiles.errors import DatabaseBusyError, ProfileError
from jarvis.profiles.models import CreateProfile, DeterministicProfileIdGenerator, RenameProfile
from jarvis.profiles.service import ProfileConfigService, ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import MigrationRunner

pytestmark = pytest.mark.integration
TEST_NOW = datetime(2026, 8, 11, 12, tzinfo=UTC)


def _setup(tmp_path: Path) -> tuple[Path, ProfileService, ProfileConfigService]:
    directory = tmp_path / "data" / "jarvis-cli"
    directory.mkdir(parents=True, mode=0o700)
    path = (directory / "jarvis.sqlite3").absolute()
    clock = FakeClock(TEST_NOW)
    with SQLiteDatabase(path) as database:
        MigrationRunner(database, clock).apply()
    profiles = ProfileService(
        path,
        clock=clock,
        profile_ids=DeterministicProfileIdGenerator(
            UUID(f"10000000-0000-4000-8000-{number:012d}") for number in range(1, 10)
        ),
    )
    profiles.ensure_jarvis()
    return path, profiles, ProfileConfigService(path, clock=clock)


def _outcomes(queue: Any, count: int = 2) -> list[Any]:
    values: list[Any] = []
    for _ in range(count):
        try:
            values.append(queue.get(timeout=2))
        except Empty as error:
            raise AssertionError("child process did not report an outcome") from error
    return values


def test_simultaneous_alias_colliding_creates_have_one_winner(tmp_path: Path) -> None:
    path, _profiles, _configs = _setup(tmp_path)
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    queue = context.Queue()

    def run(name: str) -> None:
        barrier.wait()
        try:
            ProfileService(path).create_profile(CreateProfile(name))
            queue.put("created")
        except ProfileError as error:
            queue.put(error.code)

    processes = [
        context.Process(target=run, args=("João Trabalho",)),
        context.Process(target=run, args=("JOAO TRABALHO",)),
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
    assert [process.exitcode for process in processes] == [0, 0]
    assert sorted(_outcomes(queue)) == ["created", "profile.name_conflict"]


def test_rename_vs_rename_has_one_expected_revision_winner(tmp_path: Path) -> None:
    path, profiles, _configs = _setup(tmp_path)
    profile = profiles.create_profile(CreateProfile("Original"))
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    queue = context.Queue()

    def run(name: str) -> None:
        barrier.wait()
        try:
            ProfileService(path).rename_profile(RenameProfile(profile.profile.profile_id, name, 1))
            queue.put("renamed")
        except ProfileError as error:
            queue.put(error.code)

    processes = [context.Process(target=run, args=(name,)) for name in ("First", "Second")]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
    assert [process.exitcode for process in processes] == [0, 0]
    assert sorted(_outcomes(queue)) == ["profile.concurrent_modification", "renamed"]


def test_rename_and_create_alias_collision_has_one_winner(tmp_path: Path) -> None:
    path, profiles, _configs = _setup(tmp_path)
    profile = profiles.create_profile(CreateProfile("Original"))
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    queue = context.Queue()

    def rename() -> None:
        barrier.wait()
        try:
            ProfileService(path).rename_profile(
                RenameProfile(profile.profile.profile_id, "Target", 1)
            )
            queue.put("winner")
        except ProfileError as error:
            queue.put(error.code)

    def create() -> None:
        barrier.wait()
        try:
            ProfileService(path).create_profile(CreateProfile("Target"))
            queue.put("winner")
        except ProfileError as error:
            queue.put(error.code)

    processes = [context.Process(target=rename), context.Process(target=create)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
    assert [process.exitcode for process in processes] == [0, 0]
    assert sorted(_outcomes(queue)) == ["profile.name_conflict", "winner"]


def test_rename_vs_confirmed_delete_revalidates_after_write_ownership(tmp_path: Path) -> None:
    path, profiles, _configs = _setup(tmp_path)
    profile = profiles.create_profile(CreateProfile("Work"))
    preview = profiles.preview_delete(profile.profile.profile_id)
    command = ConfirmDestructiveOperation(
        preview.operation_id, preview.target, preview.profile_id, preview.confirmation_token
    )
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    queue = context.Queue()

    def rename() -> None:
        barrier.wait()
        try:
            ProfileService(path).rename_profile(
                RenameProfile(profile.profile.profile_id, "Renamed", 1)
            )
            queue.put("renamed")
        except ProfileError as error:
            queue.put(error.code)

    def delete() -> None:
        barrier.wait()
        try:
            ProfileService(path, clock=FakeClock(TEST_NOW)).confirm_delete(command)
            queue.put("deleted")
        except ProfileError as error:
            queue.put(error.code)

    processes = [context.Process(target=rename), context.Process(target=delete)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
    assert [process.exitcode for process in processes] == [0, 0]
    outcomes = _outcomes(queue)
    assert ("renamed" in outcomes) != ("deleted" in outcomes)
    assert any(
        value.startswith("profile.") for value in outcomes if value not in {"renamed", "deleted"}
    )


def test_reset_vs_confirmed_delete_cannot_both_commit(tmp_path: Path) -> None:
    path, profiles, configs = _setup(tmp_path)
    profile = profiles.create_profile(CreateProfile("Work"))
    customized = configs.update_configuration(
        UpdateProfileConfiguration(
            profile.profile.profile_id,
            1,
            1,
            replace(profile.configuration.values, persona_text="Custom"),
        )
    )
    reset_preview = configs.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
    delete_preview = profiles.preview_delete(profile.profile.profile_id)
    reset_command = ConfirmDestructiveOperation(
        reset_preview.operation_id,
        reset_preview.target,
        reset_preview.profile_id,
        reset_preview.confirmation_token,
    )
    delete_command = ConfirmDestructiveOperation(
        delete_preview.operation_id,
        delete_preview.target,
        delete_preview.profile_id,
        delete_preview.confirmation_token,
    )
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    queue = context.Queue()

    def reset() -> None:
        barrier.wait()
        try:
            ProfileConfigService(path, clock=FakeClock(TEST_NOW)).confirm_reset(reset_command)
            queue.put("reset")
        except ProfileError as error:
            queue.put(error.code)

    def delete() -> None:
        barrier.wait()
        try:
            ProfileService(path, clock=FakeClock(TEST_NOW)).confirm_delete(delete_command)
            queue.put("deleted")
        except ProfileError as error:
            queue.put(error.code)

    processes = [context.Process(target=reset), context.Process(target=delete)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
    assert [process.exitcode for process in processes] == [0, 0]
    outcomes = _outcomes(queue)
    assert ("reset" in outcomes) != ("deleted" in outcomes)
    if "reset" in outcomes:
        assert configs.get_configuration(profile.profile.profile_id) != customized


def test_confirmation_replay_race_allows_exactly_one_commit(tmp_path: Path) -> None:
    path, profiles, configs = _setup(tmp_path)
    profile = profiles.create_profile(CreateProfile("Work"))
    preview = configs.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
    command = ConfirmDestructiveOperation(
        preview.operation_id, preview.target, preview.profile_id, preview.confirmation_token
    )
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    queue = context.Queue()

    def run() -> None:
        barrier.wait()
        try:
            ProfileConfigService(path, clock=FakeClock(TEST_NOW)).confirm_reset(command)
            queue.put("confirmed")
        except ProfileError as error:
            queue.put(error.code)

    processes = [context.Process(target=run) for _ in range(2)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
    assert [process.exitcode for process in processes] == [0, 0]
    assert sorted(_outcomes(queue)) == ["confirmed", "profile.confirmation_invalid"]


def test_jarvis_update_during_clone_is_never_a_mixed_snapshot(tmp_path: Path) -> None:
    path, profiles, configs = _setup(tmp_path)
    jarvis = profiles.get_profile(profiles.list_profiles()[0].profile.profile_id)
    before = (
        jarvis.configuration.values.persona_text,
        jarvis.configuration.values.appearance.accent_color,
        jarvis.configuration.values.waiting_messages,
    )
    after_values = replace(
        jarvis.configuration.values,
        persona_text="Post-update persona",
        appearance=replace(jarvis.configuration.values.appearance, accent_color="#123456"),
        waiting_messages=("Post update",),
    )
    after = (
        after_values.persona_text,
        after_values.appearance.accent_color,
        after_values.waiting_messages,
    )
    command = UpdateProfileConfiguration(jarvis.profile.profile_id, 1, 1, after_values)
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    queue = context.Queue()

    def update() -> None:
        barrier.wait()
        ProfileConfigService(path).update_configuration(command)
        queue.put("updated")

    def clone() -> None:
        barrier.wait()
        created = ProfileService(path).create_profile(CreateProfile("Clone"))
        values = created.configuration.values
        queue.put((values.persona_text, values.appearance.accent_color, values.waiting_messages))

    processes = [context.Process(target=update), context.Process(target=clone)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
    assert [process.exitcode for process in processes] == [0, 0]
    outcomes = _outcomes(queue)
    clone_snapshot = next(value for value in outcomes if value != "updated")
    assert clone_snapshot in {before, after}


def test_busy_timeout_exhaustion_is_typed_without_automatic_retry(tmp_path: Path) -> None:
    path, profiles, _configs = _setup(tmp_path)
    profile = profiles.create_profile(CreateProfile("Busy Preview"))
    intent_service = ProfileDestructiveIntentService(
        path, clock=FakeClock(TEST_NOW), busy_timeout_ms=25
    )
    preview = intent_service.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
    confirmation = ConfirmDestructiveOperation(
        preview.operation_id, preview.target, preview.profile_id, preview.confirmation_token
    )
    with SQLiteDatabase(path) as blocker, blocker.transaction(immediate=True):
        service = ProfileService(path, busy_timeout_ms=25)
        with pytest.raises(DatabaseBusyError) as caught:
            service.create_profile(CreateProfile("Blocked"))
        with pytest.raises(DatabaseBusyError) as destructive_caught:
            service.preview_delete(profile.profile.profile_id)
        with pytest.raises(DatabaseBusyError) as direct_internal_caught:
            intent_service.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
        with pytest.raises(DatabaseBusyError) as direct_coordinator_caught:
            ProfileDestructiveCoordinator(
                path, clock=FakeClock(TEST_NOW), busy_timeout_ms=25
            ).confirm_reset(confirmation)
    assert caught.value.code == "database.busy"
    assert destructive_caught.value.code == "database.busy"
    assert direct_internal_caught.value.code == "database.busy"
    assert direct_coordinator_caught.value.code == "database.busy"
