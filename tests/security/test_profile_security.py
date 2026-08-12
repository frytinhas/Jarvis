from __future__ import annotations

import os
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from jarvis.foundation.clock import FakeClock
from jarvis.profiles.configuration import UpdateProfileConfiguration
from jarvis.profiles.destructive import ResetScope
from jarvis.profiles.errors import InvalidProfileNameError, ProfileNameConflictError
from jarvis.profiles.models import CreateProfile, DeterministicProfileIdGenerator, ProfileId
from jarvis.profiles.names import normalize_profile_name
from jarvis.profiles.service import ProfileConfigService, ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import MigrationRunner

pytestmark = pytest.mark.security


def _setup(tmp_path: Path) -> tuple[Path, ProfileService, ProfileConfigService]:
    directory = tmp_path / "isolated-data" / "jarvis-cli"
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
    profiles.ensure_jarvis()
    return path, profiles, ProfileConfigService(path, clock=clock)


@pytest.mark.parametrize(
    "value",
    [
        "../work",
        "work/profile",
        "work\\profile",
        "work;touch pwned",
        "work$(id)",
        "work`id`",
        "work\x00name",
        "work\nname",
        "work\u202ename",
        "work\u2066name",
        "work-name",
    ],
)
def test_path_shell_control_bidi_and_hyphen_input_is_rejected(value: str) -> None:
    with pytest.raises(InvalidProfileNameError):
        normalize_profile_name(value)


def test_accent_case_and_whitespace_variants_cannot_create_duplicate_aliases(
    tmp_path: Path,
) -> None:
    _path, profiles, _configs = _setup(tmp_path)
    profiles.create_profile(CreateProfile("João  Trabalho"))
    for collision in ("JOAO TRABALHO", "Joáo Trabalho", "joao   trabalho"):
        with pytest.raises(ProfileNameConflictError):
            profiles.create_profile(CreateProfile(collision))


def test_unicode_homoglyphs_never_normalize_into_reserved_jarvis_alias() -> None:
    # Cyrillic JE is not transliterated into ASCII J; it cannot acquire the protected alias.
    result = normalize_profile_name("\u0408arvis")
    assert result.command_alias == "arvis"
    assert result.command_alias != "jarvis"


def test_profile_id_and_alias_are_not_interchangeable_ownership_keys(tmp_path: Path) -> None:
    _path, profiles, configs = _setup(tmp_path)
    profile = profiles.create_profile(CreateProfile("Work"))
    with pytest.raises(ValueError):
        ProfileId.parse(profile.profile.command_alias)
    assert configs.get_configuration(profile.profile.profile_id) == profile.configuration


def test_hostile_private_text_is_parameterized_and_absent_from_safe_errors(tmp_path: Path) -> None:
    path, profiles, configs = _setup(tmp_path)
    jarvis = profiles.list_profiles()[0]
    private = "private-persona'); DROP TABLE profiles; --"
    updated = configs.update_configuration(
        UpdateProfileConfiguration(
            jarvis.profile.profile_id,
            1,
            1,
            replace(jarvis.configuration.values, persona_text=private),
        )
    )
    assert updated.values.persona_text == private
    profiles.create_profile(CreateProfile("Work"))
    with pytest.raises(ProfileNameConflictError) as caught:
        profiles.create_profile(CreateProfile("WORK"))
    assert private not in repr(caught.value.to_safe_dict())
    with SQLiteDatabase(path) as database:
        assert database.connection().execute("SELECT count(*) FROM profiles").fetchone()[0] == 2


def test_confirmation_token_and_private_configuration_never_enter_diagnostics(
    tmp_path: Path,
) -> None:
    _path, profiles, configs = _setup(tmp_path)
    profile = profiles.create_profile(CreateProfile("Work"))
    private = "private-profile-context-sentinel"
    configs.update_configuration(
        UpdateProfileConfiguration(
            profile.profile.profile_id,
            1,
            1,
            replace(profile.configuration.values, profile_context_text=private),
        )
    )
    preview = configs.preview_reset(profile.profile.profile_id, ResetScope.PROFILE_CONTEXT)
    state_root = Path(os.environ["XDG_STATE_HOME"])
    persisted = b"".join(path.read_bytes() for path in state_root.rglob("*") if path.is_file())
    assert private.encode() not in persisted
    assert preview.confirmation_token.encode() not in persisted
    assert preview.confirmation_token not in repr(preview)


def test_direct_sql_cannot_delete_or_reassign_jarvis_identity_and_alias(tmp_path: Path) -> None:
    path, profiles, _configs = _setup(tmp_path)
    jarvis = profiles.list_profiles()[0]
    with SQLiteDatabase(path) as database:
        connection = database.connection()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE profiles SET profile_kind = 'standard' WHERE profile_id = ?",
                (str(jarvis.profile.profile_id),),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE profile_aliases SET command_alias = 'other' WHERE profile_id = ?",
                (str(jarvis.profile.profile_id),),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM profiles WHERE profile_id = ?", (str(jarvis.profile.profile_id),)
            )


def test_schema_and_source_surface_contain_no_later_milestone_capabilities(tmp_path: Path) -> None:
    path, _profiles, _configs = _setup(tmp_path)
    with SQLiteDatabase(path) as database:
        tables = {
            row[0]
            for row in database.connection()
            .execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            .fetchall()
        }
    assert tables == {
        "schema_migrations",
        "profiles",
        "profile_aliases",
        "profile_configurations",
        "profile_configuration_sections",
        "profile_messages",
        "profile_permissions",
        "profile_operation_intents",
    }
    forbidden = {
        "core",
        "ipc",
        "llm",
        "models",
        "runtime",
        "tools",
        "permissions",
        "memory",
        "network",
        "tui",
        "updater",
        "installer",
    }
    package_directories = {path.name for path in Path("src/jarvis").iterdir() if path.is_dir()}
    assert package_directories.isdisjoint(forbidden)
