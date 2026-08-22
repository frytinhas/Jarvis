"""Installed-wheel fixed-dispatch acceptance with no checkout import dependency."""

from __future__ import annotations

import asyncio
import os
import struct
import subprocess
from pathlib import Path

import jarvis
from jarvis.core.runtime import JarvisCore
from jarvis.foundation.bootstrap import initialize_foundation
from jarvis.llm.fake import FakeLLMProvider
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.service import ProfileService
from jarvis.storage.xdg import resolve_xdg_paths


def _gguf(path: Path) -> None:
    key = b"general.name"
    name = b"Installed M006C"
    path.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + struct.pack("<Q", len(key))
        + key
        + struct.pack("<I", 8)
        + struct.pack("<Q", len(name))
        + name
    )


async def _run() -> None:
    installation = Path(os.environ["XDG_DATA_HOME"]) / "jarvis-cli/installation"
    assert Path(jarvis.__file__).resolve().is_relative_to(installation.resolve())
    initialize_foundation()
    paths = resolve_xdg_paths()
    database = paths.data / "jarvis.sqlite3"
    profile = ProfileService(database).ensure_jarvis().profile
    model_root = paths.data / "acceptance-models"
    model_root.mkdir(mode=0o700)
    _gguf(model_root / "model.gguf")
    models = ModelRegistryService(database)
    models.update_runtime_location((str(model_root),), "/usr/bin/gnutrue")
    model = models.refresh().records[0]
    models.select(profile.profile_id, model.model_id, 0)
    core = JarvisCore(provider=FakeLLMProvider(chat_deltas=("installed-wheel-ok",)))
    task = asyncio.create_task(core.run())
    for _ in range(400):
        if (paths.runtime / "core.sock").exists():
            break
        await asyncio.sleep(0.005)
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = await asyncio.to_thread(
        subprocess.run,
        [str(Path(os.environ["HOME"]) / ".local/bin/jarvis"), "hello"],
        cwd="/",
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    try:
        assert result.returncode == 0, result.stderr + result.stdout
        assert "installed-wheel-ok" in result.stdout
        print(f"module={jarvis.__file__}")
        print(result.stdout)
    finally:
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
