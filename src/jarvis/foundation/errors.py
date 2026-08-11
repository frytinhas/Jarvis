"""Typed foundation errors with a deliberately narrow safe representation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from jarvis.foundation.identifiers import CorrelationId

type SafeScalar = str | int | bool | None
SAFE_ERROR_ENVELOPE_VERSION: Final = 1
_SAFE_ERROR_NAME: Final = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_SENSITIVE_DETAIL_MARKERS: Final = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "authorization",
    "cookie",
    "privatekey",
    "credential",
)


def _normalized_name(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _safe_details(details: Mapping[str, SafeScalar] | None) -> Mapping[str, SafeScalar]:
    if details is None:
        return MappingProxyType({})
    copied: dict[str, SafeScalar] = {}
    for key, value in details.items():
        if not isinstance(key, str):
            raise TypeError("safe error detail keys must be strings")
        normalized = _normalized_name(key)
        if any(marker in normalized for marker in _SENSITIVE_DETAIL_MARKERS):
            raise TypeError("safe error detail keys must not identify secrets")
        if value is not None and not isinstance(value, str | int | bool):
            raise TypeError("safe error detail values must be scalar JSON values")
        copied[key] = value
    return MappingProxyType(copied)


class JarvisError(Exception):
    """Root internal error with a localization-ready, serialization-safe projection."""

    default_code: str = "foundation.error"
    default_message_key: str = "error.foundation"

    def __init__(
        self,
        *,
        code: str | None = None,
        message_key: str | None = None,
        correlation_id: CorrelationId | None = None,
        safe_details: Mapping[str, SafeScalar] | None = None,
        internal_message: str | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.message_key = message_key or self.default_message_key
        if _SAFE_ERROR_NAME.fullmatch(self.code) is None:
            raise ValueError("error code must be a stable dotted lowercase identifier")
        if _SAFE_ERROR_NAME.fullmatch(self.message_key) is None:
            raise ValueError("message key must be a stable dotted lowercase identifier")
        self.correlation_id = correlation_id
        self.safe_details = _safe_details(safe_details)
        self.internal_message = internal_message
        super().__init__(internal_message or self.code)

    def to_safe_dict(self) -> dict[str, object]:
        """Return only fields explicitly allowed to cross a future process boundary."""

        result: dict[str, object] = {
            "envelope_version": SAFE_ERROR_ENVELOPE_VERSION,
            "code": self.code,
            "message_key": self.message_key,
            "details": dict(self.safe_details),
        }
        if self.correlation_id is not None:
            result["correlation_id"] = str(self.correlation_id)
        return result


class ConfigurationError(JarvisError):
    """Configuration or path-resolution failure."""


class StorageError(JarvisError):
    """Persistent or bounded-storage failure."""


class DiagnosticError(JarvisError):
    """Diagnostic validation or persistence failure."""


class SecurityBoundaryError(JarvisError):
    """Ambiguous or denied security-boundary evaluation."""
