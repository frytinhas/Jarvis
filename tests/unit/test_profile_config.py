from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from jarvis.config.defaults import DefaultsRegistry
from jarvis.profiles.configuration import (
    AppearanceConfiguration,
    ProfileConfigurationValues,
)
from jarvis.profiles.errors import ProfileConfigurationError
from jarvis.profiles.models import Capability, PermissionDecision, VisibleLoggingMode

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
        {"profile_context_text": "\x00"},
        {"waiting_messages": ("line\nbreak",)},
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
