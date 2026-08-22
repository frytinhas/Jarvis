"""Controlled real llama-server/GGUF acceptance for M006C; uses disposable XDG state."""

from __future__ import annotations

import asyncio
import io
import sys
from dataclasses import replace
from pathlib import Path

from jarvis.cli.chat_application import ChatArguments, run_chat
from jarvis.cli.presenter import TerminalPresenter
from jarvis.core.runtime import JarvisCore
from jarvis.foundation.bootstrap import initialize_foundation
from jarvis.models.models import ModelRuntimeConfig
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.service import ProfileService
from jarvis.storage.xdg import resolve_xdg_paths


async def _run(runtime: Path, model_path: Path) -> None:
    initialize_foundation()
    database = resolve_xdg_paths().data / "jarvis.sqlite3"
    profile = ProfileService(database).ensure_jarvis().profile
    models = ModelRegistryService(database)
    models.update_runtime_location((str(model_path.parent),), str(runtime))
    record = next(
        item for item in models.refresh().records if item.canonical_path == model_path.resolve()
    )
    models.select(profile.profile_id, record.model_id, 0)
    configured = replace(
        ModelRuntimeConfig(),
        reasoning="off",
        context_window=1024,
        gpu_layers=0,
        threads=4,
        batch_size=128,
        startup_timeout_seconds=300,
        generation_timeout_seconds=300,
    )
    models.update_config(profile.profile_id, record.model_id, configured, 1)
    core = JarvisCore()
    task = asyncio.create_task(core.run())
    socket_path = resolve_xdg_paths().runtime / "core.sock"
    for _ in range(1_000):
        if socket_path.exists():
            break
        await asyncio.sleep(0.01)
    output = io.StringIO()
    try:
        status = await run_chat(
            ChatArguments("jarvis", "Reply with exactly: OK"),
            TerminalPresenter(stdin=io.StringIO(), stdout=output),
        )
        if status != 0:
            raise AssertionError(output.getvalue())
        assert core.resources is not None
        runtime_status = await core.resources.runtime_manager.status(profile.profile_id)
        print(f"state={runtime_status.state.value} health={runtime_status.health.value}")
        print(output.getvalue())
    finally:
        await core.request_shutdown()
        await asyncio.wait_for(task, 30)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: manual_real_gguf_m006c.py LLAMA_SERVER MODEL_GGUF")
    asyncio.run(_run(Path(sys.argv[1]), Path(sys.argv[2])))


if __name__ == "__main__":
    main()
