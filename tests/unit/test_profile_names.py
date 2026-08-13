from __future__ import annotations

import unicodedata
from uuid import UUID

import pytest

from jarvis.profiles.errors import InvalidProfileNameError
from jarvis.profiles.models import ProfileId
from jarvis.profiles.names import (
    RESERVED_ALIASES,
    is_reserved_alias,
    normalize_command_alias,
    normalize_profile_name,
    validate_display_name,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("source", "display", "alias"),
    [
        ("João Trabalho", "João Trabalho", "joao-trabalho"),
        ("MY AI 2", "MY AI 2", "my-ai-2"),
        ("  Work  Profile  ", "Work  Profile", "work-profile"),
        ("Cafe\u0301", "Café", "cafe"),
        ("A1", "A1", "a1"),
    ],
)
def test_display_and_alias_normalization(source: str, display: str, alias: str) -> None:
    result = normalize_profile_name(source)
    assert result.display_name == display
    assert result.command_alias == alias
    assert unicodedata.is_normalized("NFC", result.display_name)


@pytest.mark.parametrize(
    "source",
    [
        "",
        "   ",
        "Work-Profile",
        "Work/Profile",
        "Work_Profile",
        "Work;Profile",
        "Work\tProfile",
        "Work\nProfile",
        "Work\u00a0Profile",
        "\u202eWork",
        "\x00Work",
        "\u0301Work",
        "1\u0301",
        "A \u0301",
        "A\ud800",
        "A" * 129,
    ],
)
def test_unsupported_or_oversized_display_names_are_rejected(source: str) -> None:
    with pytest.raises(InvalidProfileNameError):
        validate_display_name(source)


def test_non_ascii_name_with_no_ascii_alias_is_rejected() -> None:
    assert validate_display_name("中文") == "中文"
    with pytest.raises(InvalidProfileNameError) as caught:
        normalize_command_alias("中文")
    assert caught.value.safe_details["reason"] == "empty_alias"


def test_alias_length_bound_is_enforced_after_normalization() -> None:
    with pytest.raises(InvalidProfileNameError) as caught:
        normalize_command_alias("A" * 64)
    assert caught.value.safe_details["reason"] == "alias_too_long"


def test_extreme_unnormalized_input_is_rejected_before_unicode_normalization() -> None:
    with pytest.raises(InvalidProfileNameError) as caught:
        validate_display_name("A" + "\u0301" * 1_000_000)
    assert caught.value.safe_details["reason"] == "too_many_codepoints"


def test_reserved_alias_set_is_exact_and_canonical() -> None:
    assert {
        "jarvis",
        "jarvis-config",
        "jarvis-update",
        "jarvis-clear",
        "jarvis-manage",
        "jarvis-help",
        "jarvisd",
    } == RESERVED_ALIASES
    assert all(is_reserved_alias(alias) for alias in RESERVED_ALIASES)
    assert not is_reserved_alias("Jarvis")


def test_profile_ids_require_canonical_rfc4122_uuid4_values() -> None:
    assert str(ProfileId.parse("10000000-0000-4000-8000-000000000001")) == (
        "10000000-0000-4000-8000-000000000001"
    )
    with pytest.raises(ValueError):
        ProfileId.parse("10000000-0000-1000-8000-000000000001")
    with pytest.raises(ValueError):
        ProfileId(UUID("10000000-0000-4000-0000-000000000001"))
