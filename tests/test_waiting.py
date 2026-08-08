from __future__ import annotations

from pathlib import Path
import time

from jarvis.ui.waiting import WaitingIndicator, load_waiting_messages


def test_blank_waiting_file_disables_messages(tmp_path: Path) -> None:
    path = tmp_path / "WaitingMessages.txt"
    path.write_text("\n\n", encoding="utf-8")
    assert load_waiting_messages(path) == []


def test_waiting_indicator_rotates_without_immediate_repeat() -> None:
    shown: list[str] = []
    indicator = WaitingIndicator(
        ["one", "two"],
        interval=lambda: 0.002,
        choose=lambda choices: choices[0],
        write=shown.append,
    )

    with indicator.active():
        time.sleep(0.012)
    count_after_stop = len(shown)
    time.sleep(0.005)

    assert len(shown) >= 2
    assert all(left != right for left, right in zip(shown, shown[1:]))
    assert len(shown) == count_after_stop


def test_missing_waiting_file_is_silent(tmp_path: Path) -> None:
    assert load_waiting_messages(tmp_path / "missing.txt") == []
