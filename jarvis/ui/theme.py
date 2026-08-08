from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys
import tomllib
from typing import TextIO

from jarvis.config import config_path
from jarvis.settings import ColorMode


DEFAULT_COLORS: dict[str, str] = {
    "primary": "#ff8700",
    "accent": "#ffaf00",
    "user": "#ffd7af",
    "assistant": "#ff8700",
    "heading": "#ffaf00",
    "bold": "#ffd787",
    "code": "#d7af87",
    "tool": "#ff9f1c",
    "path": "#ffd787",
    "timer": "#a8a8a8",
    "success": "#5fd75f",
    "warning": "#ffaf00",
    "error": "#ff5f5f",
    "muted": "#8a8a8a",
}
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
_ASSIGNMENT = re.compile(r'^\s*([a-z_]+)\s*=\s*["\'](#[0-9a-fA-F]{6})["\']\s*(?:#.*)?$')


def colors_path() -> Path:
    return config_path().parent / "colors.toml"


def _salvage(payload: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in payload.splitlines():
        match = _ASSIGNMENT.fullmatch(line)
        if match and match.group(1) in DEFAULT_COLORS:
            values[match.group(1)] = match.group(2)
    return values


def _read_valid_colors(path: Path) -> tuple[dict[str, str], bool]:
    try:
        payload = path.read_text(encoding="utf-8")
    except OSError:
        return {}, False
    try:
        parsed = tomllib.loads(payload)
        source = parsed.get("colors", parsed)
        values = source if isinstance(source, dict) else {}
    except (tomllib.TOMLDecodeError, UnicodeError):
        return _salvage(payload), False
    valid = {
        key: value
        for key, value in values.items()
        if key in DEFAULT_COLORS and isinstance(value, str) and _HEX_COLOR.fullmatch(value)
    }
    complete = len(valid) == len(DEFAULT_COLORS)
    return valid, complete


def ensure_colors_file(path: Path | None = None) -> dict[str, str]:
    target = path or colors_path()
    valid, complete = _read_valid_colors(target) if target.is_file() else ({}, False)
    merged = {**DEFAULT_COLORS, **valid}
    if not complete:
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Jarvis terminal colors. Use hexadecimal values in #RRGGBB format.",
            "[colors]",
            *[f'{key} = "{merged[key]}"' for key in DEFAULT_COLORS],
            "",
        ]
        temporary = target.with_suffix(".tmp")
        temporary.write_text("\n".join(lines), encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(target)
    return merged


def _ansi_color(value: str) -> str:
    red, green, blue = (int(value[index:index + 2], 16) for index in (1, 3, 5))
    return f"\033[38;2;{red};{green};{blue}m"


@dataclass(frozen=True)
class Theme:
    colors: dict[str, str]
    enabled: bool

    @classmethod
    def load(
        cls,
        mode: ColorMode,
        *,
        stream: TextIO = sys.stdout,
        path: Path | None = None,
    ) -> "Theme":
        colors = ensure_colors_file(path)
        enabled = mode is ColorMode.ALWAYS or (
            mode is ColorMode.AUTO
            and stream.isatty()
            and "NO_COLOR" not in os.environ
        )
        return cls(colors, enabled)

    def paint(self, text: str, role: str, *, strong: bool = False) -> str:
        if not self.enabled or not text:
            return text
        weight = "\033[1m" if strong else ""
        return f"{weight}{_ansi_color(self.colors[role])}{text}\033[0m"


PLAIN_THEME = Theme(DEFAULT_COLORS, False)
