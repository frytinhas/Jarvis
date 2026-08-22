"""Immutable, versioned product defaults loaded from a single packaged resource."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from types import MappingProxyType
from typing import Final

from jarvis.foundation.errors import ConfigurationError

SUPPORTED_DEFAULTS_SCHEMA_VERSION: Final = 5
CURRENT_PRODUCT_DEFAULTS_VERSION: Final = 6
FOUNDATION_DIAGNOSTICS_CATEGORY: Final = "foundation_diagnostics"
PROFILE_DEFAULTS_CATEGORY: Final = "profile_defaults"
MODEL_DEFAULTS_CATEGORY: Final = "model_defaults"
RUNTIME_MANAGER_CATEGORY: Final = "runtime_manager"
CHAT_CATEGORY: Final = "chat"

_ROOT_KEYS: Final = frozenset(
    {
        "defaults_schema_version",
        "product_defaults_version",
        FOUNDATION_DIAGNOSTICS_CATEGORY,
        PROFILE_DEFAULTS_CATEGORY,
        MODEL_DEFAULTS_CATEGORY,
        RUNTIME_MANAGER_CATEGORY,
        CHAT_CATEGORY,
    }
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
_PROFILE_KEYS: Final = frozenset(
    {
        "persona_text",
        "profile_context_text",
        "accent_color",
        "foreground_color",
        "background_color",
        "waiting_messages",
        "goodbye_messages",
        "visible_logging_mode",
        "start_with_computer",
        "permissions",
    }
)
_PERMISSION_KEYS: Final = frozenset(
    {"create", "copy", "read", "screen", "internet", "execute", "delete", "modify", "move"}
)
_PERMISSION_VALUES: Final = frozenset({"allow", "ask", "deny"})
_LOGGING_MODES: Final = frozenset(
    {"full", "server-essential", "essential", "essential-minimum", "none"}
)

# Product-default provenance is retained on each persisted profile configuration
# section.  These are the explicit historical transitions that can lead to the
# currently packaged defaults, not a range inferred from integer ordering.
_SUPPORTED_PERSISTED_DEFAULTS_TRANSITIONS: Final = frozenset(
    {
        (2, 2),
        (2, 3),
        (2, 4),
        (2, 5),
        (2, 6),
        (3, 3),
        (3, 4),
        (3, 5),
        (3, 6),
        (4, 4),
        (4, 5),
        (4, 6),
        (5, 5),
        (5, 6),
        (6, 6),
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
class ProfileDefaults:
    persona_text: str
    profile_context_text: str
    accent_color: str
    foreground_color: str
    background_color: str
    waiting_messages: tuple[str, ...]
    goodbye_messages: tuple[str, ...]
    visible_logging_mode: str
    start_with_computer: bool
    permissions: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ModelDefaults:
    reasoning: str
    context_window: int
    runtime_config: Mapping[str, object]
    scanner_limits: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class RuntimeManagerDefaults:
    max_concurrent_runtimes: int
    max_pending_starts: int
    stream_capture_bytes: int
    event_retention_count: int
    endpoint_allocation_attempts: int


@dataclass(frozen=True, slots=True)
class ChatDefaults:
    max_message_bytes: int
    max_partial_bytes: int
    max_session_bytes: int
    max_diagnostic_bytes: int
    minimum_diagnostic_reservation_bytes: int
    max_diagnostic_summary_bytes: int
    max_context_contribution_bytes: int
    max_provider_delta_bytes: int
    max_sse_frame_bytes: int
    max_sse_response_bytes: int
    max_queued_generations: int


@dataclass(frozen=True, slots=True)
class DefaultsSnapshot:
    defaults_schema_version: int
    product_defaults_version: int
    foundation_diagnostics: DiagnosticDefaults
    profile_defaults: ProfileDefaults
    model_defaults: ModelDefaults
    runtime_manager: RuntimeManagerDefaults
    chat: ChatDefaults


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


def _context_window(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000:
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"field": name, "reason": "invalid_context_window"},
        )
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"field": name, "reason": "expected_string"},
        )
    return value


def _string_tuple(value: object, name: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or len(value) > 16
        or any(not isinstance(item, str) for item in value)
    ):
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"field": name, "reason": "expected_string_array"},
        )
    return tuple(value)


def _parse_profile_defaults(value: object) -> ProfileDefaults:
    if not isinstance(value, dict):
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"section": PROFILE_DEFAULTS_CATEGORY},
        )
    _require_exact_keys(value, _PROFILE_KEYS, PROFILE_DEFAULTS_CATEGORY)
    raw_permissions = value["permissions"]
    if not isinstance(raw_permissions, dict):
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"section": "profile_defaults.permissions"},
        )
    _require_exact_keys(raw_permissions, _PERMISSION_KEYS, "profile_defaults.permissions")
    permissions: dict[str, str] = {}
    for capability, raw_decision in raw_permissions.items():
        decision = _string(raw_decision, f"permissions.{capability}")
        if decision not in _PERMISSION_VALUES:
            raise ConfigurationError(
                code="defaults.invalid",
                message_key="error.defaults.invalid",
                safe_details={"field": f"permissions.{capability}", "reason": "invalid_choice"},
            )
        permissions[capability] = decision
    logging_mode = _string(value["visible_logging_mode"], "visible_logging_mode")
    if logging_mode not in _LOGGING_MODES:
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"field": "visible_logging_mode", "reason": "invalid_choice"},
        )
    startup = value["start_with_computer"]
    if type(startup) is not bool:
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"field": "start_with_computer", "reason": "expected_boolean"},
        )
    return ProfileDefaults(
        persona_text=_string(value["persona_text"], "persona_text"),
        profile_context_text=_string(value["profile_context_text"], "profile_context_text"),
        accent_color=_string(value["accent_color"], "accent_color"),
        foreground_color=_string(value["foreground_color"], "foreground_color"),
        background_color=_string(value["background_color"], "background_color"),
        waiting_messages=_string_tuple(value["waiting_messages"], "waiting_messages"),
        goodbye_messages=_string_tuple(value["goodbye_messages"], "goodbye_messages"),
        visible_logging_mode=logging_mode,
        start_with_computer=startup,
        permissions=MappingProxyType(permissions),
    )


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
    profile_defaults = _parse_profile_defaults(document[PROFILE_DEFAULTS_CATEGORY])
    raw_models = document[MODEL_DEFAULTS_CATEGORY]
    if not isinstance(raw_models, dict):
        raise ConfigurationError(code="defaults.invalid", message_key="error.defaults.invalid")
    _require_exact_keys(
        raw_models,
        frozenset({"reasoning", "context_window", "runtime_config", "scanner_limits"}),
        MODEL_DEFAULTS_CATEGORY,
    )
    limits = raw_models.get("scanner_limits")
    expected_limits = frozenset(
        {
            "max_directories",
            "max_path_bytes",
            "max_depth",
            "max_directory_entries",
            "max_candidates",
            "metadata_budget_bytes",
            "max_metadata_entries",
            "max_key_bytes",
            "max_display_string_bytes",
            "max_array_payload_bytes",
            "max_array_elements",
            "max_metadata_payload_bytes",
        }
    )
    if not isinstance(limits, dict):
        raise ConfigurationError(code="defaults.invalid", message_key="error.defaults.invalid")
    _require_exact_keys(limits, expected_limits, "model_defaults.scanner_limits")
    if any(type(v) is not int or v <= 0 for v in limits.values()):
        raise ConfigurationError(code="defaults.invalid", message_key="error.defaults.invalid")
    model_defaults = ModelDefaults(
        reasoning=_string(raw_models.get("reasoning"), "model_defaults.reasoning"),
        context_window=_context_window(
            raw_models.get("context_window"), "model_defaults.context_window"
        ),
        runtime_config=MappingProxyType({}),
        scanner_limits=MappingProxyType({str(k): int(v) for k, v in limits.items()}),
    )
    if model_defaults.reasoning not in {"off", "low", "medium", "high", "max"}:
        raise ConfigurationError(code="defaults.invalid", message_key="error.defaults.invalid")
    raw_runtime = raw_models.get("runtime_config")
    if not isinstance(raw_runtime, dict):
        raise ConfigurationError(code="defaults.invalid", message_key="error.defaults.invalid")
    from jarvis.models.errors import ModelError
    from jarvis.models.models import ModelRuntimeConfig

    try:
        runtime_config = ModelRuntimeConfig.from_mapping(
            {
                "reasoning": model_defaults.reasoning,
                "context_window": model_defaults.context_window,
                **raw_runtime,
            }
        ).to_mapping()
    except ModelError as error:
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details=error.safe_details,
        ) from error
    model_defaults = ModelDefaults(
        model_defaults.reasoning,
        model_defaults.context_window,
        MappingProxyType(runtime_config),
        model_defaults.scanner_limits,
    )
    # Reuse the profile domain's authoritative value validation without making defaults depend on
    # persistence or services. The local import avoids a module-import cycle.
    from jarvis.profiles.configuration import ProfileConfigurationValues
    from jarvis.profiles.errors import ProfileConfigurationError

    try:
        ProfileConfigurationValues.from_defaults(profile_defaults)
    except ProfileConfigurationError as error:
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details=error.safe_details,
            internal_message=error.internal_message,
        ) from error
    raw_runtime_manager = document[RUNTIME_MANAGER_CATEGORY]
    if not isinstance(raw_runtime_manager, dict):
        raise ConfigurationError(code="defaults.invalid", message_key="error.defaults.invalid")
    runtime_keys = frozenset(
        {
            "max_concurrent_runtimes",
            "max_pending_starts",
            "stream_capture_bytes",
            "event_retention_count",
            "endpoint_allocation_attempts",
        }
    )
    _require_exact_keys(raw_runtime_manager, runtime_keys, RUNTIME_MANAGER_CATEGORY)
    runtime_manager = RuntimeManagerDefaults(
        **{
            key: _positive_int(raw_runtime_manager[key], f"runtime_manager.{key}")
            for key in runtime_keys
        }
    )
    if runtime_manager.max_concurrent_runtimes > 16:
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"field": "runtime_manager.max_concurrent_runtimes"},
        )
    raw_chat = document[CHAT_CATEGORY]
    chat_keys = frozenset(ChatDefaults.__dataclass_fields__)
    if not isinstance(raw_chat, dict):
        raise ConfigurationError(code="defaults.invalid", message_key="error.defaults.invalid")
    _require_exact_keys(raw_chat, chat_keys, CHAT_CATEGORY)
    chat = ChatDefaults(**{key: _positive_int(raw_chat[key], f"chat.{key}") for key in chat_keys})
    if chat.max_queued_generations != 16:
        raise ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            safe_details={"field": "chat.max_queued_generations"},
        )
    if not (
        chat.minimum_diagnostic_reservation_bytes <= chat.max_diagnostic_bytes
        and chat.max_provider_delta_bytes <= chat.max_sse_frame_bytes
        and chat.max_sse_frame_bytes <= chat.max_sse_response_bytes
    ):
        raise ConfigurationError(code="defaults.invalid", message_key="error.defaults.invalid")
    return DefaultsSnapshot(
        schema_version,
        product_version,
        diagnostics,
        profile_defaults,
        model_defaults,
        runtime_manager,
        chat,
    )


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
    """Preserve profile values across defaults revisions; model state has no v2 rows."""

    # The transition registry is also the authority for persisted section
    # provenance.  Do not let Python's numeric equality admit floats or bools
    # as registry keys (for example, ``5.0 == 5``).
    if type(from_version) is not int or type(to_version) is not int:
        raise ConfigurationError(
            code="defaults.unsupported_version",
            message_key="error.defaults.unsupported_version",
            safe_details={"reason": "non_integer_version"},
        )
    if (from_version, to_version) in _SUPPORTED_PERSISTED_DEFAULTS_TRANSITIONS:
        return MappingProxyType(dict(values))
    raise ConfigurationError(
        code="defaults.unsupported_version",
        message_key="error.defaults.unsupported_version",
        safe_details={"from_version": from_version, "to_version": to_version},
    )


def is_supported_persisted_defaults_version(version: object) -> bool:
    """Return whether a section provenance can transition to packaged defaults.

    A stored version records which product defaults were last explicitly applied
    to that section.  It is deliberately independent of the currently packaged
    version, so ordinary reads and user edits do not rewrite historical
    provenance.  The transition registry remains the single authority for
    accepting historical values.
    """

    return (
        type(version) is int
        and (version, CURRENT_PRODUCT_DEFAULTS_VERSION) in _SUPPORTED_PERSISTED_DEFAULTS_TRANSITIONS
    )
