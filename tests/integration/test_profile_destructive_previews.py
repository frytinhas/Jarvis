from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from jarvis.foundation.clock import FakeClock
from jarvis.profiles.configuration import UpdateProfileConfiguration
from jarvis.profiles.destructive import (
    DeterministicOperationIdGenerator,
    ProfileDestructiveIntentService,
    ProfileOperationIntentRepository,
    ResetScope,
)
from jarvis.profiles.errors import ProfileInvariantError, ProtectedProfileError
from jarvis.profiles.models import CreateProfile, DeterministicProfileIdGenerator
from jarvis.profiles.service import ProfileConfigService, ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import MigrationRunner

pytestmark = pytest.mark.integration


def _setup(
    tmp_path: Path,
) -> tuple[Path, FakeClock, ProfileService, ProfileConfigService, ProfileDestructiveIntentService]:
    directory = tmp_path / "data" / "jarvis-cli"
    directory.mkdir(parents=True, mode=0o700)
    path = (directory / "jarvis.sqlite3").absolute()
    clock = FakeClock(datetime(2026, 8, 11, 12, tzinfo=UTC))
    with SQLiteDatabase(path) as database:
        MigrationRunner(database, clock).apply()
    profiles = ProfileService(
        path,
        clock=clock,
        profile_ids=DeterministicProfileIdGenerator(
            UUID(f"10000000-0000-4000-8000-{number:012d}") for number in range(1, 8)
        ),
    )
    configs = ProfileConfigService(path, clock=clock)
    tokens = iter(f"raw-confirmation-{number}" for number in range(1, 20))
    destructive = ProfileDestructiveIntentService(
        path,
        clock=clock,
        operation_ids=DeterministicOperationIdGenerator(
            UUID(f"20000000-0000-4000-8000-{number:012d}") for number in range(1, 20)
        ),
        token_factory=lambda: next(tokens),
    )
    return path, clock, profiles, configs, destructive


def test_reset_preview_lists_exact_fields_and_persists_only_token_digest(tmp_path: Path) -> None:
    path, _clock, profiles, configs, destructive = _setup(tmp_path)
    jarvis = profiles.ensure_jarvis()
    customized = configs.update_configuration(
        UpdateProfileConfiguration(
            jarvis.profile.profile_id,
            1,
            1,
            replace(
                jarvis.configuration.values,
                persona_text="Private persona",
                waiting_messages=("Wait",),
                start_with_computer=True,
            ),
        )
    )
    preview = destructive.preview_reset(jarvis.profile.profile_id, ResetScope.WHOLE_PROFILE)
    assert preview.expected_configuration_revision == customized.configuration_revision
    assert len(preview.items) == 19
    assert {item.key for item in preview.items} >= {
        "persona",
        "appearance.accent_color",
        "waiting-messages",
        "startup",
        "permissions.delete",
        "profile-model-associations",
    }
    assert preview.has_changes
    with SQLiteDatabase(path) as database:
        row = (
            database.connection()
            .execute(
                "SELECT token_digest_sha256, state_digest_sha256 FROM profile_operation_intents"
            )
            .fetchone()
        )
    assert row[0] == hashlib.sha256(preview.confirmation_token.encode()).hexdigest()
    assert len(row[1]) == 64
    assert preview.confirmation_token not in path.read_bytes().decode("utf-8", errors="ignore")


def test_default_section_preview_is_truthful_no_change(tmp_path: Path) -> None:
    _path, _clock, profiles, _configs, destructive = _setup(tmp_path)
    jarvis = profiles.ensure_jarvis()
    preview = destructive.preview_reset(jarvis.profile.profile_id, ResetScope.APPEARANCE)
    assert len(preview.items) == 3
    assert not preview.has_changes
    assert not any(item.will_change for item in preview.items)


def test_unsupported_message_defaults_origin_fails_closed_before_preview(tmp_path: Path) -> None:
    path, _clock, profiles, _configs, destructive = _setup(tmp_path)
    jarvis = profiles.ensure_jarvis()
    with SQLiteDatabase(path) as database:
        database.connection().execute(
            "UPDATE profile_configuration_sections SET defaults_version = 5 "
            "WHERE profile_id = ? AND section_name = 'waiting-messages'",
            (str(jarvis.profile.profile_id),),
        )
    with pytest.raises(ProfileInvariantError):
        destructive.preview_reset(jarvis.profile.profile_id, ResetScope.WAITING_MESSAGES)


def test_replacement_preview_invalidates_only_same_profile_kind_scope_tuple(
    tmp_path: Path,
) -> None:
    path, _clock, profiles, _configs, destructive = _setup(tmp_path)
    profiles.ensure_jarvis()
    profile = profiles.create_profile(CreateProfile("Work"))
    first = destructive.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
    other_scope = destructive.preview_reset(profile.profile.profile_id, ResetScope.STARTUP)
    replacement = destructive.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
    with SQLiteDatabase(path) as database:
        rows = (
            database.connection()
            .execute("SELECT operation_id, scope FROM profile_operation_intents ORDER BY scope")
            .fetchall()
        )
    assert len(rows) == 2
    assert (str(first.operation_id), ResetScope.PERSONA.value) not in rows
    assert (str(replacement.operation_id), ResetScope.PERSONA.value) in rows
    assert (str(other_scope.operation_id), ResetScope.STARTUP.value) in rows


def test_delete_preview_counts_current_rows_and_rejects_jarvis(tmp_path: Path) -> None:
    _path, _clock, profiles, configs, destructive = _setup(tmp_path)
    jarvis = profiles.ensure_jarvis()
    profile = profiles.create_profile(CreateProfile("Work"))
    configs.update_configuration(
        UpdateProfileConfiguration(
            profile.profile.profile_id,
            1,
            1,
            replace(
                profile.configuration.values,
                waiting_messages=("One", "Two"),
                goodbye_messages=("Bye",),
            ),
        )
    )
    preview = destructive.preview_delete(profile.profile.profile_id)
    counts = {item.key: item.current_count for item in preview.items}
    assert counts == {
        "identity": 1,
        "alias": 1,
        "configuration": 1,
        "configuration-sections": 8,
        "permissions": 9,
        "profile-model-associations": 0,
        "waiting-messages": 2,
        "goodbye-messages": 1,
    }
    with pytest.raises(ProtectedProfileError):
        destructive.preview_delete(jarvis.profile.profile_id)


def test_expiry_pruning_is_bounded_deterministic_and_preserves_unexpired_rows(
    tmp_path: Path,
) -> None:
    path, clock, profiles, _configs, destructive = _setup(tmp_path)
    profiles.ensure_jarvis()
    profile = profiles.create_profile(CreateProfile("Work"))
    first = destructive.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
    second = destructive.preview_reset(profile.profile.profile_id, ResetScope.STARTUP)
    clock.advance(timedelta(minutes=6))
    with SQLiteDatabase(path) as database, database.transaction(immediate=True):
        pruned = ProfileOperationIntentRepository(database.connection()).prune_expired(
            clock.now(), limit=1
        )
    assert pruned == (min(str(first.operation_id), str(second.operation_id)),)
    new_preview = destructive.preview_reset(profile.profile.profile_id, ResetScope.APPEARANCE)
    with SQLiteDatabase(path) as database:
        rows = (
            database.connection()
            .execute("SELECT operation_id FROM profile_operation_intents ORDER BY operation_id")
            .fetchall()
        )
    assert rows == [(str(new_preview.operation_id),)]
