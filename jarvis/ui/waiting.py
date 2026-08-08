from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import random
from threading import Event, Thread
from typing import Callable, Iterator


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
        choose: Callable[[list[str]], str] | None = None,
        write: Callable[[str], None] | None = None,
    ) -> None:
        self.messages = messages
        self.interval = interval or (lambda: random.uniform(5.0, 10.0))
        self.choose = choose or random.choice
        self.write = write or (lambda message: print(f"\n◌ {message}", flush=True))

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

    def _run(self, stopped: Event) -> None:
        previous: str | None = None
        while not stopped.wait(max(0.0, self.interval())):
            choices = [message for message in self.messages if message != previous] or self.messages
            selected = self.choose(choices)
            self.write(selected)
            previous = selected
