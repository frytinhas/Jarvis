from __future__ import annotations

import io

import pytest

from jarvis.cli.commands import SlashCommandError, parse_slash_command
from jarvis.cli.presenter import TerminalPresenter, display_stream_text, display_text
from jarvis.cli.rendering import MAX_RENDERED_RESPONSE_BYTES, StreamRenderer
from jarvis.profiles.models import VisibleLoggingMode

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


def test_stream_text_preserves_newlines_but_escapes_terminal_controls() -> None:
    assert display_stream_text("line 1\nline 2\x1b[2J\rhidden‮") == (
        "line 1\nline 2\\x1b[2J\\rhidden\\u202e"
    )


@pytest.mark.parametrize(
    ("mode", "visible", "hidden"),
    [
        (VisibleLoggingMode.FULL, "[chat] response started", None),
        (VisibleLoggingMode.SERVER_ESSENTIAL, "model.generate: Started", "[chat]"),
        (VisibleLoggingMode.ESSENTIAL, "chat.generate: Generating", "model.generate"),
        (VisibleLoggingMode.ESSENTIAL_MINIMUM, "Generating response", "chat.generate"),
        (VisibleLoggingMode.NONE, "answer", "Generating response"),
    ],
)
def test_all_visible_logging_modes_render_text_and_expected_operational_detail(
    mode: VisibleLoggingMode, visible: str, hidden: str | None
) -> None:
    output = _InteractiveOutput()
    renderer = StreamRenderer(TerminalPresenter(stdout=output), mode)
    renderer.render(
        {
            "type": "event",
            "sequence": 1,
            "event_type": "response_started",
            "terminal": False,
            "payload": {"turn_id": "turn", "model_id": "model"},
        }
    )
    renderer.render(
        {
            "type": "event",
            "sequence": 2,
            "event_type": "text_delta",
            "terminal": False,
            "payload": {"text": "answer"},
        }
    )
    renderer.render(
        {
            "type": "event",
            "sequence": 3,
            "event_type": "response_completed",
            "terminal": True,
            "payload": {},
        }
    )
    assert visible in output.getvalue()
    assert "answer" in output.getvalue()
    if hidden is not None:
        assert hidden not in output.getvalue()
    assert renderer.state.terminal_count == 1


def test_none_still_renders_errors_and_duplicate_sequences_are_not_rendered() -> None:
    output = _InteractiveOutput()
    renderer = StreamRenderer(TerminalPresenter(stdout=output), VisibleLoggingMode.NONE)
    error = {
        "type": "event",
        "sequence": 1,
        "event_type": "error",
        "terminal": True,
        "error": {"code": "chat.failed\x1b[2J"},
    }
    renderer.render(error)
    renderer.render(error)
    assert output.getvalue().count("Error:") == 1
    assert "\\x1b" in output.getvalue()


def test_stream_renderer_enforces_its_core_contract_bound() -> None:
    output = _InteractiveOutput()
    renderer = StreamRenderer(TerminalPresenter(stdout=output), VisibleLoggingMode.NONE)
    renderer.render(
        {
            "type": "event",
            "sequence": 1,
            "event_type": "text_delta",
            "terminal": False,
            "payload": {"text": "x" * (MAX_RENDERED_RESPONSE_BYTES + 10)},
        }
    )
    assert len(output.getvalue().encode()) == MAX_RENDERED_RESPONSE_BYTES


def test_stream_renderer_bounds_sanitized_control_character_expansion() -> None:
    output = _InteractiveOutput()
    renderer = StreamRenderer(TerminalPresenter(stdout=output), VisibleLoggingMode.NONE)
    renderer.render(
        {
            "type": "event",
            "sequence": 1,
            "event_type": "text_delta",
            "terminal": False,
            "payload": {"text": "\x1b" * MAX_RENDERED_RESPONSE_BYTES},
        }
    )

    assert len(output.getvalue().encode()) == MAX_RENDERED_RESPONSE_BYTES
    assert "\x1b" not in output.getvalue()


@pytest.mark.parametrize(
    "command",
    [
        "/help",
        "/quit",
        "/exit",
        "/clear",
        "/model",
        "/reasoning",
        "/context",
        "/status",
        "/server",
        "/config",
        "/license",
        "/logs",
        "/learning",
        "/learning status",
        "/learning start",
        "/learning finish",
    ],
)
def test_authorized_slash_commands_are_intercepted(command: str) -> None:
    parsed = parse_slash_command(command)
    assert parsed is not None


@pytest.mark.parametrize(
    "command", ["/unknown", "/model use other", "/learning reset", "/help extra", "/"]
)
def test_unknown_or_out_of_scope_slash_commands_are_rejected(command: str) -> None:
    with pytest.raises(SlashCommandError):
        parse_slash_command(command)


def test_natural_language_is_not_a_slash_command() -> None:
    assert parse_slash_command("olá") is None
