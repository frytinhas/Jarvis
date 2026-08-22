"""Dependency-free, terminal-safe rendering and input helpers."""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from collections.abc import Sequence
from typing import TextIO

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_STREAM_CONTROL = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]")


def display_text(value: object) -> str:
    """Render stored text without permitting terminal-control injection."""

    def escaped(match: re.Match[str]) -> str:
        return repr(match.group(0))[1:-1]

    text = _CONTROL.sub(escaped, str(value))
    # Unicode format characters include bidirectional controls.  They do not
    # emit ANSI bytes, but can visually reorder a terminal transcript and hide
    # user-controlled content from the person approving an action.
    return "".join(
        character if unicodedata.category(character) != "Cf" else f"\\u{ord(character):04x}"
        for character in text
    )


def display_stream_text(value: object) -> str:
    """Render streamed model text while preserving line feeds, never terminal controls."""

    def escaped(match: re.Match[str]) -> str:
        return repr(match.group(0))[1:-1]

    text = _STREAM_CONTROL.sub(escaped, str(value))
    return "".join(
        character if unicodedata.category(character) != "Cf" else f"\\u{ord(character):04x}"
        for character in text
    )


class TerminalPresenter:
    def __init__(self, *, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
        self.stdin = stdin
        self.stdout = stdout

    def write(self, value: str = "") -> None:
        print(value, file=self.stdout)

    def stream(self, value: str) -> None:
        self.stdout.write(value)
        self.stdout.flush()

    def prompt_inline(self, label: str) -> str:
        self.stream(f"{label}: ")
        return self._readline()

    def choose(self, heading: str, options: Sequence[str]) -> int:
        self.write(heading)
        for index, option in enumerate(options, 1):
            self.write(f"{index}. {display_text(option)}")
        self.write("0. Back")
        while True:
            self.write("Select: ")
            response = self._readline().strip()
            if response.isdigit() and 0 <= int(response) <= len(options):
                return int(response) - 1
            self.write("Invalid selection. Enter one of the listed numbers.")

    def prompt(self, label: str) -> str:
        self.write(f"{label}: ")
        return self._readline()

    def confirm(self, prompt: str) -> bool:
        self.write(f"{prompt} [y/N]: ")
        return self._readline().strip().lower() in {"y", "yes"}

    def _readline(self) -> str:
        line = self.stdin.readline()
        if line == "":
            raise EOFError
        return str(line).rstrip("\n")

    @property
    def interactive(self) -> bool:
        return bool(getattr(self.stdin, "isatty", lambda: False)()) and bool(
            getattr(self.stdout, "isatty", lambda: False)()
        )

    @property
    def color_enabled(self) -> bool:
        return self.interactive and not os.environ.get("NO_COLOR")
