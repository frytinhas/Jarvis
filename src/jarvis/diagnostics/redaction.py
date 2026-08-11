"""Central recursive secret redaction with deterministic structural bounds."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import islice

type JsonScalar = str | int | float | bool | None
type SanitizedValue = JsonScalar | dict[str, SanitizedValue] | list[SanitizedValue]

REDACTED = "[REDACTED]"
TRUNCATED = "[TRUNCATED]"
DEPTH_LIMIT = "[DEPTH_LIMIT]"
_TRUNCATION_OVERLAP_BYTES = 256

_DEFAULT_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "apikey",
        "authorization",
        "proxyauthorization",
        "cookie",
        "setcookie",
        "privatekey",
        "clientsecret",
        "accesstoken",
        "refreshtoken",
        "credential",
        "credentials",
    }
)
_SENSITIVE_KEY_MARKERS = (
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

_PEM_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_AUTHORIZATION = re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]+")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\b")
_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|client[_-]?secret|credentials?)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_SENSITIVE_HEADER = re.compile(
    r"(?im)^(authorization|proxy-authorization|cookie|set-cookie)\s*:\s*[^\r\n]*"
)
_URL_USERINFO = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)[^/@\s:]+:[^/@\s]+@")
_QUERY_SECRET = re.compile(
    r"(?i)([?&](?:password|passwd|secret|token|api[_-]?key|access_token|refresh_token)=)"
    r"[^&#\s]*"
)


def _normalize_key(key: str) -> str:
    return "".join(character for character in key.casefold() if character.isalnum())


def _looks_sensitive_key(key: str, configured: frozenset[str]) -> bool:
    normalized = _normalize_key(key)
    return normalized in configured or any(
        marker in normalized for marker in _SENSITIVE_KEY_MARKERS
    )


@dataclass(frozen=True, slots=True)
class RedactionMetadata:
    redacted_values: int = 0
    truncated_values: int = 0
    dropped_items: int = 0
    depth_limited_values: int = 0

    def changed(self) -> bool:
        return any(
            (
                self.redacted_values,
                self.truncated_values,
                self.dropped_items,
                self.depth_limited_values,
            )
        )


@dataclass(frozen=True, slots=True)
class RedactionResult:
    value: SanitizedValue
    metadata: RedactionMetadata


@dataclass
class _Counts:
    redacted_values: int = 0
    truncated_values: int = 0
    dropped_items: int = 0
    depth_limited_values: int = 0

    def snapshot(self) -> RedactionMetadata:
        return RedactionMetadata(
            self.redacted_values,
            self.truncated_values,
            self.dropped_items,
            self.depth_limited_values,
        )


class Redactor:
    """Privacy-favoring redactor for explicitly supplied diagnostic values."""

    def __init__(
        self,
        *,
        max_text_bytes: int,
        max_depth: int,
        max_container_entries: int,
        sensitive_environment_names: Sequence[str] = (),
    ) -> None:
        if max_text_bytes < len(TRUNCATED.encode()) + 1:
            raise ValueError("max_text_bytes is too small")
        if max_depth <= 0 or max_container_entries <= 0:
            raise ValueError("structural bounds must be positive")
        self.max_text_bytes = max_text_bytes
        self.max_depth = max_depth
        self.max_container_entries = max_container_entries
        self._sensitive_keys = _DEFAULT_SENSITIVE_KEYS | {
            _normalize_key(name) for name in sensitive_environment_names
        }

    def redact_text(self, text: str) -> RedactionResult:
        counts = _Counts()
        sanitized = self._bounded_text(text, counts)
        sanitized = self._redact_patterns(sanitized, counts)
        return RedactionResult(sanitized, counts.snapshot())

    def redact_value(self, value: object) -> RedactionResult:
        counts = _Counts()
        sanitized = self._value(value, depth=0, counts=counts)
        return RedactionResult(sanitized, counts.snapshot())

    def _value(self, value: object, *, depth: int, counts: _Counts) -> SanitizedValue:
        if value is None or isinstance(value, bool | int | float):
            return value
        if isinstance(value, str):
            return self._redact_patterns(self._bounded_text(value, counts), counts)
        if isinstance(value, Mapping):
            if depth >= self.max_depth:
                counts.depth_limited_values += 1
                return DEPTH_LIMIT
            result: dict[str, SanitizedValue] = {}
            items = list(islice(value.items(), self.max_container_entries + 1))
            if len(items) > self.max_container_entries:
                counts.dropped_items += 1
            for raw_key, child in items[: self.max_container_entries]:
                key = raw_key if isinstance(raw_key, str) else str(raw_key)
                bounded_key = self._redact_patterns(self._bounded_text(key, counts), counts)
                if bounded_key in result:
                    counts.dropped_items += 1
                    continue
                if _looks_sensitive_key(key, self._sensitive_keys):
                    result[bounded_key] = REDACTED
                    counts.redacted_values += 1
                else:
                    result[bounded_key] = self._value(child, depth=depth + 1, counts=counts)
            return result
        if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | memoryview):
            if depth >= self.max_depth:
                counts.depth_limited_values += 1
                return DEPTH_LIMIT
            items = list(islice(value, self.max_container_entries + 1))
            if len(items) > self.max_container_entries:
                counts.dropped_items += 1
            return [
                self._value(child, depth=depth + 1, counts=counts)
                for child in items[: self.max_container_entries]
            ]
        return self._redact_patterns(self._bounded_text(str(value), counts), counts)

    def _bounded_text(self, text: str, counts: _Counts) -> str:
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= self.max_text_bytes:
            return text
        placeholder = TRUNCATED.encode("utf-8")
        retained_bytes = max(
            0,
            self.max_text_bytes - len(placeholder) - _TRUNCATION_OVERLAP_BYTES,
        )
        retained = encoded[:retained_bytes].decode("utf-8", errors="ignore")
        counts.truncated_values += 1
        return retained + TRUNCATED

    @staticmethod
    def _redact_patterns(text: str, counts: _Counts) -> str:
        def replace_whole(match: re.Match[str]) -> str:
            counts.redacted_values += 1
            return REDACTED

        def replace_assignment(match: re.Match[str]) -> str:
            counts.redacted_values += 1
            return f"{match.group(1)}{match.group(2)}{REDACTED}"

        def replace_header(match: re.Match[str]) -> str:
            counts.redacted_values += 1
            return f"{match.group(1)}: {REDACTED}"

        def replace_userinfo(match: re.Match[str]) -> str:
            counts.redacted_values += 1
            return f"{match.group(1)}{REDACTED}@"

        def replace_query(match: re.Match[str]) -> str:
            counts.redacted_values += 1
            return f"{match.group(1)}{REDACTED}"

        text = _PEM_PRIVATE_KEY.sub(replace_whole, text)
        text = _SENSITIVE_HEADER.sub(replace_header, text)
        text = _AUTHORIZATION.sub(replace_whole, text)
        text = _JWT.sub(replace_whole, text)
        text = _ASSIGNMENT.sub(replace_assignment, text)
        text = _URL_USERINFO.sub(replace_userinfo, text)
        return _QUERY_SECRET.sub(replace_query, text)
