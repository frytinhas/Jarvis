"""The sole auditable assembler of model input for M006A."""

from __future__ import annotations

from dataclasses import dataclass

from jarvis.chat.errors import ChatContextError
from jarvis.chat.models import (
    ContextContribution,
    ContextProvenance,
    MessageRole,
    StoredMessage,
)

CORE_PROTOCOL_TEXT = (
    "Jarvis local chat protocol: produce assistant text for the current user request."
)
TECHNICAL_FORMATTING_TEXT = "Return the assistant response as valid UTF-8 text."


@dataclass(frozen=True, slots=True)
class BuiltContext:
    contributions: tuple[ContextContribution, ...]
    estimated_tokens: int
    context_window: int
    dropped_conversation_messages: int


class ContextBuilder:
    """Build bounded input in one fixed provenance order without log/tool/memory inputs."""

    def __init__(self, *, max_contribution_bytes: int) -> None:
        self._maximum = max_contribution_bytes

    @staticmethod
    def estimate_tokens(content: str) -> int:
        # Provider-independent conservative accounting. Providers may report exact usage later.
        return max(1, (len(content.encode("utf-8")) + 3) // 4)

    def _contribution(
        self, provenance: ContextProvenance, role: MessageRole, content: str
    ) -> ContextContribution:
        byte_count = len(content.encode("utf-8"))
        if byte_count > self._maximum or "\x00" in content:
            raise ChatContextError("contribution_bound_exceeded")
        return ContextContribution(
            provenance, role, content, byte_count, self.estimate_tokens(content)
        )

    def build(
        self,
        *,
        persona: str,
        profile_context: str,
        user_configured: str,
        conversation: tuple[StoredMessage, ...],
        user_request: str,
        context_window: int,
    ) -> BuiltContext:
        prefix = (
            self._contribution(
                ContextProvenance.CORE_PROTOCOL, MessageRole.SYSTEM, CORE_PROTOCOL_TEXT
            ),
            self._contribution(ContextProvenance.PROFILE_PERSONA, MessageRole.SYSTEM, persona),
            self._contribution(
                ContextProvenance.PROFILE_CONTEXT, MessageRole.SYSTEM, profile_context
            ),
            self._contribution(
                ContextProvenance.USER_CONFIGURED, MessageRole.SYSTEM, user_configured
            ),
            self._contribution(
                ContextProvenance.TECHNICAL_FORMATTING,
                MessageRole.SYSTEM,
                TECHNICAL_FORMATTING_TEXT,
            ),
        )
        current = self._contribution(ContextProvenance.USER_REQUEST, MessageRole.USER, user_request)
        mandatory_tokens = sum(item.estimated_tokens for item in prefix) + current.estimated_tokens
        if mandatory_tokens > context_window:
            raise ChatContextError()
        remaining = context_window - mandatory_tokens
        selected_reversed: list[ContextContribution] = []
        for message in reversed(conversation):
            contribution = self._contribution(
                ContextProvenance.CONVERSATION, message.role, message.content
            )
            if contribution.estimated_tokens > remaining:
                break
            selected_reversed.append(contribution)
            remaining -= contribution.estimated_tokens
        selected = tuple(reversed(selected_reversed))
        contributions = (*prefix, *selected, current)
        return BuiltContext(
            contributions,
            sum(item.estimated_tokens for item in contributions),
            context_window,
            len(conversation) - len(selected),
        )

    @staticmethod
    def accepts(value: object) -> bool:
        """Explicit nominal gate used by security tests and future contribution sources."""

        return isinstance(value, ContextContribution)
