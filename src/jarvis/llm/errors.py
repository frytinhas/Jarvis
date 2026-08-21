"""Provider-boundary aliases for sanitized runtime failures."""

from jarvis.runtimes.errors import (
    RuntimeEndpointError,
    RuntimeOwnershipError,
    RuntimeStartupError,
    UnsupportedExtraArgumentsError,
)

__all__ = [
    "RuntimeEndpointError",
    "RuntimeOwnershipError",
    "RuntimeStartupError",
    "UnsupportedExtraArgumentsError",
]
