"""Sanitized runtime-manager failures."""

from __future__ import annotations

from jarvis.foundation.errors import JarvisError


class RuntimeManagerError(JarvisError):
    def __init__(self, code: str, reason: str = "unknown") -> None:
        super().__init__(code=code, message_key=f"error.{code}", safe_details={"reason": reason})


class RuntimeNotConfiguredError(RuntimeManagerError):
    def __init__(self, reason: str = "not_configured") -> None:
        super().__init__("runtime.not_configured", reason)


class RuntimeModelInvalidError(RuntimeManagerError):
    def __init__(self, reason: str = "model_invalid") -> None:
        super().__init__("runtime.model_invalid", reason)


class RuntimeAlreadyActiveError(RuntimeManagerError):
    def __init__(self, reason: str = "already_active") -> None:
        super().__init__("runtime.already_active", reason)


class RuntimeCapacityError(RuntimeManagerError):
    def __init__(self, reason: str = "pending_limit") -> None:
        super().__init__("runtime.capacity_exhausted", reason)


class RuntimeEndpointError(RuntimeManagerError):
    def __init__(self, reason: str = "endpoint_unavailable") -> None:
        super().__init__("runtime.endpoint_unavailable", reason)


class RuntimeStartupError(RuntimeManagerError):
    def __init__(self, reason: str = "startup_failed") -> None:
        super().__init__("runtime.start_failed", reason)


class RuntimeOwnershipError(RuntimeManagerError):
    def __init__(self, reason: str = "ambiguous_ownership") -> None:
        super().__init__("runtime.ownership_ambiguous", reason)


class RuntimeArtifactError(RuntimeManagerError):
    def __init__(self, reason: str = "invalid_artifact") -> None:
        super().__init__("runtime.artifact_invalid", reason)


class RuntimePolicyConflictError(RuntimeManagerError):
    def __init__(self, reason: str = "revision_mismatch") -> None:
        super().__init__("runtime.policy_conflict", reason)


class RuntimeDatabaseError(RuntimeManagerError):
    def __init__(self, reason: str = "database") -> None:
        super().__init__("runtime.database_error", reason)


class RuntimeSwitchRequiredError(RuntimeManagerError):
    def __init__(self) -> None:
        super().__init__("runtime.switch_required", "active_runtime")


class RuntimePartialCleanupError(RuntimeManagerError):
    def __init__(self) -> None:
        super().__init__("runtime.partial_cleanup", "database_confirmation_failed")


class UnsupportedExtraArgumentsError(RuntimeManagerError):
    def __init__(self) -> None:
        super().__init__("runtime.unsupported_extra_arguments", "unsupported")
