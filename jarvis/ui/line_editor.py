"""Reliable interactive input built on prompt_toolkit."""
from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Iterable
from typing import TextIO

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import has_selection
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import DummyHistory
from prompt_toolkit.input.base import Input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.output.base import Output
from prompt_toolkit.selection import SelectionType
from prompt_toolkit.validation import ValidationError, Validator


Validation = Callable[[str], str | None]
CompletionSource = Callable[[str], list[str]]


def supports_line_editing(
    input_stream: TextIO | None = None, output_stream: TextIO | None = None
) -> bool:
    source = input_stream or sys.stdin
    target = output_stream or sys.stdout
    return (
        source.isatty()
        and target.isatty()
        and os.environ.get("TERM", "").lower() not in {"", "dumb"}
    )


def normalize_paste(content: str) -> str:
    """Keep terminal pastes in one editable draft instead of submitting lines."""
    return re.sub(r"[\r\n]+", " ", content).strip()


class _CommandCompleter(Completer):
    def __init__(self, source: CompletionSource) -> None:
        self.source = source

    def get_completions(
        self, document: Document, complete_event: object
    ) -> Iterable[Completion]:
        before_cursor = document.text_before_cursor
        for candidate in self.source(document.text):
            yield Completion(candidate, start_position=-len(before_cursor))


class _InputValidator(Validator):
    def __init__(self, validator: Validation, blocked_message: str) -> None:
        self.validator = validator
        self.blocked_message = blocked_message

    def validate(self, document: Document) -> None:
        reason = self.validator(document.text)
        if reason:
            raise ValidationError(
                cursor_position=document.cursor_position,
                message=f"{self.blocked_message}: {reason}. Edit the draft and submit again.",
            )


def _key_bindings(completer: CompletionSource | None) -> KeyBindings:
    bindings = KeyBindings()

    def move_visual_line(event: object, direction: int) -> bool:
        buffer = event.current_buffer  # type: ignore[attr-defined]
        window = event.app.layout.current_window  # type: ignore[attr-defined]
        render_info = window.render_info
        if render_info is None:
            return False
        row = buffer.document.cursor_position_row
        column = buffer.document.cursor_position_col
        positions = render_info._rowcol_to_yx  # prompt_toolkit render map.
        current = positions.get((row, column))
        if current is None:
            return False
        current_y, current_x = current
        previous_position = getattr(buffer, "_jarvis_vertical_position", None)
        preferred_x = getattr(buffer, "_jarvis_vertical_column", current_x)
        if previous_position != buffer.cursor_position:
            preferred_x = current_x
        target_y = current_y + direction
        candidates = [
            (candidate_column, x)
            for (candidate_row, candidate_column), (y, x) in positions.items()
            if candidate_row == row and y == target_y
        ]
        if not candidates:
            return False
        target_column, _ = min(candidates, key=lambda item: abs(item[1] - preferred_x))
        buffer.cursor_position = buffer.document.translate_row_col_to_index(row, target_column)
        buffer._jarvis_vertical_position = buffer.cursor_position
        buffer._jarvis_vertical_column = preferred_x
        return True

    def select_visual_line(event: object, direction: int) -> None:
        buffer = event.current_buffer  # type: ignore[attr-defined]
        started = buffer.selection_state is None
        if started and buffer.text:
            buffer.start_selection(selection_type=SelectionType.CHARACTERS)
            buffer.selection_state.enter_shift_mode()
        moved = move_visual_line(event, direction)
        if started and not moved:
            buffer.exit_selection()

    @bindings.add(Keys.Up, eager=True)
    def _up(event: object) -> None:
        move_visual_line(event, -1)

    @bindings.add(Keys.Down, eager=True)
    def _down(event: object) -> None:
        move_visual_line(event, 1)

    @bindings.add(Keys.ShiftUp, eager=True)
    def _shift_up(event: object) -> None:
        select_visual_line(event, -1)

    @bindings.add(Keys.ShiftDown, eager=True)
    def _shift_down(event: object) -> None:
        select_visual_line(event, 1)

    @bindings.add(Keys.BracketedPaste, eager=True)
    def _paste(event: object) -> None:
        buffer = event.current_buffer  # type: ignore[attr-defined]
        if buffer.selection_state is not None:
            buffer.cut_selection()
        buffer.insert_text(normalize_paste(event.data))  # type: ignore[attr-defined]

    @bindings.add(Keys.Any, filter=has_selection)
    def _replace_selection(event: object) -> None:
        buffer = event.current_buffer  # type: ignore[attr-defined]
        buffer.cut_selection()
        buffer.insert_text(event.data)  # type: ignore[attr-defined]

    if completer is not None:
        @bindings.add(Keys.ControlI)
        def _complete(event: object) -> None:
            buffer = event.current_buffer  # type: ignore[attr-defined]
            candidates = completer(buffer.text)
            if len(candidates) == 1:
                buffer.document = Document(candidates[0], cursor_position=len(candidates[0]))
            elif candidates:
                buffer.start_completion(select_first=False)

    return bindings


def read_line(
    prompt: str,
    *,
    validator: Validation | None = None,
    completer: CompletionSource | None = None,
    blocked_message: str = "Input blocked",
    input_stream: Input | None = None,
    output_stream: Output | None = None,
) -> str:
    """Read one wrapped, editable input line without storing input history."""
    if input_stream is None and output_stream is None and not supports_line_editing():
        return input(prompt)
    session = PromptSession(
        message=ANSI(prompt),
        multiline=False,
        wrap_lines=True,
        history=DummyHistory(),
        validator=_InputValidator(validator, blocked_message) if validator else None,
        validate_while_typing=False,
        completer=_CommandCompleter(completer) if completer else None,
        complete_while_typing=False,
        key_bindings=_key_bindings(completer),
        input=input_stream,
        output=output_stream,
    )
    return session.prompt()
