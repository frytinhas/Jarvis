"""Application services for stable profile identity and lifecycle operations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from jarvis.config.defaults import DefaultsRegistry
from jarvis.foundation.clock import Clock, SystemClock
from jarvis.profiles.configuration import (
    ProfileAggregate,
    ProfileConfiguration,
    ProfileConfigurationSectionSnapshot,
    ProfileConfigurationValues,
    UpdateProfileConfiguration,
    section_value,
)
from jarvis.profiles.destructive import (
    ConfirmDestructiveOperation,
    DeleteProfileResult,
    DestructivePreview,
    ProfileDestructiveCoordinator,
    ProfileDestructiveIntentService,
    ResetProfileResult,
    ResetScope,
)
from jarvis.profiles.errors import (
    ConcurrentProfileModificationError,
    ProfileError,
    ProfileInvariantError,
    ProfileNameConflictError,
    ProtectedProfileError,
    translate_profile_database_error,
)
from jarvis.profiles.models import (
    AliasChange,
    AliasChangeKind,
    ConfigurationSection,
    CreateProfile,
    ProfileId,
    ProfileIdGenerator,
    ProfileKind,
    RandomProfileIdGenerator,
    RenameProfile,
    RenameResult,
)
from jarvis.profiles.names import is_reserved_alias, normalize_profile_name
from jarvis.profiles.repository import ProfileConfigurationRepository, ProfileRepository
from jarvis.storage.database import SQLiteDatabase


class ProfileService:
    """Profile-domain service; each public call owns one database connection."""

    def __init__(
        self,
        database_path: Path,
        *,
        defaults: DefaultsRegistry | None = None,
        clock: Clock | None = None,
        profile_ids: ProfileIdGenerator | None = None,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        self._database_path = database_path
        self._defaults = DefaultsRegistry.load_packaged() if defaults is None else defaults
        self._clock = SystemClock() if clock is None else clock
        self._profile_ids = RandomProfileIdGenerator() if profile_ids is None else profile_ids
        self._busy_timeout_ms = busy_timeout_ms

    def ensure_jarvis(self) -> ProfileAggregate:
        """Create Jarvis once or verify its complete persisted invariant set."""

        defaults = self._defaults.current()
        try:
            with (
                SQLiteDatabase(
                    self._database_path, busy_timeout_ms=self._busy_timeout_ms
                ) as database,
                database.transaction(immediate=True),
            ):
                connection = database.connection()
                identities = ProfileRepository(connection)
                configurations = ProfileConfigurationRepository(connection)
                jarvis = identities.find_jarvis()
                if jarvis is None:
                    if identities.has_any_domain_state():
                        raise ProfileInvariantError(
                            safe_details={"reason": "jarvis_missing_from_nonempty_domain"}
                        )
                    now = self._clock.now()
                    jarvis = identities.insert(
                        profile_id=self._profile_ids.new_profile_id(),
                        kind=ProfileKind.JARVIS,
                        display_name="Jarvis",
                        command_alias="jarvis",
                        timestamp_utc=now,
                    )
                    configuration = configurations.insert(
                        profile_id=jarvis.profile_id,
                        values=ProfileConfigurationValues.from_defaults(defaults.profile_defaults),
                        defaults_versions={
                            section: defaults.product_defaults_version
                            for section in ConfigurationSection
                        },
                        timestamp_utc=now,
                    )
                else:
                    if jarvis.display_name != "Jarvis" or jarvis.command_alias != "jarvis":
                        raise ProfileInvariantError(
                            safe_details={"reason": "invalid_jarvis_identity"}
                        )
                    configuration = configurations.get(jarvis.profile_id)
        except ProfileError:
            raise
        except sqlite3.Error as error:
            raise translate_profile_database_error(
                error, reason="bootstrap_database_failure"
            ) from error
        return ProfileAggregate(jarvis, configuration)

    def list_profiles(self) -> tuple[ProfileAggregate, ...]:
        try:
            with (
                SQLiteDatabase(
                    self._database_path, busy_timeout_ms=self._busy_timeout_ms
                ) as database,
                database.transaction(immediate=False),
            ):
                identities = ProfileRepository(database.connection())
                configurations = ProfileConfigurationRepository(database.connection())
                return tuple(
                    ProfileAggregate(profile, configurations.get(profile.profile_id))
                    for profile in identities.list()
                )
        except ProfileError:
            raise
        except sqlite3.Error as error:
            raise translate_profile_database_error(error, reason="list_database_failure") from error

    def get_profile(self, profile_id: ProfileId) -> ProfileAggregate:
        try:
            with (
                SQLiteDatabase(
                    self._database_path, busy_timeout_ms=self._busy_timeout_ms
                ) as database,
                database.transaction(immediate=False),
            ):
                identities = ProfileRepository(database.connection())
                profile = identities.get(profile_id)
                configuration = ProfileConfigurationRepository(database.connection()).get(
                    profile_id
                )
                return ProfileAggregate(profile, configuration)
        except ProfileError:
            raise
        except sqlite3.Error as error:
            raise translate_profile_database_error(error, reason="get_database_failure") from error

    def resolve_alias(self, command_alias: str) -> ProfileAggregate:
        """Resolve an already-canonical logical alias to its stable profile aggregate."""

        try:
            with (
                SQLiteDatabase(
                    self._database_path, busy_timeout_ms=self._busy_timeout_ms
                ) as database,
                database.transaction(immediate=False),
            ):
                identities = ProfileRepository(database.connection())
                owner = identities.alias_owner(command_alias)
                if owner is None:
                    from jarvis.profiles.errors import ProfileNotFoundError

                    raise ProfileNotFoundError(safe_details={"reason": "alias_not_found"})
                configuration = ProfileConfigurationRepository(database.connection()).get(owner)
                return ProfileAggregate(identities.get(owner), configuration)
        except ProfileError:
            raise
        except sqlite3.Error as error:
            raise translate_profile_database_error(
                error, reason="resolve_alias_database_failure"
            ) from error

    def create_profile(self, command: CreateProfile) -> ProfileAggregate:
        normalized = normalize_profile_name(command.display_name)
        if is_reserved_alias(normalized.command_alias):
            raise ProfileNameConflictError(safe_details={"reason": "reserved_alias"})
        try:
            with (
                SQLiteDatabase(
                    self._database_path, busy_timeout_ms=self._busy_timeout_ms
                ) as database,
                database.transaction(immediate=True),
            ):
                connection = database.connection()
                identities = ProfileRepository(connection)
                configurations = ProfileConfigurationRepository(connection)
                jarvis = identities.find_jarvis()
                if jarvis is None:
                    raise ProfileInvariantError(safe_details={"reason": "jarvis_missing"})
                jarvis_configuration = configurations.get(jarvis.profile_id)
                if identities.alias_owner(normalized.command_alias) is not None:
                    raise ProfileNameConflictError(safe_details={"reason": "alias_conflict"})
                now = self._clock.now()
                profile_id = self._profile_ids.new_profile_id()
                if identities.exists(profile_id):
                    raise ProfileInvariantError(safe_details={"reason": "profile_id_collision"})
                profile = identities.insert(
                    profile_id=profile_id,
                    kind=ProfileKind.STANDARD,
                    display_name=normalized.display_name,
                    command_alias=normalized.command_alias,
                    timestamp_utc=now,
                )
                configuration = configurations.insert(
                    profile_id=profile.profile_id,
                    values=jarvis_configuration.values,
                    defaults_versions={
                        section: jarvis_configuration.section_revisions[section].defaults_version
                        for section in ConfigurationSection
                    },
                    timestamp_utc=now,
                )
                return ProfileAggregate(profile, configuration)
        except ProfileError:
            raise
        except sqlite3.IntegrityError as error:
            raise ProfileNameConflictError(
                safe_details={"reason": "alias_conflict"}, internal_message=str(error)
            ) from error
        except sqlite3.Error as error:
            raise translate_profile_database_error(
                error, reason="create_database_failure"
            ) from error

    def rename_profile(self, command: RenameProfile) -> RenameResult:
        normalized = normalize_profile_name(command.display_name)
        if is_reserved_alias(normalized.command_alias):
            raise ProfileNameConflictError(safe_details={"reason": "reserved_alias"})
        try:
            with (
                SQLiteDatabase(
                    self._database_path, busy_timeout_ms=self._busy_timeout_ms
                ) as database,
                database.transaction(immediate=True),
            ):
                identities = ProfileRepository(database.connection())
                current = identities.get(command.profile_id)
                if current.kind is ProfileKind.JARVIS:
                    raise ProtectedProfileError(safe_details={"operation": "rename"})
                if current.identity_revision != command.expected_identity_revision:
                    raise ConcurrentProfileModificationError(
                        safe_details={"reason": "identity_revision_mismatch"}
                    )
                owner = identities.alias_owner(normalized.command_alias)
                if owner is not None and owner != command.profile_id:
                    raise ProfileNameConflictError(safe_details={"reason": "alias_conflict"})
                if (
                    current.display_name == normalized.display_name
                    and current.command_alias == normalized.command_alias
                ):
                    updated = current
                else:
                    changed = identities.rename(
                        profile_id=command.profile_id,
                        display_name=normalized.display_name,
                        command_alias=normalized.command_alias,
                        expected_identity_revision=command.expected_identity_revision,
                        timestamp_utc=self._clock.now(),
                    )
                    if not changed:
                        raise ConcurrentProfileModificationError(
                            safe_details={"reason": "identity_revision_mismatch"}
                        )
                    updated = identities.get(command.profile_id)
                return RenameResult(
                    profile=updated,
                    alias_change=AliasChange(
                        profile_id=command.profile_id,
                        kind=AliasChangeKind.RENAMED,
                        old_alias=current.command_alias,
                        new_alias=updated.command_alias,
                    ),
                )
        except ProfileError:
            raise
        except sqlite3.IntegrityError as error:
            raise ProfileNameConflictError(
                safe_details={"reason": "alias_conflict"}, internal_message=str(error)
            ) from error
        except sqlite3.Error as error:
            raise translate_profile_database_error(
                error, reason="rename_database_failure"
            ) from error

    def preview_delete(self, profile_id: ProfileId) -> DestructivePreview:
        try:
            return ProfileDestructiveIntentService(
                self._database_path,
                defaults=self._defaults,
                clock=self._clock,
                busy_timeout_ms=self._busy_timeout_ms,
            ).preview_delete(profile_id)
        except ProfileError:
            raise
        except sqlite3.Error as error:
            raise translate_profile_database_error(
                error, reason="delete_preview_database_failure"
            ) from error

    def confirm_delete(self, command: ConfirmDestructiveOperation) -> DeleteProfileResult:
        try:
            return ProfileDestructiveCoordinator(
                self._database_path,
                defaults=self._defaults,
                clock=self._clock,
                busy_timeout_ms=self._busy_timeout_ms,
            ).confirm_delete(command)
        except ProfileError:
            raise
        except sqlite3.Error as error:
            raise translate_profile_database_error(
                error, reason="delete_database_failure"
            ) from error


class ProfileConfigService:
    """Profile-scoped configuration reads and revision-checked writes."""

    def __init__(
        self,
        database_path: Path,
        *,
        defaults: DefaultsRegistry | None = None,
        clock: Clock | None = None,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        self._database_path = database_path
        self._defaults = DefaultsRegistry.load_packaged() if defaults is None else defaults
        self._clock = SystemClock() if clock is None else clock
        self._busy_timeout_ms = busy_timeout_ms

    def get_configuration(self, profile_id: ProfileId) -> ProfileConfiguration:
        try:
            with (
                SQLiteDatabase(
                    self._database_path, busy_timeout_ms=self._busy_timeout_ms
                ) as database,
                database.transaction(immediate=False),
            ):
                ProfileRepository(database.connection()).get(profile_id)
                return ProfileConfigurationRepository(database.connection()).get(profile_id)
        except ProfileError:
            raise
        except sqlite3.Error as error:
            raise translate_profile_database_error(
                error, reason="get_configuration_failure"
            ) from error

    def get_section(
        self, profile_id: ProfileId, section: ConfigurationSection
    ) -> ProfileConfigurationSectionSnapshot:
        configuration = self.get_configuration(profile_id)
        return ProfileConfigurationSectionSnapshot(
            profile_id=profile_id,
            section=section,
            value=section_value(configuration.values, section),
            revision=configuration.section_revisions[section],
        )

    def update_configuration(self, command: UpdateProfileConfiguration) -> ProfileConfiguration:
        try:
            with (
                SQLiteDatabase(
                    self._database_path, busy_timeout_ms=self._busy_timeout_ms
                ) as database,
                database.transaction(immediate=True),
            ):
                connection = database.connection()
                profile = ProfileRepository(connection).get(command.profile_id)
                current = ProfileConfigurationRepository(connection).get(command.profile_id)
                if profile.identity_revision != command.expected_identity_revision:
                    raise ConcurrentProfileModificationError(
                        safe_details={"reason": "identity_revision_mismatch"}
                    )
                if current.configuration_revision != command.expected_configuration_revision:
                    raise ConcurrentProfileModificationError(
                        safe_details={"reason": "configuration_revision_mismatch"}
                    )
                changed_sections = frozenset(
                    section
                    for section in ConfigurationSection
                    if section_value(current.values, section)
                    != section_value(command.values, section)
                )
                if not changed_sections:
                    return current
                changed = ProfileConfigurationRepository(connection).update(
                    profile_id=command.profile_id,
                    expected_configuration_revision=command.expected_configuration_revision,
                    values=command.values,
                    changed_sections=changed_sections,
                    timestamp_utc=self._clock.now(),
                )
                if not changed:
                    raise ConcurrentProfileModificationError(
                        safe_details={"reason": "configuration_revision_mismatch"}
                    )
                return ProfileConfigurationRepository(connection).get(command.profile_id)
        except ProfileError:
            raise
        except sqlite3.Error as error:
            raise translate_profile_database_error(
                error, reason="update_configuration_failure"
            ) from error

    def preview_reset(self, profile_id: ProfileId, scope: ResetScope) -> DestructivePreview:
        try:
            return ProfileDestructiveIntentService(
                self._database_path,
                defaults=self._defaults,
                clock=self._clock,
                busy_timeout_ms=self._busy_timeout_ms,
            ).preview_reset(profile_id, scope)
        except ProfileError:
            raise
        except sqlite3.Error as error:
            raise translate_profile_database_error(
                error, reason="reset_preview_database_failure"
            ) from error

    def confirm_reset(self, command: ConfirmDestructiveOperation) -> ResetProfileResult:
        try:
            return ProfileDestructiveCoordinator(
                self._database_path,
                defaults=self._defaults,
                clock=self._clock,
                busy_timeout_ms=self._busy_timeout_ms,
            ).confirm_reset(command)
        except ProfileError:
            raise
        except sqlite3.Error as error:
            raise translate_profile_database_error(
                error, reason="reset_database_failure"
            ) from error
