from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from jarvis.config.defaults import DefaultsRegistry
from jarvis.foundation.clock import FakeClock
from jarvis.profiles.configuration import UpdateProfileConfiguration
from jarvis.profiles.destructive import ConfirmDestructiveOperation, ResetScope
from jarvis.profiles.errors import (
    ConfirmationExpiredError,
    ConfirmationInvalidError,
    ConfirmationStaleError,
    ProfileNotFoundError,
)
from jarvis.profiles.models import (
    ConfigurationSection,
    CreateProfile,
    DeterministicProfileIdGenerator,
)
from jarvis.profiles.repository import ProfileConfigurationRepository, ProfileRepository
from jarvis.profiles.service import ProfileConfigService, ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.migrations import MigrationRunner

pytestmark = pytest.mark.integration


def _setup(tmp_path: Path) -> tuple[Path, FakeClock, ProfileService, ProfileConfigService]:
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
    return path, clock, profiles, ProfileConfigService(path, clock=clock)


def _confirm(preview: object) -> ConfirmDestructiveOperation:
    from jarvis.profiles.destructive import DestructivePreview

    assert isinstance(preview, DestructivePreview)
    return ConfirmDestructiveOperation(
        preview.operation_id, preview.target, preview.profile_id, preview.confirmation_token
    )


def test_section_reset_changes_only_selected_section_and_consumes_intent(tmp_path: Path) -> None:
    path, _clock, profiles, configs = _setup(tmp_path)
    profiles.ensure_jarvis()
    profile = profiles.create_profile(CreateProfile("Work"))
    customized = configs.update_configuration(
        UpdateProfileConfiguration(
            profile.profile.profile_id,
            1,
            1,
            replace(
                profile.configuration.values,
                persona_text="Custom persona",
                appearance=replace(profile.configuration.values.appearance, accent_color="#123456"),
            ),
        )
    )
    preview = configs.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
    result = configs.confirm_reset(_confirm(preview))
    defaults = DefaultsRegistry.load_packaged().current().profile_defaults
    assert result.configuration.values.persona_text == defaults.persona_text
    assert result.configuration.values.appearance.accent_color == "#123456"
    assert result.configuration.configuration_revision == customized.configuration_revision + 1
    assert result.changed_sections == (ConfigurationSection.PERSONA,)
    assert result.configuration.section_revisions[ConfigurationSection.PERSONA].revision == 3
    assert result.configuration.section_revisions[ConfigurationSection.APPEARANCE].revision == 2
    current_profile = profiles.get_profile(profile.profile.profile_id).profile
    assert current_profile.profile_id == profile.profile.profile_id
    assert current_profile.display_name == "Work"
    assert current_profile.command_alias == "work"
    with SQLiteDatabase(path) as database:
        assert (
            database.connection()
            .execute("SELECT count(*) FROM profile_operation_intents")
            .fetchone()[0]
            == 0
        )
    with pytest.raises(ConfirmationInvalidError):
        configs.confirm_reset(_confirm(preview))


def test_m006c_section_provenance_survives_upgrade_until_explicit_reset(
    tmp_path: Path,
) -> None:
    path, _clock, profiles, configs = _setup(tmp_path)
    jarvis = profiles.ensure_jarvis()
    customized = configs.update_configuration(
        UpdateProfileConfiguration(
            jarvis.profile.profile_id,
            jarvis.profile.identity_revision,
            jarvis.configuration.configuration_revision,
            replace(jarvis.configuration.values, persona_text="Persisted M006C persona"),
        )
    )

    # M006C persisted profile sections with product-default provenance v5.  This
    # fixture changes only that legacy metadata, retaining the real schema and
    # all user-owned values for the M006D read path.
    with SQLiteDatabase(path) as database:
        database.connection().execute(
            "UPDATE profile_configuration_sections SET defaults_version = 5 WHERE profile_id = ?",
            (str(jarvis.profile.profile_id),),
        )

    def persisted_profile_rows() -> tuple[
        tuple[tuple[object, ...], ...],
        tuple[tuple[object, ...], ...],
        tuple[tuple[object, ...], ...],
        tuple[tuple[object, ...], ...],
    ]:
        with SQLiteDatabase(path) as database:
            connection = database.connection()
            return (
                tuple(
                    connection.execute(
                        """
                        SELECT persona_text, profile_context_text, accent_color, foreground_color,
                               background_color, visible_logging_mode, start_with_computer
                        FROM profile_configurations WHERE profile_id = ?
                        """,
                        (str(jarvis.profile.profile_id),),
                    ).fetchall()
                ),
                tuple(
                    connection.execute(
                        """
                        SELECT section_name, defaults_version, section_revision
                        FROM profile_configuration_sections WHERE profile_id = ?
                        ORDER BY section_name
                        """,
                        (str(jarvis.profile.profile_id),),
                    ).fetchall()
                ),
                tuple(
                    connection.execute(
                        """
                        SELECT message_kind, ordinal, message_text FROM profile_messages
                        WHERE profile_id = ? ORDER BY message_kind, ordinal
                        """,
                        (str(jarvis.profile.profile_id),),
                    ).fetchall()
                ),
                tuple(
                    connection.execute(
                        """
                        SELECT capability, decision FROM profile_permissions
                        WHERE profile_id = ? ORDER BY capability
                        """,
                        (str(jarvis.profile.profile_id),),
                    ).fetchall()
                ),
            )

    persisted_before_upgrade = persisted_profile_rows()

    upgraded = profiles.ensure_jarvis()
    assert upgraded.configuration.values == customized.values
    assert {
        revision.defaults_version for revision in upgraded.configuration.section_revisions.values()
    } == {5}
    assert persisted_profile_rows() == persisted_before_upgrade

    ordinary_update = configs.update_configuration(
        UpdateProfileConfiguration(
            jarvis.profile.profile_id,
            upgraded.profile.identity_revision,
            upgraded.configuration.configuration_revision,
            replace(upgraded.configuration.values, persona_text="Updated legacy persona"),
        )
    )
    assert {
        revision.defaults_version for revision in ordinary_update.section_revisions.values()
    } == {5}

    reset = configs.confirm_reset(
        _confirm(configs.preview_reset(jarvis.profile.profile_id, ResetScope.PERSONA))
    )
    assert reset.configuration.section_revisions[ConfigurationSection.PERSONA].defaults_version == 6
    assert {
        revision.defaults_version
        for section, revision in reset.configuration.section_revisions.items()
        if section is not ConfigurationSection.PERSONA
    } == {5}

    clone = profiles.create_profile(CreateProfile("Legacy Clone"))
    assert {
        section: revision.defaults_version
        for section, revision in clone.configuration.section_revisions.items()
    } == {
        section: revision.defaults_version
        for section, revision in reset.configuration.section_revisions.items()
    }


