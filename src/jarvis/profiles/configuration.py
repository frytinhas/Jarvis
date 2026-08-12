"""Validated immutable profile configuration values and revision metadata."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from jarvis.config.defaults import ProfileDefaults
from jarvis.profiles.errors import ProfileConfigurationError
from jarvis.profiles.models import (
    ALL_CAPABILITIES,
    ALL_CONFIGURATION_SECTIONS,
    Capability,
    ConfigurationSection,
    PermissionDecision,
    Profile,
    ProfileId,
    VisibleLoggingMode,
)

PROFILE_CONFIG_SCHEMA_VERSION: Final = 1
MAX_PERSONA_BYTES: Final = 32 * 1024
MAX_PROFILE_CONTEXT_BYTES: Final = 64 * 1024
MAX_MESSAGES: Final = 16
MAX_MESSAGE_CODEPOINTS: Final = 256
MAX_MESSAGE_BYTES: Final = 1024
_COLOR_PATTERN: Final = re.compile(r"^#[0-9a-f]{6}$")


def _invalid(field: str, reason: str) -> ProfileConfigurationError:
    return ProfileConfigurationError(safe_details={"field": field, "reason": reason})


def _bounded_text(value: object, *, field: str, max_bytes: int) -> str:
    if not isinstance(value, str):
        raise _invalid(field, "expected_string")
    if "\x00" in value:
        raise _invalid(field, "nul_not_allowed")
    if len(value.encode("utf-8")) > max_bytes:
        raise _invalid(field, "too_many_bytes")
    return value


def validate_color(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _COLOR_PATTERN.fullmatch(value) is None:
        raise _invalid(field, "invalid_color")
    return value


def validate_messages(value: object, *, field: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise _invalid(field, "expected_sequence")
    if len(value) > MAX_MESSAGES:
        raise _invalid(field, "too_many_messages")
    messages: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise _invalid(field, "message_not_string")
        normalized = unicodedata.normalize("NFC", item)
        if not normalized:
            raise _invalid(field, "empty_message")
        if any(character in normalized for character in ("\x00", "\n", "\r")):
            raise _invalid(field, "message_not_single_line")
        if len(normalized) > MAX_MESSAGE_CODEPOINTS:
            raise _invalid(field, "message_too_many_codepoints")
        if len(normalized.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise _invalid(field, "message_too_many_bytes")
        messages.append(normalized)
    return tuple(messages)


def validate_permissions(
    value: Mapping[Capability, PermissionDecision] | Mapping[str, str],
) -> Mapping[Capability, PermissionDecision]:
    if not isinstance(value, Mapping):
        raise _invalid("permissions", "expected_mapping")
    parsed: dict[Capability, PermissionDecision] = {}
    try:
        for raw_capability, raw_decision in value.items():
            capability = (
                raw_capability
                if isinstance(raw_capability, Capability)
                else Capability(raw_capability)
            )
            decision = (
                raw_decision
                if isinstance(raw_decision, PermissionDecision)
                else PermissionDecision(raw_decision)
            )
            parsed[capability] = decision
    except (TypeError, ValueError) as error:
        raise _invalid("permissions", "invalid_entry") from error
    if frozenset(parsed) != frozenset(ALL_CAPABILITIES):
        raise _invalid("permissions", "capabilities_mismatch")
    return MappingProxyType(parsed)


@dataclass(frozen=True, slots=True)
class AppearanceConfiguration:
    accent_color: str
    foreground_color: str
    background_color: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "accent_color", validate_color(self.accent_color, field="accent_color")
        )
        object.__setattr__(
            self,
            "foreground_color",
            validate_color(self.foreground_color, field="foreground_color"),
        )
        object.__setattr__(
            self,
            "background_color",
            validate_color(self.background_color, field="background_color"),
        )


@dataclass(frozen=True, slots=True)
class ProfileConfigurationValues:
    persona_text: str
    profile_context_text: str
    appearance: AppearanceConfiguration
    waiting_messages: tuple[str, ...]
    goodbye_messages: tuple[str, ...]
    visible_logging_mode: VisibleLoggingMode
    start_with_computer: bool
    permissions: Mapping[Capability, PermissionDecision]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "persona_text",
            _bounded_text(self.persona_text, field="persona_text", max_bytes=MAX_PERSONA_BYTES),
        )
        object.__setattr__(
            self,
            "profile_context_text",
            _bounded_text(
                self.profile_context_text,
                field="profile_context_text",
                max_bytes=MAX_PROFILE_CONTEXT_BYTES,
            ),
        )
        object.__setattr__(
            self,
            "waiting_messages",
            validate_messages(self.waiting_messages, field="waiting_messages"),
        )
        object.__setattr__(
            self,
            "goodbye_messages",
            validate_messages(self.goodbye_messages, field="goodbye_messages"),
        )
        try:
            logging_mode = VisibleLoggingMode(self.visible_logging_mode)
        except (TypeError, ValueError) as error:
            raise _invalid("visible_logging_mode", "invalid_choice") from error
        object.__setattr__(self, "visible_logging_mode", logging_mode)
        if type(self.start_with_computer) is not bool:
            raise _invalid("start_with_computer", "expected_boolean")
        object.__setattr__(self, "permissions", validate_permissions(self.permissions))

    @classmethod
    def from_defaults(cls, defaults: ProfileDefaults) -> ProfileConfigurationValues:
        return cls(
            persona_text=defaults.persona_text,
            profile_context_text=defaults.profile_context_text,
            appearance=AppearanceConfiguration(
                defaults.accent_color,
                defaults.foreground_color,
                defaults.background_color,
            ),
            waiting_messages=defaults.waiting_messages,
            goodbye_messages=defaults.goodbye_messages,
            visible_logging_mode=VisibleLoggingMode(defaults.visible_logging_mode),
            start_with_computer=defaults.start_with_computer,
            permissions={
                Capability(capability): PermissionDecision(decision)
                for capability, decision in defaults.permissions.items()
            },
        )


@dataclass(frozen=True, slots=True)
class SectionRevision:
    section: ConfigurationSection
    defaults_version: int
    revision: int

    def __post_init__(self) -> None:
        if self.defaults_version <= 0 or self.revision <= 0:
            raise ValueError("section defaults version and revision must be positive")


def validate_section_revisions(
    revisions: Mapping[ConfigurationSection, SectionRevision],
) -> Mapping[ConfigurationSection, SectionRevision]:
    copied = dict(revisions)
    if frozenset(copied) != frozenset(ALL_CONFIGURATION_SECTIONS):
        raise ValueError("configuration must contain every section revision")
    if any(section != revision.section for section, revision in copied.items()):
        raise ValueError("section revision key does not match its value")
    return MappingProxyType(copied)


@dataclass(frozen=True, slots=True)
class ProfileConfiguration:
    profile_id: ProfileId
    config_schema_version: int
    configuration_revision: int
    values: ProfileConfigurationValues
    section_revisions: Mapping[ConfigurationSection, SectionRevision]

    def __post_init__(self) -> None:
        if self.config_schema_version != PROFILE_CONFIG_SCHEMA_VERSION:
            raise ValueError("unsupported profile configuration schema version")
        if self.configuration_revision <= 0:
            raise ValueError("configuration revision must be positive")
        object.__setattr__(
            self, "section_revisions", validate_section_revisions(self.section_revisions)
        )


@dataclass(frozen=True, slots=True)
class ProfileAggregate:
    profile: Profile
    configuration: ProfileConfiguration


@dataclass(frozen=True, slots=True)
class UpdateProfileConfiguration:
    profile_id: ProfileId
    expected_identity_revision: int
    expected_configuration_revision: int
    values: ProfileConfigurationValues

    def __post_init__(self) -> None:
        if self.expected_identity_revision <= 0 or self.expected_configuration_revision <= 0:
            raise ValueError("expected identity and configuration revisions must be positive")


type ProfileSectionValue = (
    str
    | AppearanceConfiguration
    | tuple[str, ...]
    | VisibleLoggingMode
    | bool
    | Mapping[Capability, PermissionDecision]
)


@dataclass(frozen=True, slots=True)
class ProfileConfigurationSectionSnapshot:
    profile_id: ProfileId
    section: ConfigurationSection
    value: ProfileSectionValue
    revision: SectionRevision


def section_value(
    values: ProfileConfigurationValues, section: ConfigurationSection
) -> ProfileSectionValue:
    match section:
        case ConfigurationSection.PERSONA:
            return values.persona_text
        case ConfigurationSection.PROFILE_CONTEXT:
            return values.profile_context_text
        case ConfigurationSection.APPEARANCE:
            return values.appearance
        case ConfigurationSection.WAITING_MESSAGES:
            return values.waiting_messages
        case ConfigurationSection.GOODBYE_MESSAGES:
            return values.goodbye_messages
        case ConfigurationSection.VISIBLE_LOGGING:
            return values.visible_logging_mode
        case ConfigurationSection.STARTUP:
            return values.start_with_computer
        case ConfigurationSection.PERMISSIONS:
            return values.permissions
