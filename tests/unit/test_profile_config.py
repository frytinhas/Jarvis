from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from jarvis.config.defaults import DefaultsRegistry
from jarvis.profiles.configuration import (
    AppearanceConfiguration,
    ProfileConfigurationValues,
    SectionRevision,
)
from jarvis.profiles.errors import ProfileConfigurationError
from jarvis.profiles.models import (
    Capability,
    ConfigurationSection,
    PermissionDecision,
    VisibleLoggingMode,
)

pytestmark = pytest.mark.unit


def _defaults() -> ProfileConfigurationValues:
    return ProfileConfigurationValues.from_defaults(
        DefaultsRegistry.load_packaged().current().profile_defaults
    )


def test_packaged_profile_values_are_exact_and_immutable() -> None:
    values = _defaults()
    assert values.visible_logging_mode is VisibleLoggingMode.ESSENTIAL_MINIMUM
    assert values.start_with_computer is False
    assert values.appearance == AppearanceConfiguration("#4fc3f7", "#e6edf3", "#0d1117")
    assert values.waiting_messages == ()
    assert values.goodbye_messages == ()
    assert values.permissions[Capability.CREATE] is PermissionDecision.ALLOW
    assert values.permissions[Capability.DELETE] is PermissionDecision.ASK
    with pytest.raises(FrozenInstanceError):
        values.persona_text = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        values.permissions[Capability.DELETE] = PermissionDecision.DENY  # type: ignore[index]


@pytest.mark.parametrize(
    "mutation",
    [
        {"persona_text": "x" * (32 * 1024 + 1)},
        {"persona_text": "\ud800"},
        {"profile_context_text": "\x00"},
        {"waiting_messages": ("line\nbreak",)},
        {"waiting_messages": ("\ud800",)},
        {"goodbye_messages": tuple("x" for _ in range(17))},
        {"visible_logging_mode": "verbose"},
        {"start_with_computer": 1},
        {"permissions": {Capability.CREATE: PermissionDecision.ALLOW}},
    ],
)
def test_invalid_configuration_values_fail_closed(mutation: dict[str, object]) -> None:
    with pytest.raises(ProfileConfigurationError):
        replace(_defaults(), **mutation)  # type: ignore[arg-type]


@pytest.mark.parametrize("color", ["#ABCDEF", "blue", "#12345", "123456", "#gggggg"])
def test_colors_require_lowercase_hex(color: str) -> None:
    with pytest.raises(ProfileConfigurationError):
        AppearanceConfiguration(color, "#e6edf3", "#0d1117")


def test_messages_are_nfc_normalized_and_ordered() -> None:
    values = replace(_defaults(), waiting_messages=("Cafe\u0301", "Second"))
    assert values.waiting_messages == ("Café", "Second")


def test_extreme_persona_is_rejected_before_utf8_materialization() -> None:
    with pytest.raises(ProfileConfigurationError) as caught:
        replace(_defaults(), persona_text="é" * 1_000_000)
    assert caught.value.safe_details == {"field": "persona_text", "reason": "too_many_bytes"}


@pytest.mark.parametrize("version", [1, 6])
def test_profile_sections_reject_nonexistent_or_future_defaults_versions(version: int) -> None:
    with pytest.raises(ValueError, match="unsupported section defaults version"):
        SectionRevision(ConfigurationSection.PERSONA, version, 1)
