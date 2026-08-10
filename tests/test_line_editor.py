from __future__ import annotations

import threading
import time

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from jarvis.ui.line_editor import normalize_paste, read_line


def _read(payload: str, *, validator=None, completer=None) -> str:  # type: ignore[no-untyped-def]
    with create_pipe_input() as input_stream:
        input_stream.send_text(payload)
        return read_line(
            "Você > ",
            validator=validator,
            completer=completer,
            input_stream=input_stream,
            output_stream=DummyOutput(),
        )


def _read_steps(*steps: str) -> str:
    with create_pipe_input() as input_stream:
        result: list[str] = []
        reader = threading.Thread(
            target=lambda: result.append(
                read_line(
                    "Você > ", input_stream=input_stream, output_stream=DummyOutput()
                )
            )
        )
        reader.start()
        for step in steps:
            input_stream.send_text(step)
            time.sleep(0.05)
        reader.join(timeout=1)
        assert not reader.is_alive()
        return result[0]


def test_line_editor_accepts_long_wrapped_text_without_repeating_it() -> None:
    message = "boa noite" + "x" * 400

    assert _read(message + "\r") == message


def test_line_editor_selection_replaces_selected_text() -> None:
    selected = _read("abcd\x1b[1;2D\x1b[1;2DX\r")

    assert selected == "abX"


def test_line_editor_moves_up_across_a_wrapped_visual_line() -> None:
    message = "x" * 200
    moved = _read_steps(message, "\x1b[A", "Z\r")

    assert moved != message + "Z"
    assert len(moved) == len(message) + 1


def test_line_editor_moves_down_across_a_wrapped_visual_line() -> None:
    message = "x" * 200
    moved = _read_steps(message, "\x1b[H", "\x1b[B", "Z\r")

    assert moved != "Z" + message
    assert len(moved) == len(message) + 1


def test_line_editor_selects_up_across_a_wrapped_visual_line() -> None:
    message = "x" * 200
    selected = _read_steps(message, "\x1b[1;2A", "Z\r")

    assert len(selected) < len(message)
    assert selected.endswith("Z")


def test_line_editor_keeps_bracketed_paste_as_one_draft() -> None:
    value = _read("\x1b[200~one\ntwo\x1b[201~\r")

    assert value == "one two"
    assert normalize_paste("one\r\ntwo") == "one two"


def test_line_editor_keeps_invalid_draft_for_correction() -> None:
    value = _read(
        "bad\r\x15good\r", validator=lambda text: "marker" if text == "bad" else None
    )

    assert value == "good"


def test_line_editor_completes_a_unique_command() -> None:
    value = _read("/hel\t\r", completer=lambda text: ["/help"] if text == "/hel" else [])

    assert value == "/help"
