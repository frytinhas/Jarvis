"""Closed destructive previews and short-lived hashed confirmation intents."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from os import PathLike
from pathlib import Path
from typing import Protocol
from uuid import RFC_4122, UUID, uuid4

from jarvis.config.defaults import DefaultsRegistry
from jarvis.foundation.clock import Clock, SystemClock, format_utc, normalize_utc
from jarvis.profiles.configuration import (
    ProfileAggregate,
    ProfileConfiguration,
    ProfileConfigurationValues,
    section_value,
)
from jarvis.profiles.errors import (
    ConfirmationExpiredError,
    ConfirmationInvalidError,
    ConfirmationStaleError,
    ProfileError,
    ProfileInvariantError,
    ProtectedProfileError,
    translate_profile_database_error,
)
from jarvis.profiles.models import (
    AliasChange,
    AliasChangeKind,
    Capability,
    ConfigurationSection,
    ProfileId,
    ProfileKind,
)
from jarvis.profiles.repository import ProfileConfigurationRepository, ProfileRepository
from jarvis.storage.database import SQLiteDatabase

CONFIRMATION_TTL = timedelta(minutes=5)
INTENT_PRUNE_BATCH = 100
MAX_CONFIRMATION_TOKEN_BYTES = 256


def _confirmation_token_digest(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_CONFIRMATION_TOKEN_BYTES:
        raise ConfirmationInvalidError(safe_details={"reason": "invalid_token"})
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ConfirmationInvalidError(safe_details={"reason": "invalid_token"}) from error
    if len(encoded) > MAX_CONFIRMATION_TOKEN_BYTES:
        raise ConfirmationInvalidError(safe_details={"reason": "invalid_token"})
    return hashlib.sha256(encoded).hexdigest()


@contextmanager
def _translate_sqlite_errors(*, reason: str) -> Iterator[None]:
    try:
        yield
    except ProfileError:
        raise
    except sqlite3.Error as error:
        raise translate_profile_database_error(error, reason=reason) from error


class DestructiveOperationKind(StrEnum):
    DELETE_PROFILE = "delete-profile"
    RESET_CONFIGURATION = "reset-configuration"

    @classmethod
    def parse(cls, value: str) -> DestructiveOperationKind:
        try:
            return cls(value)
        except ValueError as error:
            raise ConfirmationInvalidError(
                safe_details={"reason": "invalid_operation_kind"}
            ) from error


class DeletionScope(StrEnum):
    WHOLE_PROFILE = "whole-profile"

    @classmethod
    def parse(cls, value: str) -> DeletionScope:
        try:
            return cls(value)
        except ValueError as error:
            raise ConfirmationInvalidError(safe_details={"reason": "invalid_scope"}) from error


class ResetScope(StrEnum):
    PERSONA = "persona"
    PROFILE_CONTEXT = "profile-context"
    APPEARANCE = "appearance"
    WAITING_MESSAGES = "waiting-messages"
    GOODBYE_MESSAGES = "goodbye-messages"
    VISIBLE_LOGGING = "visible-logging"
    STARTUP = "startup"
    PERMISSIONS = "permissions"
    WHOLE_PROFILE = "whole-profile"

    @classmethod
    def parse(cls, value: str) -> ResetScope:
        try:
            return cls(value)
        except ValueError as error:
            raise ConfirmationInvalidError(safe_details={"reason": "invalid_scope"}) from error


type DestructiveScope = DeletionScope | ResetScope


@dataclass(frozen=True, slots=True)
class DestructiveTarget:
    operation_kind: DestructiveOperationKind
    scope: DestructiveScope

    def __post_init__(self) -> None:
        valid = (
            self.operation_kind is DestructiveOperationKind.DELETE_PROFILE
            and self.scope is DeletionScope.WHOLE_PROFILE
        ) or (
            self.operation_kind is DestructiveOperationKind.RESET_CONFIGURATION
            and isinstance(self.scope, ResetScope)
        )
        if not valid:
            raise ConfirmationInvalidError(safe_details={"reason": "invalid_operation_scope"})


@dataclass(frozen=True, slots=True)
class OperationId:
    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4 or self.value.variant != RFC_4122:
            raise ValueError("operation ID must be an RFC 4122 version-4 UUID")

    @classmethod
    def parse(cls, value: str) -> OperationId:
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError("operation ID must use canonical lowercase UUID text")
        return cls(parsed)

    def __str__(self) -> str:
        return str(self.value)


class OperationIdGenerator(Protocol):
    def new_operation_id(self) -> OperationId:
        """Return a new opaque operation identifier."""


class RandomOperationIdGenerator:
    def new_operation_id(self) -> OperationId:
        return OperationId(uuid4())


class DeterministicOperationIdGenerator:
    def __init__(self, values: Iterable[UUID]) -> None:
        self._values = deque(values)

    def new_operation_id(self) -> OperationId:
        try:
            return OperationId(self._values.popleft())
        except IndexError as error:
            raise RuntimeError("deterministic operation identifier sequence exhausted") from error


@dataclass(frozen=True, slots=True)
class DestructivePreviewItem:
    key: str
    action: str
    current_count: int
    target_count: int
    will_change: bool

    def __post_init__(self) -> None:
        if self.current_count < 0 or self.target_count < 0:
            raise ValueError("preview counts cannot be negative")


@dataclass(frozen=True, slots=True)
class DestructivePreview:
    operation_id: OperationId
    target: DestructiveTarget
    profile_id: ProfileId
    expected_identity_revision: int
    expected_configuration_revision: int
    created_at_utc: datetime
    expires_at_utc: datetime
    target_defaults_version: int | None
    items: tuple[DestructivePreviewItem, ...]
    has_changes: bool
    confirmation_token: str = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at_utc", normalize_utc(self.created_at_utc))
        object.__setattr__(self, "expires_at_utc", normalize_utc(self.expires_at_utc))
        _confirmation_token_digest(self.confirmation_token)


@dataclass(frozen=True, slots=True)
class ConfirmDestructiveOperation:
    operation_id: OperationId
    target: DestructiveTarget
    profile_id: ProfileId
    confirmation_token: str = field(repr=False)

    def __post_init__(self) -> None:
        _confirmation_token_digest(self.confirmation_token)


@dataclass(frozen=True, slots=True)
class StoredOperationIntent:
    operation_id: OperationId
    target: DestructiveTarget
    profile_id: ProfileId
    expected_identity_revision: int
    expected_configuration_revision: int
    state_digest_sha256: str
    token_digest_sha256: str = field(repr=False)
    created_at_utc: datetime
    expires_at_utc: datetime


class ProfileOperationIntentRepository:
    """SQL storage for digests only; raw confirmation tokens never enter this boundary."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def replace(self, intent: StoredOperationIntent) -> None:
        self._connection.execute(
            """
            DELETE FROM profile_operation_intents
            WHERE profile_id = ? AND operation_kind = ? AND scope = ?
            """,
            (
                str(intent.profile_id),
                intent.target.operation_kind.value,
                intent.target.scope.value,
            ),
        )
        self._connection.execute(
            """
            INSERT INTO profile_operation_intents (
                operation_id, profile_id, operation_kind, scope,
                expected_identity_revision, expected_configuration_revision,
                state_digest_sha256, token_digest_sha256, created_at_utc, expires_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(intent.operation_id),
                str(intent.profile_id),
                intent.target.operation_kind.value,
                intent.target.scope.value,
                intent.expected_identity_revision,
                intent.expected_configuration_revision,
                intent.state_digest_sha256,
                intent.token_digest_sha256,
                format_utc(intent.created_at_utc),
                format_utc(intent.expires_at_utc),
            ),
        )

    def get(self, operation_id: OperationId) -> StoredOperationIntent | None:
        row = self._connection.execute(
            """
            SELECT operation_id, profile_id, operation_kind, scope,
                   expected_identity_revision, expected_configuration_revision,
                   state_digest_sha256, token_digest_sha256, created_at_utc, expires_at_utc
            FROM profile_operation_intents
            WHERE operation_id = ?
            """,
            (str(operation_id),),
        ).fetchone()
        if row is None:
            return None
        try:
            kind = DestructiveOperationKind.parse(str(row[2]))
            scope: DestructiveScope
            if kind is DestructiveOperationKind.DELETE_PROFILE:
                scope = DeletionScope.parse(str(row[3]))
            else:
                scope = ResetScope.parse(str(row[3]))
            return StoredOperationIntent(
                operation_id=OperationId.parse(str(row[0])),
                target=DestructiveTarget(kind, scope),
                profile_id=ProfileId.parse(str(row[1])),
                expected_identity_revision=int(row[4]),
                expected_configuration_revision=int(row[5]),
                state_digest_sha256=str(row[6]),
                token_digest_sha256=str(row[7]),
                created_at_utc=_parse_utc(str(row[8])),
                expires_at_utc=_parse_utc(str(row[9])),
            )
        except (TypeError, ValueError) as error:
            raise ProfileInvariantError(safe_details={"reason": "invalid_intent_row"}) from error

    def consume(self, operation_id: OperationId) -> bool:
        cursor = self._connection.execute(
            "DELETE FROM profile_operation_intents WHERE operation_id = ?", (str(operation_id),)
        )
        return cursor.rowcount == 1

    def prune_expired(
        self, now_utc: datetime, *, limit: int = INTENT_PRUNE_BATCH
    ) -> tuple[str, ...]:
        if limit <= 0 or limit > INTENT_PRUNE_BATCH:
            raise ValueError("intent prune limit is out of bounds")
        rows = self._connection.execute(
            """
            SELECT operation_id
            FROM profile_operation_intents
            WHERE expires_at_utc <= ?
            ORDER BY expires_at_utc, operation_id
            LIMIT ?
            """,
            (format_utc(now_utc), limit),
        ).fetchall()
        operation_ids = tuple(str(row[0]) for row in rows)
        self._connection.executemany(
            "DELETE FROM profile_operation_intents WHERE operation_id = ?",
            ((operation_id,) for operation_id in operation_ids),
        )
        return operation_ids


def _profile_model_state(
    connection: sqlite3.Connection, profile_id: ProfileId
) -> tuple[tuple[object, ...], ...]:
    return tuple(
        tuple(row)
        for row in connection.execute(
            """SELECT model_id, profile_model_revision, selected, last_valid, runtime_config_json
               FROM profile_models WHERE profile_id = ? ORDER BY model_id""",
            (str(profile_id),),
        ).fetchall()
    )


def _state_digest(
    aggregate: ProfileAggregate,
    target: DestructiveTarget,
    profile_models: tuple[tuple[object, ...], ...],
) -> str:
    profile = aggregate.profile
    configuration = aggregate.configuration
    values = configuration.values
    payload = {
        "target": [target.operation_kind.value, target.scope.value],
        "profile": {
            "profile_id": str(profile.profile_id),
            "kind": profile.kind.value,
            "display_name": profile.display_name,
            "command_alias": profile.command_alias,
            "identity_revision": profile.identity_revision,
            "created_at_utc": format_utc(profile.created_at_utc),
            "updated_at_utc": format_utc(profile.updated_at_utc),
        },
        "configuration": {
            "schema_version": configuration.config_schema_version,
            "revision": configuration.configuration_revision,
            "persona_text": values.persona_text,
            "profile_context_text": values.profile_context_text,
            "appearance": {
                "accent_color": values.appearance.accent_color,
                "foreground_color": values.appearance.foreground_color,
                "background_color": values.appearance.background_color,
            },
            "waiting_messages": list(values.waiting_messages),
            "goodbye_messages": list(values.goodbye_messages),
            "visible_logging_mode": values.visible_logging_mode.value,
            "start_with_computer": values.start_with_computer,
            "permissions": {
                capability.value: values.permissions[capability].value for capability in Capability
            },
            "sections": {
                section.value: {
                    "defaults_version": configuration.section_revisions[section].defaults_version,
                    "revision": configuration.section_revisions[section].revision,
                }
                for section in ConfigurationSection
            },
        },
        "profile_models": [list(row) for row in profile_models],
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_utc(value: str) -> datetime:
    try:
        return normalize_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError as error:
        raise ProfileInvariantError(safe_details={"reason": "invalid_intent_timestamp"}) from error


def _reset_items(
    current: ProfileConfiguration,
    target: ProfileConfigurationValues,
    scope: ResetScope,
    target_defaults_version: int,
) -> tuple[DestructivePreviewItem, ...]:
    sections = (
        tuple(ConfigurationSection)
        if scope is ResetScope.WHOLE_PROFILE
        else (ConfigurationSection(scope.value),)
    )
    items: list[DestructivePreviewItem] = []
    for section in sections:
        values = current.values
        origin_changed = (
            current.section_revisions[section].defaults_version != target_defaults_version
        )
        if section is ConfigurationSection.APPEARANCE:
            for field_name in ("accent_color", "foreground_color", "background_color"):
                changed = origin_changed or getattr(values.appearance, field_name) != getattr(
                    target.appearance, field_name
                )
                items.append(
                    DestructivePreviewItem(
                        f"appearance.{field_name}", "restore-default", 1, 1, changed
                    )
                )
        elif section is ConfigurationSection.PERMISSIONS:
            for capability in Capability:
                changed = (
                    origin_changed
                    or values.permissions[capability] != target.permissions[capability]
                )
                items.append(
                    DestructivePreviewItem(
                        f"permissions.{capability.value}", "restore-default", 1, 1, changed
                    )
                )
        elif section in {
            ConfigurationSection.WAITING_MESSAGES,
            ConfigurationSection.GOODBYE_MESSAGES,
        }:
            current_messages = section_value(values, section)
            target_messages = section_value(target, section)
            assert isinstance(current_messages, tuple) and isinstance(target_messages, tuple)
            items.append(
                DestructivePreviewItem(
                    section.value,
                    "replace-default",
                    len(current_messages),
                    len(target_messages),
                    origin_changed or current_messages != target_messages,
                )
            )
        else:
            changed = origin_changed or section_value(values, section) != section_value(
                target, section
            )
            items.append(DestructivePreviewItem(section.value, "restore-default", 1, 1, changed))
    return tuple(items)


class ProfileDestructiveIntentService:
    """Creates exact previews and persists only bounded confirmation digests."""

    def __init__(
        self,
        database_path: str | PathLike[str],
        *,
        defaults: DefaultsRegistry | None = None,
        clock: Clock | None = None,
        operation_ids: OperationIdGenerator | None = None,
        token_factory: Callable[[], str] | None = None,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        self._database_path = Path(database_path)
        self._defaults = DefaultsRegistry.load_packaged() if defaults is None else defaults
        self._clock = SystemClock() if clock is None else clock
        self._operation_ids = (
            RandomOperationIdGenerator() if operation_ids is None else operation_ids
        )
        self._token_factory: Callable[[], str] = (
            (lambda: secrets.token_urlsafe(32)) if token_factory is None else token_factory
        )
        self._busy_timeout_ms = busy_timeout_ms

    def preview_delete(self, profile_id: ProfileId) -> DestructivePreview:
        target = DestructiveTarget(
            DestructiveOperationKind.DELETE_PROFILE, DeletionScope.WHOLE_PROFILE
        )
        with (
            _translate_sqlite_errors(reason="delete_preview_database_failure"),
            SQLiteDatabase(self._database_path, busy_timeout_ms=self._busy_timeout_ms) as database,
            database.transaction(immediate=True),
        ):
            aggregate = self._aggregate(database.connection(), profile_id)
            if aggregate.profile.kind is ProfileKind.JARVIS:
                raise ProtectedProfileError(safe_details={"operation": "delete"})
            items = (
                DestructivePreviewItem("identity", "delete", 1, 0, True),
                DestructivePreviewItem("alias", "delete", 1, 0, True),
                DestructivePreviewItem("configuration", "delete", 1, 0, True),
                DestructivePreviewItem("configuration-sections", "delete", 8, 0, True),
                DestructivePreviewItem("permissions", "delete", 9, 0, True),
                DestructivePreviewItem(
                    "waiting-messages",
                    "delete",
                    len(aggregate.configuration.values.waiting_messages),
                    0,
                    bool(aggregate.configuration.values.waiting_messages),
                ),
                DestructivePreviewItem(
                    "profile-model-associations",
                    "delete",
                    int(
                        database.connection()
                        .execute(
                            "SELECT COUNT(*) FROM profile_models WHERE profile_id = ?",
                            (str(profile_id),),
                        )
                        .fetchone()[0]
                    ),
                    0,
                    bool(
                        database.connection()
                        .execute(
                            "SELECT 1 FROM profile_models WHERE profile_id = ? LIMIT 1",
                            (str(profile_id),),
                        )
                        .fetchone()
                    ),
                ),
                DestructivePreviewItem(
                    "goodbye-messages",
                    "delete",
                    len(aggregate.configuration.values.goodbye_messages),
                    0,
                    bool(aggregate.configuration.values.goodbye_messages),
                ),
            )
            return self._store_preview(
                database.connection(), aggregate, target, items, target_defaults_version=None
            )

    def preview_reset(self, profile_id: ProfileId, scope: ResetScope) -> DestructivePreview:
        target = DestructiveTarget(DestructiveOperationKind.RESET_CONFIGURATION, scope)
        defaults_snapshot = self._defaults.current()
        defaults = ProfileConfigurationValues.from_defaults(defaults_snapshot.profile_defaults)
        with (
            _translate_sqlite_errors(reason="reset_preview_database_failure"),
            SQLiteDatabase(self._database_path, busy_timeout_ms=self._busy_timeout_ms) as database,
            database.transaction(immediate=True),
        ):
            aggregate = self._aggregate(database.connection(), profile_id)
            items = _reset_items(
                aggregate.configuration, defaults, scope, defaults_snapshot.product_defaults_version
            )
            if scope is ResetScope.WHOLE_PROFILE:
                association_count = len(
                    _profile_model_state(database.connection(), aggregate.profile.profile_id)
                )
                items += (
                    DestructivePreviewItem(
                        "profile-model-associations",
                        "delete",
                        association_count,
                        0,
                        association_count > 0,
                    ),
                )
            return self._store_preview(
                database.connection(),
                aggregate,
                target,
                items,
                target_defaults_version=defaults_snapshot.product_defaults_version,
            )

    @staticmethod
    def _aggregate(connection: sqlite3.Connection, profile_id: ProfileId) -> ProfileAggregate:
        return ProfileAggregate(
            ProfileRepository(connection).get(profile_id),
            ProfileConfigurationRepository(connection).get(profile_id),
        )

    def _store_preview(
        self,
        connection: sqlite3.Connection,
        aggregate: ProfileAggregate,
        target: DestructiveTarget,
        items: tuple[DestructivePreviewItem, ...],
        *,
        target_defaults_version: int | None,
    ) -> DestructivePreview:
        now = self._clock.now()
        expires = now + CONFIRMATION_TTL
        operation_id = self._operation_ids.new_operation_id()
        raw_token = self._token_factory()
        token_digest = _confirmation_token_digest(raw_token)
        intent = StoredOperationIntent(
            operation_id=operation_id,
            target=target,
            profile_id=aggregate.profile.profile_id,
            expected_identity_revision=aggregate.profile.identity_revision,
            expected_configuration_revision=aggregate.configuration.configuration_revision,
            state_digest_sha256=_state_digest(
                aggregate, target, _profile_model_state(connection, aggregate.profile.profile_id)
            ),
            token_digest_sha256=token_digest,
            created_at_utc=now,
            expires_at_utc=expires,
        )
        repository = ProfileOperationIntentRepository(connection)
        repository.prune_expired(now)
        repository.replace(intent)
        return DestructivePreview(
            operation_id=operation_id,
            target=target,
            profile_id=aggregate.profile.profile_id,
            expected_identity_revision=aggregate.profile.identity_revision,
            expected_configuration_revision=aggregate.configuration.configuration_revision,
            created_at_utc=now,
            expires_at_utc=expires,
            target_defaults_version=target_defaults_version,
            items=items,
            has_changes=any(item.will_change for item in items),
            confirmation_token=raw_token,
        )


@dataclass(frozen=True, slots=True)
class ResetProfileResult:
    profile_id: ProfileId
    scope: ResetScope
    configuration: ProfileConfiguration
    changed_sections: tuple[ConfigurationSection, ...]


@dataclass(frozen=True, slots=True)
class DeleteProfileResult:
    profile_id: ProfileId
    alias_change: AliasChange
    deleted_items: tuple[DestructivePreviewItem, ...]


def _reset_values(
    current: ProfileConfigurationValues,
    defaults: ProfileConfigurationValues,
    scope: ResetScope,
) -> ProfileConfigurationValues:
    from dataclasses import replace

    if scope is ResetScope.WHOLE_PROFILE:
        return defaults
    section = ConfigurationSection(scope.value)
    match section:
        case ConfigurationSection.PERSONA:
            return replace(current, persona_text=defaults.persona_text)
        case ConfigurationSection.PROFILE_CONTEXT:
            return replace(current, profile_context_text=defaults.profile_context_text)
        case ConfigurationSection.APPEARANCE:
            return replace(current, appearance=defaults.appearance)
        case ConfigurationSection.WAITING_MESSAGES:
            return replace(current, waiting_messages=defaults.waiting_messages)
        case ConfigurationSection.GOODBYE_MESSAGES:
            return replace(current, goodbye_messages=defaults.goodbye_messages)
        case ConfigurationSection.VISIBLE_LOGGING:
            return replace(current, visible_logging_mode=defaults.visible_logging_mode)
        case ConfigurationSection.STARTUP:
            return replace(current, start_with_computer=defaults.start_with_computer)
        case ConfigurationSection.PERMISSIONS:
            return replace(current, permissions=defaults.permissions)


class ProfileDestructiveCoordinator:
    """Validates and applies current database-owned destructive work atomically."""

    def __init__(
        self,
        database_path: str | PathLike[str],
        *,
        defaults: DefaultsRegistry | None = None,
        clock: Clock | None = None,
        busy_timeout_ms: int = 5_000,
    ) -> None:
        self._database_path = Path(database_path)
        self._defaults = DefaultsRegistry.load_packaged() if defaults is None else defaults
        self._clock = SystemClock() if clock is None else clock
        self._busy_timeout_ms = busy_timeout_ms

    def confirm_reset(self, command: ConfirmDestructiveOperation) -> ResetProfileResult:
        if command.target.operation_kind is not DestructiveOperationKind.RESET_CONFIGURATION:
            raise ConfirmationInvalidError(safe_details={"reason": "operation_mismatch"})
        if not isinstance(command.target.scope, ResetScope):
            raise ConfirmationInvalidError(safe_details={"reason": "scope_mismatch"})
        defaults_snapshot = self._defaults.current()
        defaults = ProfileConfigurationValues.from_defaults(defaults_snapshot.profile_defaults)
        with (
            _translate_sqlite_errors(reason="reset_database_failure"),
            SQLiteDatabase(self._database_path, busy_timeout_ms=self._busy_timeout_ms) as database,
            database.transaction(immediate=True),
        ):
            connection = database.connection()
            intent, aggregate = self._validate(connection, command)
            scope = command.target.scope
            selected = (
                frozenset(ConfigurationSection)
                if scope is ResetScope.WHOLE_PROFILE
                else frozenset({ConfigurationSection(scope.value)})
            )
            target_values = _reset_values(aggregate.configuration.values, defaults, scope)
            changed_sections = frozenset(
                section
                for section in selected
                if section_value(aggregate.configuration.values, section)
                != section_value(target_values, section)
                or aggregate.configuration.section_revisions[section].defaults_version
                != defaults_snapshot.product_defaults_version
            )
            if changed_sections:
                changed = ProfileConfigurationRepository(connection).update(
                    profile_id=command.profile_id,
                    expected_configuration_revision=intent.expected_configuration_revision,
                    values=target_values,
                    changed_sections=changed_sections,
                    timestamp_utc=self._clock.now(),
                    defaults_version=defaults_snapshot.product_defaults_version,
                )
                if not changed:
                    raise ConfirmationStaleError(
                        safe_details={"reason": "configuration_revision_mismatch"}
                    )
            if not ProfileOperationIntentRepository(connection).consume(command.operation_id):
                raise ConfirmationInvalidError(safe_details={"reason": "intent_missing"})
            configuration = ProfileConfigurationRepository(connection).get(command.profile_id)
            if scope is ResetScope.WHOLE_PROFILE:
                connection.execute(
                    "DELETE FROM profile_models WHERE profile_id = ?", (str(command.profile_id),)
                )
            return ResetProfileResult(
                command.profile_id,
                scope,
                configuration,
                tuple(section for section in ConfigurationSection if section in changed_sections),
            )

    def confirm_delete(self, command: ConfirmDestructiveOperation) -> DeleteProfileResult:
        if command.target != DestructiveTarget(
            DestructiveOperationKind.DELETE_PROFILE, DeletionScope.WHOLE_PROFILE
        ):
            raise ConfirmationInvalidError(safe_details={"reason": "operation_mismatch"})
        with (
            _translate_sqlite_errors(reason="delete_database_failure"),
            SQLiteDatabase(self._database_path, busy_timeout_ms=self._busy_timeout_ms) as database,
            database.transaction(immediate=True),
        ):
            connection = database.connection()
            _intent, aggregate = self._validate(connection, command)
            if aggregate.profile.kind is ProfileKind.JARVIS:
                raise ProtectedProfileError(safe_details={"operation": "delete"})
            association_count = len(_profile_model_state(connection, command.profile_id))
            items = (
                DestructivePreviewItem("identity", "delete", 1, 0, True),
                DestructivePreviewItem("alias", "delete", 1, 0, True),
                DestructivePreviewItem("configuration", "delete", 1, 0, True),
                DestructivePreviewItem("configuration-sections", "delete", 8, 0, True),
                DestructivePreviewItem("permissions", "delete", 9, 0, True),
                DestructivePreviewItem(
                    "waiting-messages",
                    "delete",
                    len(aggregate.configuration.values.waiting_messages),
                    0,
                    bool(aggregate.configuration.values.waiting_messages),
                ),
                DestructivePreviewItem(
                    "profile-model-associations",
                    "delete",
                    association_count,
                    0,
                    association_count > 0,
                ),
                DestructivePreviewItem(
                    "goodbye-messages",
                    "delete",
                    len(aggregate.configuration.values.goodbye_messages),
                    0,
                    bool(aggregate.configuration.values.goodbye_messages),
                ),
            )
            if not ProfileRepository(connection).delete(command.profile_id):
                raise ConfirmationStaleError(safe_details={"reason": "profile_changed"})
            return DeleteProfileResult(
                profile_id=command.profile_id,
                alias_change=AliasChange(
                    profile_id=command.profile_id,
                    kind=AliasChangeKind.REMOVED,
                    old_alias=aggregate.profile.command_alias,
                    new_alias=None,
                ),
                deleted_items=items,
            )

    def _validate(
        self, connection: sqlite3.Connection, command: ConfirmDestructiveOperation
    ) -> tuple[StoredOperationIntent, ProfileAggregate]:
        repository = ProfileOperationIntentRepository(connection)
        intent = repository.get(command.operation_id)
        if intent is None:
            raise ConfirmationInvalidError(safe_details={"reason": "intent_missing"})
        supplied_digest = _confirmation_token_digest(command.confirmation_token)
        if not hmac.compare_digest(supplied_digest, intent.token_digest_sha256):
            raise ConfirmationInvalidError(safe_details={"reason": "token_mismatch"})
        if self._clock.now() >= intent.expires_at_utc:
            raise ConfirmationExpiredError(safe_details={"reason": "intent_expired"})
        if (
            intent.profile_id != command.profile_id
            or intent.target != command.target
            or intent.operation_id != command.operation_id
        ):
            raise ConfirmationInvalidError(safe_details={"reason": "intent_mismatch"})
        aggregate = ProfileAggregate(
            ProfileRepository(connection).get(command.profile_id),
            ProfileConfigurationRepository(connection).get(command.profile_id),
        )
        if (
            aggregate.profile.identity_revision != intent.expected_identity_revision
            or aggregate.configuration.configuration_revision
            != intent.expected_configuration_revision
        ):
            raise ConfirmationStaleError(safe_details={"reason": "revision_mismatch"})
        recomputed = _state_digest(
            aggregate, command.target, _profile_model_state(connection, command.profile_id)
        )
        if not hmac.compare_digest(recomputed, intent.state_digest_sha256):
            raise ConfirmationStaleError(safe_details={"reason": "state_mismatch"})
        return intent, aggregate
