from __future__ import annotations

import os
import select
import sys
import termios
import tty
from collections.abc import Sequence
from typing import TextIO


def supports_arrow_selection(
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> bool:
    source = input_stream or sys.stdin
    target = output_stream or sys.stdout
    return (
        source.isatty()
        and target.isatty()
        and os.environ.get("TERM", "").lower() not in {"", "dumb"}
    )


def _read_key(input_stream: TextIO) -> str:
    descriptor = input_stream.fileno()
    previous = termios.tcgetattr(descriptor)
    try:
        tty.setcbreak(descriptor)
        first = os.read(descriptor, 1)
        if first in {b"\r", b"\n"}:
            return "enter"
        if first == b"\x03":
            raise KeyboardInterrupt
        if first != b"\x1b":
            return first.decode(errors="ignore")
        if not select.select([descriptor], [], [], 0.05)[0]:
            return "escape"
        second = os.read(descriptor, 1)
        if second != b"[" or not select.select([descriptor], [], [], 0.05)[0]:
            return "escape"
        final = os.read(descriptor, 1)
        return {
            b"A": "up",
            b"B": "down",
            b"C": "right",
            b"D": "left",
        }.get(final, "unknown")
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)


def _render_options(
    options: Sequence[str],
    selected: int,
    output_stream: TextIO,
    *,
    redraw: bool,
) -> None:
    if redraw:
        output_stream.write(f"\x1b[{len(options)}A")
    for index, option in enumerate(options):
        marker = "›" if index == selected else " "
        style = "\x1b[7m" if index == selected else ""
        reset = "\x1b[0m" if index == selected else ""
        output_stream.write(f"\r\x1b[2K {marker} {style}{option}{reset}\n")
    output_stream.flush()


def select_option(
    prompt: str,
    options: Sequence[str],
    default: int = 1,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    if not options:
        raise ValueError("o seletor precisa de ao menos uma opção")
    if not 1 <= default <= len(options):
        raise ValueError("a opção padrão está fora da lista")
    source = input_stream or sys.stdin
    target = output_stream or sys.stdout
    selected = default - 1
    target.write(f"{prompt} (use as setas e Enter)\n")
    _render_options(options, selected, target, redraw=False)
    while True:
        key = _read_key(source)
        if key in {"up", "left"}:
            selected = (selected - 1) % len(options)
            _render_options(options, selected, target, redraw=True)
        elif key in {"down", "right"}:
            selected = (selected + 1) % len(options)
            _render_options(options, selected, target, redraw=True)
        elif key == "enter":
            return selected + 1
