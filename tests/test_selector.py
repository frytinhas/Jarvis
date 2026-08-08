from __future__ import annotations

import io
import os
import pty
import termios
import threading
import time

from jarvis.ui import selector


def test_arrow_selector_moves_wraps_and_confirms(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    keys = iter(["up", "enter"])
    monkeypatch.setattr(selector, "_read_key", lambda _: next(keys))
    output = io.StringIO()

    selected = selector.select_option(
        "Escolha",
        ("Primeiro", "Segundo", "Terceiro"),
        input_stream=io.StringIO(),
        output_stream=output,
    )

    assert selected == 3
    assert "use as setas e Enter" in output.getvalue()


def test_arrow_reader_restores_terminal_state() -> None:
    master, slave = pty.openpty()
    source = os.fdopen(slave, "r", encoding="utf-8")
    try:
        before = termios.tcgetattr(source.fileno())
        result: list[str] = []
        reader = threading.Thread(target=lambda: result.append(selector._read_key(source)))
        reader.start()
        deadline = time.monotonic() + 1
        while termios.tcgetattr(source.fileno())[3] & termios.ICANON:
            assert time.monotonic() < deadline
            time.sleep(0.001)
        os.write(master, b"\x1b[B")
        reader.join(timeout=1)

        assert not reader.is_alive()
        assert result == ["down"]
        assert termios.tcgetattr(source.fileno()) == before
    finally:
        source.close()
        os.close(master)


def test_non_tty_does_not_enable_arrow_selection() -> None:
    assert not selector.supports_arrow_selection(io.StringIO(), io.StringIO())
