"""Terminal-safe rendering of client-neutral Core events."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from jarvis.profiles.models import VisibleLoggingMode

from .presenter import TerminalPresenter, display_stream_text, display_text

MAX_RENDERED_RESPONSE_BYTES = 256 * 1024


@dataclass(slots=True)
class RenderState:
    last_sequence: int = 0
    terminal_count: int = 0
    terminal_error: bool = False
    response_bytes: int = 0
    wrote_response: bool = False
    response_ended_with_newline: bool = False


class StreamRenderer:
    """Render an ordered Core stream without interpreting its authority."""

    def __init__(self, presenter: TerminalPresenter, mode: VisibleLoggingMode) -> None:
        self.presenter = presenter
        self.mode = mode
        self.state = RenderState()

    def render(self, event: Mapping[str, object]) -> None:
        sequence = event.get("sequence")
        if type(sequence) is int:
            if sequence <= self.state.last_sequence:
                return
            self.state.last_sequence = sequence
        event_type = str(event.get("event_type", event.get("type", "unknown")))
        terminal = event.get("terminal") is True
        if terminal:
            self.state.terminal_count += 1

        if event_type == "text_delta":
            payload = event.get("payload")
            text = payload.get("text") if isinstance(payload, dict) else None
            if isinstance(text, str):
                self._stream_delta(text)
            return
        if event_type == "response_started":
            self._render_response_started(event)
            return
        if event_type == "response_completed":
            self._finish_response()
            if self.mode is VisibleLoggingMode.FULL:
                self.presenter.write("[chat] response completed")
            return
        if event_type == "error" or event.get("type") == "error":
            if terminal:
                self.state.terminal_error = True
            self._finish_response()
            error = event.get("error")
            code = error.get("code") if isinstance(error, dict) else "ipc.unknown_error"
            if code == "chat.cancelled":
                self.presenter.write("Generation cancelled.")
            else:
                self.presenter.write(f"Error: {display_text(code)}")
            return
        if event_type == "runtime.state_changed":
            if self.mode in {VisibleLoggingMode.SERVER_ESSENTIAL, VisibleLoggingMode.FULL}:
                payload = event.get("payload")
                state = payload.get("state") if isinstance(payload, dict) else "unknown"
                self.presenter.write(f"Model runtime: {display_text(state)}")
            return
        if self.mode is VisibleLoggingMode.FULL:
            self.presenter.write(f"[core] {display_text(event_type)}")

    def _render_response_started(self, event: Mapping[str, object]) -> None:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        if self.mode is VisibleLoggingMode.ESSENTIAL_MINIMUM:
            self.presenter.write("Generating response")
        elif self.mode is VisibleLoggingMode.ESSENTIAL:
            self.presenter.write("chat.generate: Generating response")
        elif self.mode is VisibleLoggingMode.SERVER_ESSENTIAL:
            self.presenter.write(
                f"model.generate: Started ({display_text(payload.get('model_id', 'unknown'))})"
            )
        elif self.mode is VisibleLoggingMode.FULL:
            self.presenter.write(
                "[chat] response started "
                f"turn={display_text(payload.get('turn_id', 'unknown'))} "
                f"model={display_text(payload.get('model_id', 'unknown'))}"
            )

    def _stream_delta(self, text: str) -> None:
        remaining = MAX_RENDERED_RESPONSE_BYTES - self.state.response_bytes
        if remaining <= 0:
            return
        text = _truncate_utf8(text, remaining)
        rendered = display_stream_text(text)
        rendered = _truncate_utf8(rendered, remaining)
        if rendered:
            self.presenter.stream(rendered)
            self.state.wrote_response = True
            self.state.response_ended_with_newline = rendered.endswith("\n")
            self.state.response_bytes += len(rendered.encode("utf-8"))

    def _finish_response(self) -> None:
        if self.state.wrote_response and not self.state.response_ended_with_newline:
            self.presenter.write()
            self.state.response_ended_with_newline = True


def _truncate_utf8(value: str, maximum_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value
    encoded = encoded[:maximum_bytes]
    while encoded:
        try:
            return encoded.decode("utf-8")
        except UnicodeDecodeError as error:
            encoded = encoded[: error.start]
    return ""
