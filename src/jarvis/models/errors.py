"""Sanitized model-registry failures."""

from jarvis.foundation.errors import JarvisError


class ModelError(JarvisError):
    def __init__(self, code: str, *, reason: str = "unknown") -> None:
        super().__init__(code=code, message_key=f"error.{code}", safe_details={"reason": reason})


class InvalidGgufError(ModelError):
    def __init__(self, reason: str = "invalid") -> None:
        super().__init__("model.invalid_gguf", reason=reason)


class UnreadableModelError(ModelError):
    def __init__(self, reason: str = "unreadable") -> None:
        super().__init__("model.unreadable", reason=reason)


class ModelUnavailableError(ModelError):
    def __init__(self) -> None:
        super().__init__("model.unavailable")


class ModelNotFoundError(ModelError):
    def __init__(self) -> None:
        super().__init__("model.not_found")


class InvalidRuntimeConfigurationError(ModelError):
    def __init__(self, reason: str = "invalid") -> None:
        super().__init__("model.invalid_runtime_configuration", reason=reason)


class InvalidRuntimeLocationError(ModelError):
    def __init__(self, reason: str = "invalid") -> None:
        super().__init__("model.invalid_runtime_location", reason=reason)


class ScanLimitExceededError(ModelError):
    def __init__(self, reason: str) -> None:
        super().__init__("model.scan_limit_exceeded", reason=reason)


class ConcurrentModelModificationError(ModelError):
    def __init__(self, reason: str = "conflict") -> None:
        super().__init__("model.concurrent_modification", reason=reason)


class ModelDatabaseError(ModelError):
    def __init__(self, reason: str = "database") -> None:
        super().__init__("model.database_error", reason=reason)
