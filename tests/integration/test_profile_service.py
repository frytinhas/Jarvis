from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from jarvis.foundation.clock import FakeClock
from jarvis.profiles.errors import (
    ConcurrentProfileModificationError,
    InvalidProfileNameError,
    ProfileNameConflictError,
    ProtectedProfileError,
)
from jarvis.profiles.models import (
    CreateProfile,
    DeterministicProfileIdGenerator,
    RenameProfile,
)
from jarvis.profiles.service import ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import MigrationRunner

pytestmark = pytest.mark.integration


def _service(tmp_path: Path) -> ProfileService:
    directory = tmp_path / "data" / "jarvis-cli"
    directory.mkdir(parents=True, mode=0o700)
    path = (directory / "jarvis.sqlite3").absolute()
    clock = FakeClock(datetime(2026, 8, 11, 12, tzinfo=UTC))
    with SQLiteDatabase(path) as database:
        MigrationRunner(database, clock).apply()
    return ProfileService(
        path,
        clock=clock,
        profile_ids=DeterministicProfileIdGenerator(
            [
                UUID("10000000-0000-4000-8000-000000000001"),
                UUID("10000000-0000-4000-8000-000000000002"),
                UUID("10000000-0000-4000-8000-000000000003"),
                UUID("10000000-0000-4000-8000-000000000004"),
            ]
        ),
    )


def test_create_list_get_and_rename_preserve_stable_identity_and_configuration(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    jarvis = service.ensure_jarvis()
    created = service.create_profile(CreateProfile("João Trabalho"))
    assert created.profile.command_alias == "joao-trabalho"
    assert created.configuration.values == jarvis.configuration.values
    assert created.profile.profile_id != jarvis.profile.profile_id
    assert service.get_profile(created.profile.profile_id) == created
    assert service.list_profiles() == (jarvis, created)

    renamed = service.rename_profile(RenameProfile(created.profile.profile_id, "Work Profile", 1))
    assert renamed.profile.profile_id == created.profile.profile_id
    assert renamed.profile.command_alias == "work-profile"
    assert renamed.profile.identity_revision == 2
    assert renamed.alias_change.old_alias == "joao-trabalho"
    assert renamed.alias_change.new_alias == "work-profile"
    assert service.get_profile(created.profile.profile_id).configuration == created.configuration


@pytest.mark.parametrize("name", ["Jarvis", "JÁRVIS", "jarvis config", "jarvisd"])
def test_creation_rejects_reserved_aliases(tmp_path: Path, name: str) -> None:
    service = _service(tmp_path)
    service.ensure_jarvis()
    with pytest.raises(ProfileNameConflictError) as caught:
        service.create_profile(CreateProfile(name))
    assert caught.value.safe_details["reason"] == "reserved_alias"


def test_creation_rejects_alias_collision_after_accent_case_and_space_normalization(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.ensure_jarvis()
    service.create_profile(CreateProfile("João  Trabalho"))
    with pytest.raises(ProfileNameConflictError):
        service.create_profile(CreateProfile("JOAO TRABALHO"))


def test_display_name_hyphen_is_rejected_before_database_write(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ensure_jarvis()
    with pytest.raises(InvalidProfileNameError):
        service.create_profile(CreateProfile("Work-Profile"))
    assert len(service.list_profiles()) == 1


def test_jarvis_rename_is_always_rejected(tmp_path: Path) -> None:
    service = _service(tmp_path)
    jarvis = service.ensure_jarvis()
    with pytest.raises(ProtectedProfileError):
        service.rename_profile(RenameProfile(jarvis.profile.profile_id, "Other", 1))
    assert service.get_profile(jarvis.profile.profile_id) == jarvis


def test_rename_requires_expected_revision_and_conflict_free_alias(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ensure_jarvis()
    first = service.create_profile(CreateProfile("First"))
    second = service.create_profile(CreateProfile("Second"))
    service.rename_profile(RenameProfile(first.profile.profile_id, "Renamed", 1))
    with pytest.raises(ConcurrentProfileModificationError):
        service.rename_profile(RenameProfile(first.profile.profile_id, "Again", 1))
    with pytest.raises(ProfileNameConflictError):
        service.rename_profile(RenameProfile(second.profile.profile_id, "Renamed", 1))


def test_exact_noop_rename_does_not_increment_revision(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.ensure_jarvis()
    created = service.create_profile(CreateProfile("Work"))
    result = service.rename_profile(RenameProfile(created.profile.profile_id, "Work", 1))
    assert result.profile.identity_revision == 1
    assert service.get_profile(created.profile.profile_id).profile.identity_revision == 1
