from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import random
import sys
from threading import Event, Thread
from typing import Callable, Iterator, TextIO


def default_waiting_messages_path() -> Path:
    return Path(__file__).with_name("default_waiting_messages.txt")


def load_waiting_messages(path: Path) -> list[str]:
    try:
        return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, UnicodeError):
        return []


class WaitingIndicator:
    def __init__(
        self,
        messages: list[str],
        *,
        interval: Callable[[], float] | None = None,
        write: Callable[[str], None] | None = None,
        clear: Callable[[], None] | None = None,
        start_index: int | None = None,
        stream: TextIO | None = None,
    ) -> None:
        self.messages = messages
        self.interval = interval or (lambda: random.uniform(5.0, 10.0))
        self._index = (
            (start_index % len(messages))
            if messages and start_index is not None
            else random.randrange(len(messages)) if messages else 0
        )
        if write is None:
            output = stream if stream is not None else sys.stdout
            self.write = lambda message: self._write_line(output, message)
            self.clear = clear or (lambda: self._clear_line(output))
        else:
            self.write = write
            self.clear = clear or (lambda: None)

    @contextmanager
    def active(self) -> Iterator[None]:
        if not self.messages:
            yield
            return
        stopped = Event()
        worker = Thread(target=self._run, args=(stopped,), daemon=True)
        worker.start()
        try:
            yield
        finally:
            stopped.set()
            worker.join()
            self.clear()

    def _run(self, stopped: Event) -> None:
        while not stopped.wait(max(0.0, self.interval())):
            self.write(self._next_message())

    def _next_message(self) -> str:
        selected = self.messages[self._index]
        self._index = (self._index + 1) % len(self.messages)
        return selected

    @staticmethod
    def _write_line(stream: TextIO, message: str) -> None:
        if not stream.isatty():
            return
        stream.write(f"\r\033[2K◌ {message}")
        stream.flush()

    @staticmethod
    def _clear_line(stream: TextIO) -> None:
        if not stream.isatty():
            return
        stream.write("\r\033[2K")
        stream.flush()
