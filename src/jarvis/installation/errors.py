"""Typed failures for user-local installation and repair."""

from jarvis.foundation.errors import JarvisError


class InstallationError(JarvisError):
    default_code = "installation.failed"
    default_message_key = "error.installation.failed"


def installation_error(code: str, **details: str | int | bool | None) -> InstallationError:
    return InstallationError(
        code=code,
        message_key=f"error.{code}",
        safe_details=details,
    )
