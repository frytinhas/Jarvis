from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from jarvis.foundation.clock import FakeClock
from jarvis.profiles.configuration import UpdateProfileConfiguration
from jarvis.profiles.errors import ConcurrentProfileModificationError
from jarvis.profiles.models import (
    Capability,
    ConfigurationSection,
    CreateProfile,
    DeterministicProfileIdGenerator,
    PermissionDecision,
    RenameProfile,
    VisibleLoggingMode,
)
from jarvis.profiles.service import ProfileConfigService, ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import MigrationRunner

pytestmark = pytest.mark.integration


def _services(tmp_path: Path) -> tuple[ProfileService, ProfileConfigService]:
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
    return profiles, ProfileConfigService(path, clock=clock)


def test_single_and_multi_section_updates_increment_exact_revisions(tmp_path: Path) -> None:
    profiles, configurations = _services(tmp_path)
    jarvis = profiles.ensure_jarvis()
    initial = jarvis.configuration
    persona_values = replace(initial.values, persona_text="Updated persona")
    first = configurations.update_configuration(
        UpdateProfileConfiguration(jarvis.profile.profile_id, 1, 1, persona_values)
    )
    assert first.configuration_revision == 2
    assert first.section_revisions[ConfigurationSection.PERSONA].revision == 2
    assert all(
        revision.revision == 1
        for section, revision in first.section_revisions.items()
        if section is not ConfigurationSection.PERSONA
    )

    permissions = dict(first.values.permissions)
    permissions[Capability.READ] = PermissionDecision.DENY
    multi_values = replace(
        first.values,
        waiting_messages=("Please wait", "Still working"),
        visible_logging_mode=VisibleLoggingMode.FULL,
        permissions=permissions,
    )
    second = configurations.update_configuration(
        UpdateProfileConfiguration(jarvis.profile.profile_id, 1, 2, multi_values)
    )
    assert second.configuration_revision == 3
    for section in (
        ConfigurationSection.WAITING_MESSAGES,
        ConfigurationSection.VISIBLE_LOGGING,
        ConfigurationSection.PERMISSIONS,
    ):
        assert second.section_revisions[section].revision == 2
    assert second.section_revisions[ConfigurationSection.PERSONA].revision == 2


def test_exact_configuration_noop_does_not_increment_any_revision(tmp_path: Path) -> None:
    profiles, configurations = _services(tmp_path)
    jarvis = profiles.ensure_jarvis()
    unchanged = configurations.update_configuration(
        UpdateProfileConfiguration(
            jarvis.profile.profile_id,
            jarvis.profile.identity_revision,
            jarvis.configuration.configuration_revision,
            jarvis.configuration.values,
        )
    )
    assert unchanged == jarvis.configuration


def test_updates_require_both_identity_and_configuration_revisions(tmp_path: Path) -> None:
    profiles, configurations = _services(tmp_path)
    profiles.ensure_jarvis()
    created = profiles.create_profile(CreateProfile("Work"))
    renamed = profiles.rename_profile(RenameProfile(created.profile.profile_id, "Office", 1))
    changed_values = replace(created.configuration.values, persona_text="Changed")
    with pytest.raises(ConcurrentProfileModificationError) as identity_error:
        configurations.update_configuration(
            UpdateProfileConfiguration(created.profile.profile_id, 1, 1, changed_values)
        )
    assert identity_error.value.safe_details["reason"] == "identity_revision_mismatch"
    first = configurations.update_configuration(
        UpdateProfileConfiguration(
            created.profile.profile_id, renamed.profile.identity_revision, 1, changed_values
        )
    )
    with pytest.raises(ConcurrentProfileModificationError) as config_error:
        configurations.update_configuration(
            UpdateProfileConfiguration(
                created.profile.profile_id,
                renamed.profile.identity_revision,
                1,
                replace(first.values, persona_text="Again"),
            )
        )
    assert config_error.value.safe_details["reason"] == "configuration_revision_mismatch"


def test_creation_clones_complete_current_jarvis_configuration_only(tmp_path: Path) -> None:
    profiles, configurations = _services(tmp_path)
    jarvis = profiles.ensure_jarvis()
    permissions = dict(jarvis.configuration.values.permissions)
    permissions[Capability.DELETE] = PermissionDecision.DENY
    customized_values = replace(
        jarvis.configuration.values,
        persona_text="Private ' persona; DROP TABLE profiles; --",
        profile_context_text="Context",
        waiting_messages=("Wait",),
        goodbye_messages=("Goodbye",),
        visible_logging_mode=VisibleLoggingMode.NONE,
        start_with_computer=True,
        permissions=permissions,
    )
    customized = configurations.update_configuration(
        UpdateProfileConfiguration(jarvis.profile.profile_id, 1, 1, customized_values)
    )
    clone = profiles.create_profile(CreateProfile("Clone"))
    assert clone.configuration.values == customized.values
    assert clone.configuration.configuration_revision == 1
    assert all(
        revision.revision == 1 for revision in clone.configuration.section_revisions.values()
    )
    assert {
        revision.defaults_version for revision in clone.configuration.section_revisions.values()
    } == {5}
    assert profiles.get_profile(jarvis.profile.profile_id).configuration == customized

    configurations.update_configuration(
        UpdateProfileConfiguration(
            jarvis.profile.profile_id,
            1,
            customized.configuration_revision,
            replace(customized.values, profile_context_text="Later change"),
        )
    )
    assert configurations.get_configuration(clone.profile.profile_id) == clone.configuration


def test_configuration_reads_are_profile_id_scoped_and_sections_are_typed(tmp_path: Path) -> None:
    profiles, configurations = _services(tmp_path)
    profiles.ensure_jarvis()
    first = profiles.create_profile(CreateProfile("First"))
    second = profiles.create_profile(CreateProfile("Second"))
    first_values = replace(first.configuration.values, profile_context_text="First only")
    configurations.update_configuration(
        UpdateProfileConfiguration(first.profile.profile_id, 1, 1, first_values)
    )
    assert configurations.get_configuration(second.profile.profile_id) == second.configuration
    section = configurations.get_section(
        first.profile.profile_id, ConfigurationSection.PROFILE_CONTEXT
    )
    assert section.profile_id == first.profile.profile_id
    assert section.value == "First only"
    assert section.revision.revision == 2