def test_whole_reset_uses_packaged_v2_defaults_never_current_jarvis(tmp_path: Path) -> None:
    _path, _clock, profiles, configs = _setup(tmp_path)
    jarvis = profiles.ensure_jarvis()
    customized_jarvis = configs.update_configuration(
        UpdateProfileConfiguration(
            jarvis.profile.profile_id,
            1,
            1,
            replace(
                jarvis.configuration.values,
                persona_text="Mutable Jarvis persona",
                appearance=replace(jarvis.configuration.values.appearance, accent_color="#abcdef"),
            ),
        )
    )
    clone = profiles.create_profile(CreateProfile("Clone"))
    assert clone.configuration.values == customized_jarvis.values
    preview = configs.preview_reset(clone.profile.profile_id, ResetScope.WHOLE_PROFILE)
    assert preview.target_defaults_version == 6
    result = configs.confirm_reset(_confirm(preview))
    packaged = DefaultsRegistry.load_packaged().current()
    assert result.configuration.values.persona_text == packaged.profile_defaults.persona_text
    assert result.configuration.values.appearance.accent_color == "#4fc3f7"
    assert result.configuration.values != customized_jarvis.values
    assert {
        revision.defaults_version for revision in result.configuration.section_revisions.values()
    } == {6}
    assert result.profile_id == clone.profile.profile_id


def test_noop_reset_consumes_intent_without_revision_inflation(tmp_path: Path) -> None:
    _path, _clock, profiles, configs = _setup(tmp_path)
    jarvis = profiles.ensure_jarvis()
    preview = configs.preview_reset(jarvis.profile.profile_id, ResetScope.PERSONA)
    assert not preview.has_changes
    result = configs.confirm_reset(_confirm(preview))
    assert result.configuration == jarvis.configuration
    assert result.changed_sections == ()
    with pytest.raises(ConfirmationInvalidError):
        configs.confirm_reset(_confirm(preview))


def test_delete_cascades_all_current_rows_and_returns_alias_reconciliation(tmp_path: Path) -> None:
    path, _clock, profiles, configs = _setup(tmp_path)
    profiles.ensure_jarvis()
    profile = profiles.create_profile(CreateProfile("Work"))
    configs.update_configuration(
        UpdateProfileConfiguration(
            profile.profile.profile_id,
            1,
            1,
            replace(profile.configuration.values, waiting_messages=("Wait",)),
        )
    )
    preview = profiles.preview_delete(profile.profile.profile_id)
    result = profiles.confirm_delete(_confirm(preview))
    assert result.alias_change.old_alias == "work"
    assert result.alias_change.new_alias is None
    with pytest.raises(ProfileNotFoundError):
        profiles.get_profile(profile.profile.profile_id)
    with SQLiteDatabase(path) as database:
        connection = database.connection()
        for table in (
            "profiles",
            "profile_aliases",
            "profile_configurations",
            "profile_configuration_sections",
            "profile_messages",
            "profile_permissions",
            "profile_operation_intents",
        ):
            assert (
                connection.execute(
                    f"SELECT count(*) FROM {table} WHERE profile_id = ?",
                    (str(profile.profile.profile_id),),
                ).fetchone()[0]
                == 0
            )


