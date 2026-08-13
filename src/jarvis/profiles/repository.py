"""Parameterized SQL repositories scoped by stable profile identifiers."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from datetime import datetime

from jarvis.foundation.clock import format_utc, normalize_utc
from jarvis.profiles.configuration import (
    PROFILE_CONFIG_SCHEMA_VERSION,
    AppearanceConfiguration,
    ProfileConfiguration,
    ProfileConfigurationValues,
    SectionRevision,
)
from jarvis.profiles.errors import ProfileError, ProfileInvariantError, ProfileNotFoundError
from jarvis.profiles.models import (
    ALL_CAPABILITIES,
    ALL_CONFIGURATION_SECTIONS,
    Capability,
    ConfigurationSection,
    PermissionDecision,
    Profile,
    ProfileId,
    ProfileKind,
    VisibleLoggingMode,
)
from jarvis.profiles.names import normalize_profile_name


def _text(value: object) -> str:
    if type(value) is not str:
        raise ProfileInvariantError(safe_details={"reason": "invalid_text"})
    return value


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ProfileInvariantError(safe_details={"reason": "invalid_timestamp"})
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return normalize_utc(parsed)
    except ValueError as error:
        raise ProfileInvariantError(safe_details={"reason": "invalid_timestamp"}) from error


def _integer(value: object) -> int:
    if type(value) is not int:
        raise ProfileInvariantError(safe_details={"reason": "invalid_integer"})
    return value


def _profile_from_row(row: tuple[object, ...]) -> Profile:
    try:
        display_name = _text(row[2])
        command_alias = _text(row[3])
        normalized = normalize_profile_name(display_name)
        if normalized.display_name != display_name or normalized.command_alias != command_alias:
            raise ProfileInvariantError(safe_details={"reason": "identity_alias_mismatch"})
        return Profile(
            profile_id=ProfileId.parse(_text(row[0])),
            kind=ProfileKind(_text(row[1])),
            display_name=display_name,
            command_alias=command_alias,
            identity_revision=_integer(row[4]),
            created_at_utc=_parse_utc(row[5]),
            updated_at_utc=_parse_utc(row[6]),
        )
    except ProfileInvariantError:
        raise
    except (ProfileError, TypeError, ValueError) as error:
        raise ProfileInvariantError(safe_details={"reason": "invalid_identity_row"}) from error


class ProfileRepository:
    """Identity and alias SQL using a caller-owned connection/transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def has_any_domain_state(self) -> bool:
        row = self._connection.execute(
            """
            SELECT 1 FROM profiles
            UNION ALL SELECT 1 FROM profile_aliases
            UNION ALL SELECT 1 FROM profile_configurations
            UNION ALL SELECT 1 FROM profile_configuration_sections
            UNION ALL SELECT 1 FROM profile_messages
            UNION ALL SELECT 1 FROM profile_permissions
            UNION ALL SELECT 1 FROM profile_operation_intents
            LIMIT 1
            """
        ).fetchone()
        return row is not None

    def find_jarvis(self) -> Profile | None:
        row = self._connection.execute(
            """
            SELECT p.profile_id, p.profile_kind, p.display_name, a.command_alias,
                   p.identity_revision, p.created_at_utc, p.updated_at_utc
            FROM profiles AS p
            JOIN profile_aliases AS a ON a.profile_id = p.profile_id
            WHERE p.profile_kind = ?
            """,
            (ProfileKind.JARVIS.value,),
        ).fetchone()
        return None if row is None else _profile_from_row(row)

    def get(self, profile_id: ProfileId) -> Profile:
        row = self._connection.execute(
            """
            SELECT p.profile_id, p.profile_kind, p.display_name, a.command_alias,
                   p.identity_revision, p.created_at_utc, p.updated_at_utc
            FROM profiles AS p
            LEFT JOIN profile_aliases AS a ON a.profile_id = p.profile_id
            WHERE p.profile_id = ?
            """,
            (str(profile_id),),
        ).fetchone()
        if row is None:
            raise ProfileNotFoundError(safe_details={"profile_id": str(profile_id)})
        return _profile_from_row(row)

    def list(self) -> tuple[Profile, ...]:
        rows = self._connection.execute(
            """
            SELECT p.profile_id, p.profile_kind, p.display_name, a.command_alias,
                   p.identity_revision, p.created_at_utc, p.updated_at_utc
            FROM profiles AS p
            LEFT JOIN profile_aliases AS a ON a.profile_id = p.profile_id
            ORDER BY CASE p.profile_kind WHEN 'jarvis' THEN 0 ELSE 1 END,
                     a.command_alias, p.profile_id
            """
        ).fetchall()
        return tuple(_profile_from_row(row) for row in rows)

    def alias_owner(self, command_alias: str) -> ProfileId | None:
        row = self._connection.execute(
            "SELECT profile_id FROM profile_aliases WHERE command_alias = ?",
            (command_alias,),
        ).fetchone()
        if row is None:
            return None
        try:
            return ProfileId.parse(_text(row[0]))
        except ValueError as error:
            raise ProfileInvariantError(safe_details={"reason": "invalid_alias_owner"}) from error

    def exists(self, profile_id: ProfileId) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM profiles WHERE profile_id = ?", (str(profile_id),)
        ).fetchone()
        return row is not None

    def insert(
        self,
        *,
        profile_id: ProfileId,
        kind: ProfileKind,
        display_name: str,
        command_alias: str,
        timestamp_utc: datetime,
    ) -> Profile:
        timestamp = format_utc(timestamp_utc)
        self._connection.execute(
            """
            INSERT INTO profiles (
                profile_id, profile_kind, display_name, identity_revision,
                created_at_utc, updated_at_utc
            ) VALUES (?, ?, ?, 1, ?, ?)
            """,
            (str(profile_id), kind.value, display_name, timestamp, timestamp),
        )
        self._connection.execute(
            """
            INSERT INTO profile_aliases
                (profile_id, command_alias, created_at_utc, updated_at_utc)
            VALUES (?, ?, ?, ?)
            """,
            (str(profile_id), command_alias, timestamp, timestamp),
        )
        return self.get(profile_id)

    def rename(
        self,
        *,
        profile_id: ProfileId,
        display_name: str,
        command_alias: str,
        expected_identity_revision: int,
        timestamp_utc: datetime,
    ) -> bool:
        timestamp = format_utc(timestamp_utc)
        cursor = self._connection.execute(
            """
            UPDATE profiles
            SET display_name = ?, identity_revision = identity_revision + 1, updated_at_utc = ?
            WHERE profile_id = ? AND profile_kind = 'standard' AND identity_revision = ?
            """,
            (display_name, timestamp, str(profile_id), expected_identity_revision),
        )
        if cursor.rowcount != 1:
            return False
        self._connection.execute(
            """
            UPDATE profile_aliases
            SET command_alias = ?, updated_at_utc = ?
            WHERE profile_id = ?
            """,
            (command_alias, timestamp, str(profile_id)),
        )
        return True

    def delete(self, profile_id: ProfileId) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM profiles WHERE profile_id = ? AND profile_kind = 'standard'",
            (str(profile_id),),
        )
        return cursor.rowcount == 1


