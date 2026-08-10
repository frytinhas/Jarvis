"""Small, deterministic guard for text that is about to reach the model."""
from __future__ import annotations

import re


_CHAT_PROTOCOL = re.compile(
    r"<\|(?:im_start|im_end|system|user|assistant|tool|endoftext)\|>", re.IGNORECASE
)


def unsafe_chat_input_reason(text: str) -> str | None:
    """Return a human-readable reason for model-role protocol impersonation.

    This deliberately detects only protocol delimiters. Ordinary prose, code, and
    questions must remain valid user input; tool policy remains the security
    boundary for all other content.
    """
    if _CHAT_PROTOCOL.search(text):
        return "marcadores que tentam imitar mensagens internas do modelo"
    return None


def validate_learning_summary(text: str) -> str | None:
    """Reject a proposed onboarding summary that is not durable profile data."""
    if unsafe_chat_input_reason(text):
        return "marcadores internos de chat"
    if "```" in text:
        return "blocos de código"
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"(?:[$#]\s+|(?:sudo|find|nano|bash|sh|python(?:3)?|rm|cp|mv|curl|wget)\b)", stripped, re.IGNORECASE):
            return "comandos de terminal"
    return None
