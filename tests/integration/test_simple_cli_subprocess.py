from __future__ import annotations

import asyncio
import os
import select
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from jarvis.core.runtime import JarvisCore
from jarvis.foundation.bootstrap import initialize_foundation
from jarvis.llm.fake import FakeLLMProvider
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.models import CreateProfile
from jarvis.profiles.service import ProfileService
from jarvis.storage.xdg import resolve_xdg_paths

pytestmark = pytest.mark.integration


def _gguf(path: Path) -> None:
    key = b"general.name"
    name = b"Subprocess"
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
        for _ in range(500):
            if socket_path.exists():
                return
            time.sleep(0.005)
        raise AssertionError("Core did not start")

    def stop(self) -> None:
        future = asyncio.run_coroutine_threadsafe(self.core.request_shutdown(), self.loop)
        future.result(timeout=5)
        self.thread.join(timeout=5)
        assert not self.thread.is_alive()


def _seed(tmp_path: Path) -> None:
    initialize_foundation()
    database = resolve_xdg_paths().data / "jarvis.sqlite3"
    profiles = ProfileService(database)
    jarvis = profiles.ensure_jarvis().profile
    work = profiles.create_profile(CreateProfile("Work")).profile
    model_root = tmp_path / "models"
    model_root.mkdir()
    _gguf(model_root / "subprocess.gguf")
    models = ModelRegistryService(database)
    models.update_runtime_location((str(model_root),), "/usr/bin/gnutrue")
    model = models.refresh().records[0]
    models.select(jarvis.profile_id, model.model_id, 0)
    models.select(work.profile_id, model.model_id, 0)


def _environment() -> dict[str, str]:
    environment = dict(os.environ)
    repository = Path(__file__).parents[2]
    environment["PYTHONPATH"] = str(repository / "src")
    return environment


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
            env=_environment(),
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


def test_package_module_default_and_alias_interactive_and_one_shot(tmp_path: Path) -> None:
    _seed(tmp_path)
    provider = FakeLLMProvider(chat_deltas=("subprocess ", "response"))
    core = _CoreThread(provider)
    core.start()
    try:
        default = subprocess.run(
            [sys.executable, "-m", "jarvis.cli", "olá"],
            env=_environment(),
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        alias = subprocess.run(
            [
                sys.executable,
                "-m",
                "jarvis.cli",
                "--profile-alias",
                "work",
                "olá",
            ],
            env=_environment(),
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert default.returncode == alias.returncode == 0
        assert "subprocess response" in default.stdout
        assert "subprocess response" in alias.stdout
        assert "Jarvis [jarvis]" in default.stdout
        assert "Work [work]" in alias.stdout
        assert "Jarvis [jarvis]" in _interactive(None)
        assert "Work [work]" in _interactive("work")
        assert len(provider.captured_requests) == 2
    finally:
        core.stop()
