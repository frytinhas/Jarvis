"""Immutable, versioned product defaults loaded from a single packaged resource."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from types import MappingProxyType
from typing import Final

from jarvis.foundation.errors import ConfigurationError

SUPPORTED_DEFAULTS_SCHEMA_VERSION: Final = 1
CURRENT_PRODUCT_DEFAULTS_VERSION: Final = 1
FOUNDATION_DIAGNOSTICS_CATEGORY: Final = "foundation_diagnostics"

_ROOT_KEYS: Final = frozenset(
    {"defaults_schema_version", "product_defaults_version", FOUNDATION_DIAGNOSTICS_CATEGORY}
)
_DIAGNOSTIC_KEYS: Final = frozenset(
    {
        "total_bytes",
        "file_bytes",
        "event_bytes",
        "text_bytes",
        "max_depth",
        "max_container_entries",
        "max_closed_files",
        "retention_days",
    }
)


@dataclass(frozen=True, slots=True)
class DiagnosticDefaults:
    total_bytes: int
    file_bytes: int
    event_bytes: int
    text_bytes: int
    max_depth: int
    max_container_entries: int
    max_closed_files: int
    retention_days: int


@dataclass(frozen=True, slots=True)
class DefaultsSnapshot:
    defaults_schema_version: int
    product_defaults_version: int
    foundation_diagnostics: DiagnosticDefaults


def _require_exact_keys(
    value: Mapping[str, object], expected: frozenset[str], section: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={
                "section": section,
                "missing": ",".join(missing),
                "unknown": ",".join(unknown),
            },
        )


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"field": name, "reason": "expected_positive_integer"},
        )
    return value


def _parse_snapshot(document: Mapping[str, object]) -> DefaultsSnapshot:
    _require_exact_keys(document, _ROOT_KEYS, "root")
    schema_version = _positive_int(document["defaults_schema_version"], "defaults_schema_version")
    product_version = _positive_int(
        document["product_defaults_version"], "product_defaults_version"
    )
    if schema_version != SUPPORTED_DEFAULTS_SCHEMA_VERSION:
        raise ConfigurationError(
            code="defaults.unsupported_version",
            message_key="error.defaults.unsupported_version",
            safe_details={"kind": "schema", "version": schema_version},
        )
    if product_version != CURRENT_PRODUCT_DEFAULTS_VERSION:
        raise ConfigurationError(
            code="defaults.unsupported_version",
            message_key="error.defaults.unsupported_version",
            safe_details={"kind": "product", "version": product_version},
        )
    raw_diagnostics = document[FOUNDATION_DIAGNOSTICS_CATEGORY]
    if not isinstance(raw_diagnostics, dict):
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"section": FOUNDATION_DIAGNOSTICS_CATEGORY},
        )
    _require_exact_keys(raw_diagnostics, _DIAGNOSTIC_KEYS, FOUNDATION_DIAGNOSTICS_CATEGORY)
    diagnostics = DiagnosticDefaults(
        total_bytes=_positive_int(raw_diagnostics["total_bytes"], "total_bytes"),
        file_bytes=_positive_int(raw_diagnostics["file_bytes"], "file_bytes"),
        event_bytes=_positive_int(raw_diagnostics["event_bytes"], "event_bytes"),
        text_bytes=_positive_int(raw_diagnostics["text_bytes"], "text_bytes"),
        max_depth=_positive_int(raw_diagnostics["max_depth"], "max_depth"),
        max_container_entries=_positive_int(
            raw_diagnostics["max_container_entries"], "max_container_entries"
        ),
        max_closed_files=_positive_int(raw_diagnostics["max_closed_files"], "max_closed_files"),
        retention_days=_positive_int(raw_diagnostics["retention_days"], "retention_days"),
    )
    if not diagnostics.text_bytes < diagnostics.event_bytes <= diagnostics.file_bytes:
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={
                "section": FOUNDATION_DIAGNOSTICS_CATEGORY,
                "reason": "inconsistent_bounds",
            },
        )
    if diagnostics.file_bytes > diagnostics.total_bytes:
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={
                "section": FOUNDATION_DIAGNOSTICS_CATEGORY,
                "reason": "inconsistent_bounds",
            },
        )
    return DefaultsSnapshot(schema_version, product_version, diagnostics)


class DefaultsRegistry:
    """Authoritative loader for packaged or explicitly supplied defaults."""

    def __init__(self, snapshot: DefaultsSnapshot) -> None:
        self._snapshot = snapshot

    @classmethod
    def load_packaged(cls) -> DefaultsRegistry:
        resource = files("jarvis.config").joinpath("defaults.toml")
        return cls.from_toml(resource.read_text(encoding="utf-8"))

    @classmethod
    def from_toml(cls, source: str) -> DefaultsRegistry:
        try:
            parsed = tomllib.loads(source)
        except tomllib.TOMLDecodeError as error:
            raise ConfigurationError(
                code="defaults.invalid",
                message_key="error.defaults.invalid",
                internal_message=str(error),
            ) from error
        return cls(_parse_snapshot(parsed))

    def current(self) -> DefaultsSnapshot:
        return self._snapshot


def transition_persisted_defaults(
    values: Mapping[str, object], *, from_version: int, to_version: int
) -> Mapping[str, object]:
    """Apply explicit adjacent defaults transitions; version 1 currently has no transition."""

    if from_version == to_version == CURRENT_PRODUCT_DEFAULTS_VERSION:
        return MappingProxyType(dict(values))
    raise ConfigurationError(
        code="defaults.unsupported_version",
        message_key="error.defaults.unsupported_version",
        safe_details={"from_version": from_version, "to_version": to_version},
    )
