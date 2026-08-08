from __future__ import annotations

from io import StringIO
from pathlib import Path
import time

from jarvis.ui.waiting import WaitingIndicator, load_waiting_messages


def test_blank_waiting_file_disables_messages(tmp_path: Path) -> None:
    path = tmp_path / "WaitingMessages.txt"
    path.write_text("\n\n", encoding="utf-8")
    assert load_waiting_messages(path) == []


def test_waiting_indicator_rotates_sequentially_and_wraps() -> None:
    indicator = WaitingIndicator(["one", "two", "three"], start_index=1)

    assert [indicator._next_message() for _ in range(5)] == [
        "two",
        "three",
        "one",
        "two",
        "three",
    ]


def test_waiting_indicator_randomizes_start_once(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[int] = []

    def choose_start(size: int) -> int:
        calls.append(size)
        return 2

    monkeypatch.setattr("jarvis.ui.waiting.random.randrange", choose_start)
    indicator = WaitingIndicator(["one", "two", "three"])

    assert indicator._next_message() == "three"
    assert indicator._next_message() == "one"
    assert calls == [3]


def test_waiting_indicator_keeps_cursor_between_activations() -> None:
    shown: list[str] = []
    indicator = WaitingIndicator(
        ["one", "two", "three"],
        interval=lambda: 0.002,
        write=shown.append,
        start_index=1,
    )

    with indicator.active():
        time.sleep(0.005)
    with indicator.active():
        time.sleep(0.003)
    count_after_stop = len(shown)
    time.sleep(0.005)

    assert shown[:3] == ["two", "three", "one"]
    assert len(shown) == count_after_stop


def test_missing_waiting_file_is_silent(tmp_path: Path) -> None:
    assert load_waiting_messages(tmp_path / "missing.txt") == []


class TTYBuffer(StringIO):
    def isatty(self) -> bool:
        return True


def test_terminal_waiting_message_rewrites_and_clears_one_line() -> None:
    stream = TTYBuffer()
    indicator = WaitingIndicator(["working"], start_index=0, stream=stream)

    indicator.write(indicator._next_message())
    indicator.clear()

    output = stream.getvalue()
    assert "\n" not in output
    assert output == "\r\033[2K◌ working\r\033[2K"


def test_non_terminal_output_does_not_receive_waiting_messages() -> None:
    stream = StringIO()
    indicator = WaitingIndicator(["working"], start_index=0, stream=stream)

    indicator.write(indicator._next_message())
    indicator.clear()

    assert stream.getvalue() == ""
