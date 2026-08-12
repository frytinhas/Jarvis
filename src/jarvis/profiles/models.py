"""Typed identity and closed value sets for the profile domain."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import RFC_4122, UUID, uuid4

from jarvis.foundation.clock import normalize_utc


@dataclass(frozen=True, slots=True)
class ProfileId:
    """Opaque profile ownership key backed by a UUID."""

    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4 or self.value.variant != RFC_4122:
            raise ValueError("profile ID must be an RFC 4122 version-4 UUID")

    @classmethod
    def parse(cls, value: str) -> ProfileId:
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError("profile ID must use canonical lowercase UUID text")
        return cls(parsed)

    def __str__(self) -> str:
        return str(self.value)


class ProfileIdGenerator(Protocol):
    def new_profile_id(self) -> ProfileId:
        """Return a new opaque profile identifier."""


class RandomProfileIdGenerator:
    def new_profile_id(self) -> ProfileId:
        return ProfileId(uuid4())


class DeterministicProfileIdGenerator:
    def __init__(self, values: Iterable[UUID]) -> None:
        self._values = deque(values)

    def new_profile_id(self) -> ProfileId:
        try:
            return ProfileId(self._values.popleft())
        except IndexError as error:
            raise RuntimeError("deterministic profile identifier sequence exhausted") from error


class ProfileKind(StrEnum):
    JARVIS = "jarvis"
    STANDARD = "standard"


class VisibleLoggingMode(StrEnum):
    FULL = "full"
    SERVER_ESSENTIAL = "server-essential"
    ESSENTIAL = "essential"
    ESSENTIAL_MINIMUM = "essential-minimum"
    NONE = "none"


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class Capability(StrEnum):
    CREATE = "create"
    COPY = "copy"
    READ = "read"
    SCREEN = "screen"
    INTERNET = "internet"
    EXECUTE = "execute"
    DELETE = "delete"
    MODIFY = "modify"
    MOVE = "move"


class ConfigurationSection(StrEnum):
    PERSONA = "persona"
    PROFILE_CONTEXT = "profile-context"
    APPEARANCE = "appearance"
    WAITING_MESSAGES = "waiting-messages"
    GOODBYE_MESSAGES = "goodbye-messages"
    VISIBLE_LOGGING = "visible-logging"
    STARTUP = "startup"
    PERMISSIONS = "permissions"


ALL_CONFIGURATION_SECTIONS = tuple(ConfigurationSection)
ALL_CAPABILITIES = tuple(Capability)


@dataclass(frozen=True, slots=True)
class Profile:
    profile_id: ProfileId
    kind: ProfileKind
    display_name: str
    command_alias: str
    identity_revision: int
    created_at_utc: datetime
    updated_at_utc: datetime

    def __post_init__(self) -> None:
        if self.identity_revision <= 0:
            raise ValueError("identity revision must be positive")
        object.__setattr__(self, "created_at_utc", normalize_utc(self.created_at_utc))
        object.__setattr__(self, "updated_at_utc", normalize_utc(self.updated_at_utc))


@dataclass(frozen=True, slots=True)
class CreateProfile:
    display_name: str


@dataclass(frozen=True, slots=True)
class RenameProfile:
    profile_id: ProfileId
    display_name: str
    expected_identity_revision: int

    def __post_init__(self) -> None:
        if self.expected_identity_revision <= 0:
            raise ValueError("expected identity revision must be positive")


class AliasChangeKind(StrEnum):
    RENAMED = "renamed"
    REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class AliasChange:
    profile_id: ProfileId
    kind: AliasChangeKind
    old_alias: str
    new_alias: str | None


@dataclass(frozen=True, slots=True)
class RenameResult:
    profile: Profile
    alias_change: AliasChange
