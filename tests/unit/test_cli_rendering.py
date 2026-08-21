from __future__ import annotations

import io

import pytest

from jarvis.cli.presenter import TerminalPresenter, display_text

pytestmark = pytest.mark.unit


class _InteractiveInput(io.StringIO):
    def isatty(self) -> bool:
        return True


class _InteractiveOutput(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_terminal_controls_are_rendered_as_text_and_eof_is_interrupted() -> None:
    assert "\\x1b" in display_text("bad\x1b[2J")
    assert "\\u202e" in display_text("safe\u202e.txt")
    presenter = TerminalPresenter(stdin=_InteractiveInput(""), stdout=_InteractiveOutput())
    with pytest.raises(EOFError):
        presenter.prompt("Name")


def test_numbered_selection_reads_the_presenter_stream() -> None:
    output = _InteractiveOutput()
    presenter = TerminalPresenter(stdin=_InteractiveInput("invalid\n9\n2\n"), stdout=output)
    assert presenter.choose("Profiles", ["Jarvis", "Work"]) == 1
    assert "1. Jarvis" in output.getvalue()
    assert output.getvalue().count("Invalid selection") == 2
