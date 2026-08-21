"""Typed, presentation-neutral chat failures."""

from jarvis.foundation.errors import JarvisError


class ChatError(JarvisError):
    def __init__(self, code: str, reason: str = "unknown") -> None:
        super().__init__(code=code, message_key=f"error.{code}", safe_details={"reason": reason})


class ChatContextError(ChatError):
    def __init__(self, reason: str = "mandatory_content_overflow") -> None:
        super().__init__("chat.context_overflow", reason)


class ChatQueueFullError(ChatError):
    def __init__(self) -> None:
        super().__init__("chat.queue_full", "maximum_queued_generations")


class ChatQuiescingError(ChatError):
    """A lifecycle operation has made this profile temporarily unavailable."""

    def __init__(self) -> None:
        super().__init__("chat.profile_quiescing", "profile_lifecycle_operation")


class ChatNotFoundError(ChatError):
    def __init__(self, reason: str = "not_found") -> None:
        super().__init__("chat.not_found", reason)


class ChatStorageError(ChatError):
    def __init__(self, reason: str = "durability_unavailable") -> None:
        super().__init__("chat.storage_unavailable", reason)


class ProviderStreamError(ChatError):
    def __init__(self, reason: str) -> None:
        super().__init__("chat.provider_failed", reason)
