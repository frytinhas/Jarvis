"""Safe typed errors for the local IPC boundary."""

from __future__ import annotations

from jarvis.foundation.errors import JarvisError


class IpcError(JarvisError):
    """Base error for protocol, transport, and Core-ownership failures."""

    default_code = "ipc.internal_error"
    default_message_key = "error.ipc.internal_error"


def ipc_error(code: str, **details: str | int | bool | None) -> IpcError:
    """Create a safe IPC error whose localization key follows its stable code."""

    return IpcError(code=code, message_key=f"error.{code}", safe_details=details)
