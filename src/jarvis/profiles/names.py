"""Single authoritative implementation of profile display-name and alias rules."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final

from jarvis.profiles.errors import InvalidProfileNameError

MAX_DISPLAY_NAME_CODEPOINTS: Final = 128
MAX_DISPLAY_NAME_BYTES: Final = 512
MAX_ALIAS_LENGTH: Final = 63
RESERVED_ALIASES: Final = frozenset(
    {
        "jarvis",
        "jarvis-config",
        "jarvis-update",
        "jarvis-clear",
        "jarvis-manage",
        "jarvis-help",
        "jarvisd",
    }
)
_ALIAS_PATTERN: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class NormalizedProfileName:
    display_name: str
    command_alias: str


def _invalid(reason: str) -> InvalidProfileNameError:
    return InvalidProfileNameError(safe_details={"reason": reason})


def validate_display_name(value: str) -> str:
    """Return the canonical NFC display name or raise a typed validation error."""

    if not isinstance(value, str):
        raise _invalid("expected_string")
    normalized = unicodedata.normalize("NFC", value).strip(" ")
    if not normalized:
        raise _invalid("empty")
    if len(normalized) > MAX_DISPLAY_NAME_CODEPOINTS:
        raise _invalid("too_many_codepoints")
    if len(normalized.encode("utf-8")) > MAX_DISPLAY_NAME_BYTES:
        raise _invalid("too_many_bytes")

    has_alphanumeric = False
    combining_base_is_letter = False
    for character in normalized:
        category = unicodedata.category(character)
        if category.startswith("L"):
            has_alphanumeric = True
            combining_base_is_letter = True
        elif category == "Nd":
            has_alphanumeric = True
            combining_base_is_letter = False
        elif character == " ":
            combining_base_is_letter = False
        elif category.startswith("M") and combining_base_is_letter:
            continue
        else:
            raise _invalid("unsupported_character")
    if not has_alphanumeric:
        raise _invalid("missing_alphanumeric")
    return normalized


def normalize_command_alias(display_name: str) -> str:
    """Derive the one canonical safe ASCII alias from a validated display name."""

    canonical_name = validate_display_name(display_name)
    decomposed = unicodedata.normalize("NFKD", canonical_name.casefold())
    output: list[str] = []
    pending_separator = False
    for character in decomposed:
        if unicodedata.category(character).startswith("M"):
            continue
        if character == " ":
            pending_separator = bool(output)
            continue
        if "a" <= character <= "z" or "0" <= character <= "9":
            if pending_separator and output[-1] != "-":
                output.append("-")
            output.append(character)
            pending_separator = False
    alias = "".join(output).strip("-")
    if not alias:
        raise _invalid("empty_alias")
    if len(alias) > MAX_ALIAS_LENGTH:
        raise _invalid("alias_too_long")
    if _ALIAS_PATTERN.fullmatch(alias) is None:
        raise _invalid("invalid_alias")
    return alias


def normalize_profile_name(value: str) -> NormalizedProfileName:
    display_name = validate_display_name(value)
    return NormalizedProfileName(display_name, normalize_command_alias(display_name))


def is_reserved_alias(alias: str) -> bool:
    return alias in RESERVED_ALIASES