class ProfileConfigurationRepository:
    """Profile configuration SQL requiring an explicit ProfileId on every operation."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert(
        self,
        *,
        profile_id: ProfileId,
        values: ProfileConfigurationValues,
        defaults_versions: Mapping[ConfigurationSection, int],
        timestamp_utc: datetime,
    ) -> ProfileConfiguration:
        if frozenset(defaults_versions) != frozenset(ALL_CONFIGURATION_SECTIONS):
            raise ValueError("every configuration section needs a defaults version")
        timestamp = format_utc(timestamp_utc)
        self._connection.execute(
            """
            INSERT INTO profile_configurations (
                profile_id, config_schema_version, configuration_revision,
                persona_text, profile_context_text, accent_color, foreground_color,
                background_color, visible_logging_mode, start_with_computer,
                created_at_utc, updated_at_utc
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(profile_id),
                PROFILE_CONFIG_SCHEMA_VERSION,
                values.persona_text,
                values.profile_context_text,
                values.appearance.accent_color,
                values.appearance.foreground_color,
                values.appearance.background_color,
                values.visible_logging_mode.value,
                int(values.start_with_computer),
                timestamp,
                timestamp,
            ),
        )
        self._connection.executemany(
            """
            INSERT INTO profile_configuration_sections
                (profile_id, section_name, defaults_version, section_revision)
            VALUES (?, ?, ?, 1)
            """,
            (
                (str(profile_id), section.value, defaults_versions[section])
                for section in ALL_CONFIGURATION_SECTIONS
            ),
        )
        self._insert_messages(profile_id, "waiting", values.waiting_messages)
        self._insert_messages(profile_id, "goodbye", values.goodbye_messages)
        self._connection.executemany(
            "INSERT INTO profile_permissions (profile_id, capability, decision) VALUES (?, ?, ?)",
            (
                (str(profile_id), capability.value, values.permissions[capability].value)
                for capability in ALL_CAPABILITIES
            ),
        )
        return self.get(profile_id)

    def _insert_messages(self, profile_id: ProfileId, kind: str, messages: tuple[str, ...]) -> None:
        self._connection.executemany(
            """
            INSERT INTO profile_messages (profile_id, message_kind, ordinal, message_text)
            VALUES (?, ?, ?, ?)
            """,
            ((str(profile_id), kind, ordinal, message) for ordinal, message in enumerate(messages)),
        )

    def get(self, profile_id: ProfileId) -> ProfileConfiguration:
        row = self._connection.execute(
            """
            SELECT config_schema_version, configuration_revision, persona_text,
                   profile_context_text, accent_color, foreground_color, background_color,
                   visible_logging_mode, start_with_computer
            FROM profile_configurations
            WHERE profile_id = ?
            """,
            (str(profile_id),),
        ).fetchone()
        if row is None:
            raise ProfileInvariantError(safe_details={"reason": "missing_configuration"})
        messages = self._read_messages(profile_id)
        permissions = self._read_permissions(profile_id)
        sections = self._read_sections(profile_id)
        try:
            values = ProfileConfigurationValues(
                persona_text=_text(row[2]),
                profile_context_text=_text(row[3]),
                appearance=AppearanceConfiguration(_text(row[4]), _text(row[5]), _text(row[6])),
                waiting_messages=messages["waiting"],
                goodbye_messages=messages["goodbye"],
                visible_logging_mode=VisibleLoggingMode(_text(row[7])),
                start_with_computer=bool(row[8]) if row[8] in (0, 1) else row[8],
                permissions=permissions,
            )
            return ProfileConfiguration(
                profile_id=profile_id,
                config_schema_version=_integer(row[0]),
                configuration_revision=_integer(row[1]),
                values=values,
                section_revisions=sections,
            )
        except (TypeError, ValueError) as error:
            raise ProfileInvariantError(
                safe_details={"reason": "invalid_configuration_row"}
            ) from error

    def update(
        self,
        *,
        profile_id: ProfileId,
        expected_configuration_revision: int,
        values: ProfileConfigurationValues,
        changed_sections: frozenset[ConfigurationSection],
        timestamp_utc: datetime,
        defaults_version: int | None = None,
    ) -> bool:
        if not changed_sections:
            return True
        timestamp = format_utc(timestamp_utc)
        cursor = self._connection.execute(
            """
            UPDATE profile_configurations
            SET configuration_revision = configuration_revision + 1,
                persona_text = ?, profile_context_text = ?, accent_color = ?,
                foreground_color = ?, background_color = ?, visible_logging_mode = ?,
                start_with_computer = ?, updated_at_utc = ?
            WHERE profile_id = ? AND configuration_revision = ?
            """,
            (
                values.persona_text,
                values.profile_context_text,
                values.appearance.accent_color,
                values.appearance.foreground_color,
                values.appearance.background_color,
                values.visible_logging_mode.value,
                int(values.start_with_computer),
                timestamp,
                str(profile_id),
                expected_configuration_revision,
            ),
        )
        if cursor.rowcount != 1:
            return False
        if ConfigurationSection.WAITING_MESSAGES in changed_sections:
            self._replace_messages(profile_id, "waiting", values.waiting_messages)
        if ConfigurationSection.GOODBYE_MESSAGES in changed_sections:
            self._replace_messages(profile_id, "goodbye", values.goodbye_messages)
        if ConfigurationSection.PERMISSIONS in changed_sections:
            self._connection.execute(
                "DELETE FROM profile_permissions WHERE profile_id = ?", (str(profile_id),)
            )
            self._connection.executemany(
                """
                INSERT INTO profile_permissions (profile_id, capability, decision)
                VALUES (?, ?, ?)
                """,
                (
                    (str(profile_id), capability.value, values.permissions[capability].value)
                    for capability in ALL_CAPABILITIES
                ),
            )
        if defaults_version is None:
            self._connection.executemany(
                """
                UPDATE profile_configuration_sections
                SET section_revision = section_revision + 1
                WHERE profile_id = ? AND section_name = ?
                """,
                ((str(profile_id), section.value) for section in changed_sections),
            )
        else:
            if defaults_version <= 0:
                raise ValueError("defaults version must be positive")
            self._connection.executemany(
                """
                UPDATE profile_configuration_sections
                SET section_revision = section_revision + 1, defaults_version = ?
                WHERE profile_id = ? AND section_name = ?
                """,
                (
                    (defaults_version, str(profile_id), section.value)
                    for section in changed_sections
                ),
            )
        return True

    def _replace_messages(
        self, profile_id: ProfileId, kind: str, messages: tuple[str, ...]
    ) -> None:
        self._connection.execute(
            "DELETE FROM profile_messages WHERE profile_id = ? AND message_kind = ?",
            (str(profile_id), kind),
        )
        self._insert_messages(profile_id, kind, messages)

    def _read_messages(self, profile_id: ProfileId) -> dict[str, tuple[str, ...]]:
        rows = self._connection.execute(
            """
            SELECT message_kind, ordinal, message_text
            FROM profile_messages
            WHERE profile_id = ?
            ORDER BY message_kind, ordinal
            """,
            (str(profile_id),),
        ).fetchall()
        grouped: dict[str, list[str]] = {"waiting": [], "goodbye": []}
        expected: dict[str, int] = {"waiting": 0, "goodbye": 0}
        for raw_kind, raw_ordinal, raw_text in rows:
            kind = _text(raw_kind)
            ordinal = _integer(raw_ordinal)
            if kind not in grouped or ordinal != expected[kind]:
                raise ProfileInvariantError(safe_details={"reason": "invalid_message_ordinals"})
            grouped[kind].append(_text(raw_text))
            expected[kind] += 1
        return {kind: tuple(values) for kind, values in grouped.items()}

    def _read_permissions(self, profile_id: ProfileId) -> Mapping[Capability, PermissionDecision]:
        rows = self._connection.execute(
            "SELECT capability, decision FROM profile_permissions WHERE profile_id = ?",
            (str(profile_id),),
        ).fetchall()
        try:
            permissions = {
                Capability(_text(capability)): PermissionDecision(_text(decision))
                for capability, decision in rows
            }
        except ValueError as error:
            raise ProfileInvariantError(safe_details={"reason": "invalid_permissions"}) from error
        if frozenset(permissions) != frozenset(ALL_CAPABILITIES):
            raise ProfileInvariantError(safe_details={"reason": "incomplete_permissions"})
        return permissions

    def _read_sections(
        self, profile_id: ProfileId
    ) -> Mapping[ConfigurationSection, SectionRevision]:
        rows = self._connection.execute(
            """
            SELECT section_name, defaults_version, section_revision
            FROM profile_configuration_sections
            WHERE profile_id = ?
            """,
            (str(profile_id),),
        ).fetchall()
        try:
            sections = {
                ConfigurationSection(_text(name)): SectionRevision(
                    ConfigurationSection(_text(name)),
                    _integer(defaults_version),
                    _integer(revision),
                )
                for name, defaults_version, revision in rows
            }
        except ValueError as error:
            raise ProfileInvariantError(safe_details={"reason": "invalid_sections"}) from error
        if frozenset(sections) != frozenset(ALL_CONFIGURATION_SECTIONS):
            raise ProfileInvariantError(safe_details={"reason": "incomplete_sections"})
        return sections
