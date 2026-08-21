"""Typed chat identity, persistence, provenance, and lifecycle values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Self
from uuid import RFC_4122, UUID, uuid4

from jarvis.models.models import ModelId
from jarvis.profiles.models import ProfileId


@dataclass(frozen=True, slots=True)
class _ChatUuid:
    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4 or self.value.variant != RFC_4122:
            raise ValueError("chat identifier must be an RFC 4122 version-4 UUID")

    @classmethod
    def new(cls) -> Self:
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> Self:
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError("chat identifier must use canonical lowercase UUID text")
        return cls(parsed)

    def __str__(self) -> str:
        return str(self.value)


class SessionId(_ChatUuid):
    pass


class TurnId(_ChatUuid):
    pass


class MessageId(_ChatUuid):
    pass


class DiagnosticId(_ChatUuid):
    pass


class TurnState(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LearningStatus(StrEnum):
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ContextProvenance(StrEnum):
    CORE_PROTOCOL = "CORE_PROTOCOL"
    PROFILE_PERSONA = "PROFILE_PERSONA"
    PROFILE_CONTEXT = "PROFILE_CONTEXT"
    USER_CONFIGURED = "USER_CONFIGURED"
    TECHNICAL_FORMATTING = "TECHNICAL_FORMATTING"
    CONVERSATION = "CONVERSATION"
    USER_REQUEST = "USER_REQUEST"


@dataclass(frozen=True, slots=True)
class ContextContribution:
    provenance: ContextProvenance
    role: MessageRole
    content: str
    byte_count: int
    estimated_tokens: int


@dataclass(frozen=True, slots=True)
class StoredMessage:
    message_id: MessageId
    session_id: SessionId
    profile_id: ProfileId
    model_id: ModelId
    turn_id: TurnId
    ordinal: int
    role: MessageRole
    content: str
    created_at_utc: str


@dataclass(frozen=True, slots=True)
class TurnSnapshot:
    turn_id: TurnId
    request_id: str
    session_id: SessionId
    profile_id: ProfileId
    model_id: ModelId
    state: TurnState
    partial_text: str
    partial_truncated: bool
    failure_code: str | None
    created_at_utc: str
    started_at_utc: str | None
    completed_at_utc: str | None

    def to_safe_mapping(self) -> dict[str, object]:
        return {
            "turn_id": str(self.turn_id),
            "request_id": self.request_id,
            "session_id": str(self.session_id),
            "profile_id": str(self.profile_id),
            "model_id": str(self.model_id),
            "state": self.state.value,
            "partial_text": self.partial_text,
            "partial_truncated": self.partial_truncated,
            "failure_code": self.failure_code,
            "created_at_utc": self.created_at_utc,
            "started_at_utc": self.started_at_utc,
            "completed_at_utc": self.completed_at_utc,
        }


@dataclass(frozen=True, slots=True)
class LearningSnapshot:
    profile_id: ProfileId
    model_id: ModelId
    status: LearningStatus
    started_at_utc: str
    updated_at_utc: str
    finished_at_utc: str | None
    revision: int

    def to_safe_mapping(self) -> dict[str, object]:
        return {
            "profile_id": str(self.profile_id),
            "model_id": str(self.model_id),
            "status": self.status.value,
            "started_at_utc": self.started_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "revision": self.revision,
        }
