from __future__ import annotations

from uuid import uuid4

import pytest

from jarvis.chat.context import CORE_PROTOCOL_TEXT, TECHNICAL_FORMATTING_TEXT, ContextBuilder
from jarvis.chat.errors import ChatContextError
from jarvis.chat.models import (
    ContextProvenance,
    MessageId,
    MessageRole,
    SessionId,
    StoredMessage,
    TurnId,
)
from jarvis.models.models import ModelId
from jarvis.profiles.models import ProfileId

pytestmark = pytest.mark.unit


def _message(ordinal: int, content: str) -> StoredMessage:
    return StoredMessage(
        MessageId(uuid4()),
        SessionId(uuid4()),
        ProfileId(uuid4()),
        ModelId(uuid4()),
        TurnId(uuid4()),
        ordinal,
        MessageRole.USER if ordinal % 2 == 0 else MessageRole.ASSISTANT,
        content,
        "2026-08-21T00:00:00.000000Z",
    )


def test_context_has_exact_order_provenance_and_no_hidden_policy() -> None:
    builder = ContextBuilder(max_contribution_bytes=65_536)
    built = builder.build(
        persona="PERSONA_SENTINEL",
        profile_context="CONTEXT_SENTINEL",
        user_configured="USER_CONFIG_SENTINEL",
        conversation=(_message(0, "HISTORY_SENTINEL"),),
        user_request="malware analysis and offensive security",
        context_window=4096,
    )
    assert [item.provenance for item in built.contributions] == [
        ContextProvenance.CORE_PROTOCOL,
        ContextProvenance.PROFILE_PERSONA,
        ContextProvenance.PROFILE_CONTEXT,
        ContextProvenance.USER_CONFIGURED,
        ContextProvenance.TECHNICAL_FORMATTING,
        ContextProvenance.CONVERSATION,
        ContextProvenance.USER_REQUEST,
    ]
    assert built.contributions[0].content == CORE_PROTOCOL_TEXT
    assert built.contributions[4].content == TECHNICAL_FORMATTING_TEXT
    joined = "\n".join(item.content for item in built.contributions).casefold()
    for forbidden in (
        "openai policy",
        "anthropic policy",
        "harmful content",
        "cybersecurity restriction",
        "refuse malware",
    ):
        assert forbidden not in joined


def test_context_drops_oldest_conversation_first_and_preserves_mandatory_content() -> None:
    builder = ContextBuilder(max_contribution_bytes=65_536)
    base = builder.build(
        persona="persona",
        profile_context="context",
        user_configured="configured",
        conversation=(),
        user_request="request",
        context_window=4096,
    )
    newest = _message(2, "newest")
    newest_tokens = builder.estimate_tokens(newest.content)
    built = builder.build(
        persona="persona",
        profile_context="context",
        user_configured="configured",
        conversation=(_message(0, "oldest is deliberately much larger"), newest),
        user_request="request",
        context_window=base.estimated_tokens + newest_tokens,
    )
    conversation = [
        item.content
        for item in built.contributions
        if item.provenance is ContextProvenance.CONVERSATION
    ]
    assert conversation == ["newest"]
    assert built.dropped_conversation_messages == 1


def test_mandatory_context_overflow_fails_before_generation() -> None:
    builder = ContextBuilder(max_contribution_bytes=65_536)
    with pytest.raises(ChatContextError) as caught:
        builder.build(
            persona="mandatory persona",
            profile_context="mandatory context",
            user_configured="configured",
            conversation=(),
            user_request="mandatory request",
            context_window=1,
        )
    assert caught.value.code == "chat.context_overflow"


def test_context_builder_rejects_nominal_human_diagnostic_type() -> None:
    from jarvis.chat.diagnostics import HumanDiagnosticSummary

    assert not ContextBuilder.accepts(HumanDiagnosticSummary("turn", (), False))
