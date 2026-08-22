"""Disposable installed-wheel M006B package-level CLI walkthrough."""

from __future__ import annotations

import asyncio
import json
import os
import select
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

from jarvis.core.runtime import JarvisCore
from jarvis.foundation.bootstrap import initialize_foundation
from jarvis.llm.fake import FakeLLMProvider
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.models import CreateProfile
from jarvis.profiles.service import ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.xdg import resolve_xdg_paths


def _gguf(path: Path) -> None:
    key = b"general.name"
    name = b"Installed CLI"
    path.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + struct.pack("<Q", len(key))
        + key
        + struct.pack("<I", 8)
        + struct.pack("<Q", len(name))
        + name
    )


class _CoreThread:
    def __init__(self, provider: FakeLLMProvider) -> None:
        self.core = JarvisCore(provider=provider)
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.core.run())

    def start(self) -> None:
        self.thread.start()
        socket_path = resolve_xdg_paths().runtime / "core.sock"
        for _ in range(1_000):
            if socket_path.exists():
                return
            time.sleep(0.005)
        raise AssertionError("Core did not start")

    def stop(self) -> None:
        future = asyncio.run_coroutine_threadsafe(self.core.request_shutdown(), self.loop)
        future.result(timeout=5)
        self.thread.join(timeout=5)
        assert not self.thread.is_alive()


def _interactive(alias: str | None) -> str:
    command = [sys.executable, "-m", "jarvis.cli"]
    if alias is not None:
        command.extend(("--profile-alias", alias))
    master, slave = os.openpty()
    try:
        process = subprocess.Popen(
            command,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True,
        )
    finally:
        os.close(slave)
    output = bytearray()
    try:
        deadline = time.monotonic() + 5
        sent_exit = False
        while time.monotonic() < deadline:
            readable, _, _ = select.select([master], [], [], 0.05)
            if readable:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                output.extend(chunk)
                if b": " in output and not sent_exit:
                    os.write(master, b"/exit\n")
                    sent_exit = True
            if process.poll() is not None:
                break
        assert process.wait(timeout=2) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        os.close(master)
    return output.decode("utf-8", errors="replace")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: manual_cli_walkthrough.py DISPOSABLE_ROOT")
    root = Path(sys.argv[1]).resolve(strict=True)
    paths = resolve_xdg_paths()
    assert all(root in path.parents or path == root for path in paths.all())
    initialize_foundation()
    database = paths.data / "jarvis.sqlite3"
    profiles = ProfileService(database)
    jarvis = profiles.ensure_jarvis().profile
    work = profiles.create_profile(CreateProfile("Work")).profile
    model_root = root / "models"
    model_root.mkdir(mode=0o700)
    _gguf(model_root / "installed.gguf")
    models = ModelRegistryService(database)
    models.update_runtime_location((str(model_root),), "/usr/bin/gnutrue")
    model = models.refresh().records[0]
    models.select(jarvis.profile_id, model.model_id, 0)
    models.select(work.profile_id, model.model_id, 0)

    provider = FakeLLMProvider(chat_deltas=("installed ", "response"))
    core = _CoreThread(provider)
    core.start()
    try:
        one_shots = []
        for arguments in (("olá",), ("--profile-alias", "work", "olá")):
            completed = subprocess.run(
                [sys.executable, "-m", "jarvis.cli", *arguments],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
            assert completed.returncode == 0, completed.stderr
            assert "installed response" in completed.stdout
            one_shots.append(completed.stdout)
        interactive = (_interactive(None), _interactive("work"))
        assert "Jarvis [jarvis]" in interactive[0]
        assert "Work [work]" in interactive[1]
    finally:
        core.stop()

    with SQLiteDatabase(database) as opened:
        sessions = (
            opened.connection()
            .execute("SELECT profile_id, COUNT(*) FROM chat_sessions GROUP BY profile_id")
            .fetchall()
        )
        learning = (
            opened.connection()
            .execute("SELECT profile_id, model_id, status FROM learning_state ORDER BY profile_id")
            .fetchall()
        )
        diagnostics = (
            opened.connection()
            .execute("SELECT COUNT(*) FROM chat_diagnostics WHERE closed = 1")
            .fetchone()[0]
        )
    assert len(sessions) == 2
    assert len(learning) == 2
    assert diagnostics > 0
    assert len(provider.captured_requests) == 2
    print(
        json.dumps(
            {
                "default_one_shot": "Jarvis [jarvis]" in one_shots[0],
                "alias_one_shot": "Work [work]" in one_shots[1],
                "interactive_profiles": 2,
                "isolated_sessions": len(sessions),
                "learning_rows": len(learning),
                "closed_diagnostics": diagnostics,
                "provider_requests": len(provider.captured_requests),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