def test_forged_expired_replaced_and_stale_confirmations_fail_deterministically(
    tmp_path: Path,
) -> None:
    _path, clock, profiles, configs = _setup(tmp_path)
    profiles.ensure_jarvis()
    profile = profiles.create_profile(CreateProfile("Work"))

    forged_preview = configs.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
    forged = replace(_confirm(forged_preview), confirmation_token="forged")
    with pytest.raises(ConfirmationInvalidError):
        configs.confirm_reset(forged)
    configs.confirm_reset(_confirm(forged_preview))

    expired_preview = configs.preview_reset(profile.profile.profile_id, ResetScope.STARTUP)
    clock.advance(timedelta(minutes=5))
    with pytest.raises(ConfirmationExpiredError):
        configs.confirm_reset(_confirm(expired_preview))

    replacement = configs.preview_reset(profile.profile.profile_id, ResetScope.APPEARANCE)
    replaced = configs.preview_reset(profile.profile.profile_id, ResetScope.APPEARANCE)
    with pytest.raises(ConfirmationInvalidError):
        configs.confirm_reset(_confirm(replacement))

    current = configs.get_configuration(profile.profile.profile_id)
    stale_preview = configs.preview_reset(profile.profile.profile_id, ResetScope.PROFILE_CONTEXT)
    configs.update_configuration(
        UpdateProfileConfiguration(
            profile.profile.profile_id,
            1,
            current.configuration_revision,
            replace(current.values, profile_context_text="Mutated"),
        )
    )
    with pytest.raises(ConfirmationStaleError):
        configs.confirm_reset(_confirm(stale_preview))
    assert replaced.operation_id != replacement.operation_id


def test_direct_state_change_without_revision_is_detected_by_digest(tmp_path: Path) -> None:
    path, _clock, profiles, configs = _setup(tmp_path)
    profiles.ensure_jarvis()
    profile = profiles.create_profile(CreateProfile("Work"))
    preview = configs.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
    with SQLiteDatabase(path) as database:
        database.connection().execute(
            "UPDATE profile_configurations SET persona_text = ? WHERE profile_id = ?",
            ("Direct mutation", str(profile.profile.profile_id)),
        )
    with pytest.raises(ConfirmationStaleError) as caught:
        configs.confirm_reset(_confirm(preview))
    assert caught.value.safe_details["reason"] == "state_mismatch"


def test_reset_failure_rolls_back_changes_and_intent_consumption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _clock, profiles, configs = _setup(tmp_path)
    profiles.ensure_jarvis()
    profile = profiles.create_profile(CreateProfile("Work"))
    customized = configs.update_configuration(
        UpdateProfileConfiguration(
            profile.profile.profile_id,
            1,
            1,
            replace(profile.configuration.values, persona_text="Custom"),
        )
    )
    preview = configs.preview_reset(profile.profile.profile_id, ResetScope.PERSONA)
    original = ProfileConfigurationRepository.update

    def fail_after_update(self: ProfileConfigurationRepository, **kwargs: object) -> bool:
        original(self, **kwargs)  # type: ignore[arg-type]
        raise RuntimeError("synthetic reset failure")

    monkeypatch.setattr(ProfileConfigurationRepository, "update", fail_after_update)
    with pytest.raises(RuntimeError, match="synthetic reset failure"):
        configs.confirm_reset(_confirm(preview))
    assert configs.get_configuration(profile.profile.profile_id) == customized
    with SQLiteDatabase(path) as database:
        assert (
            database.connection()
            .execute(
                "SELECT count(*) FROM profile_operation_intents WHERE operation_id = ?",
                (str(preview.operation_id),),
            )
            .fetchone()[0]
            == 1
        )


def test_delete_failure_rolls_back_cascade_and_preserves_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _clock, profiles, _configs = _setup(tmp_path)
    profiles.ensure_jarvis()
    profile = profiles.create_profile(CreateProfile("Work"))
    preview = profiles.preview_delete(profile.profile.profile_id)
    original = ProfileRepository.delete

    def fail_after_delete(self: ProfileRepository, profile_id: object) -> bool:
        result = original(self, profile_id)  # type: ignore[arg-type]
        assert result
        raise RuntimeError("synthetic delete failure")

    monkeypatch.setattr(ProfileRepository, "delete", fail_after_delete)
    with pytest.raises(RuntimeError, match="synthetic delete failure"):
        profiles.confirm_delete(_confirm(preview))
    assert profiles.get_profile(profile.profile.profile_id) == profile
    with SQLiteDatabase(path) as database:
        assert (
            database.connection()
            .execute(
                "SELECT count(*) FROM profile_operation_intents WHERE operation_id = ?",
                (str(preview.operation_id),),
            )
            .fetchone()[0]
            == 1
        )
