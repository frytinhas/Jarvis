from __future__ import annotations

import asyncio
import struct
from pathlib import Path

import pytest

from jarvis.cli.application import ClientOperationError, _result
from jarvis.core.runtime import JarvisCore
from jarvis.foundation.bootstrap import initialize_foundation
from jarvis.ipc.client import JarvisIpcClient
from jarvis.ipc.models import (
    MODEL_REGISTRY,
    PROFILE_MANAGEMENT,
    REQUEST_STREAM,
    RUNTIME_MANAGER,
    SETUP_V1,
)
from jarvis.llm.fake import FakeLLMProvider
from jarvis.profiles.models import CreateProfile
from jarvis.profiles.service import ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.xdg import resolve_xdg_paths

pytestmark = pytest.mark.integration


def _gguf(path: Path) -> None:
    key = b"general.name"
    name = b"Setup Test"
    path.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + struct.pack("<Q", len(key))
        + key
        + struct.pack("<I", 8)
        + struct.pack("<Q", len(name))
        + name
    )


def test_setup_v1_configures_validates_and_does_not_consume_learning(tmp_path: Path) -> None:
    initialize_foundation()
    paths = resolve_xdg_paths()
    database = paths.data / "jarvis.sqlite3"
    profiles = ProfileService(database)
    profile = profiles.ensure_jarvis().profile
    other = profiles.create_profile(CreateProfile("Other")).profile
    runtime = tmp_path / "llama-server"
    runtime.write_bytes(Path("/usr/bin/gnutrue").read_bytes())
    runtime.chmod(0o700)
    models = tmp_path / "models"
    models.mkdir()
    _gguf(models / "setup.gguf")
    provider = FakeLLMProvider()

    async def scenario() -> None:
        core = JarvisCore(provider=provider)
        task = asyncio.create_task(core.run())
        socket_path = paths.runtime / "core.sock"
        for _ in range(400):
            if socket_path.exists():
                break
            await asyncio.sleep(0.005)
        client = await JarvisIpcClient.connect(
            socket_path,
            required_capabilities=(
                REQUEST_STREAM,
                PROFILE_MANAGEMENT,
                MODEL_REGISTRY,
                RUNTIME_MANAGER,
                SETUP_V1,
            ),
        )
        try:
            state = await _result(client, "setup.start", profile_id=profile.profile_id)
            assert str(state["state"]) == "needs-runtime-path"
            initial_revision = state["revision"]
            assert type(initial_revision) is int
            with pytest.raises(ClientOperationError, match="setup.revision_conflict"):
                await _result(
                    client,
                    "setup.cancel",
                    profile_id=profile.profile_id,
                    payload={
                        "session_token": state["session_token"],
                        "expected_revision": initial_revision + 1,
                    },
                )
            with pytest.raises(ClientOperationError, match="setup.invalid_session"):
                await _result(
                    client,
                    "setup.cancel",
                    profile_id=other.profile_id,
                    payload={
                        "session_token": state["session_token"],
                        "expected_revision": state["revision"],
                    },
                )
            cancelled = await _result(client, "setup.start", profile_id=profile.profile_id)
            cancelled = await _result(
                client,
                "setup.cancel",
                profile_id=profile.profile_id,
                payload={
                    "session_token": cancelled["session_token"],
                    "expected_revision": cancelled["revision"],
                },
            )
            assert cancelled["state"] == "cancelled"
            with pytest.raises(ClientOperationError, match="setup.cancelled"):
                await _result(
                    client,
                    "setup.cancel",
                    profile_id=profile.profile_id,
                    payload={
                        "session_token": cancelled["session_token"],
                        "expected_revision": cancelled["revision"],
                    },
                )

            async def advance(action: str, value: object) -> None:
                nonlocal state
                state = await _result(
                    client,
                    "setup.advance",
                    profile_id=profile.profile_id,
                    payload={
                        "session_token": state["session_token"],
                        "expected_revision": state["revision"],
                        "action": action,
                        "value": value,
                    },
                )

            await advance("runtime-path", str(runtime))
            assert str(state["state"]) == "needs-model-directory"
            await advance("model-directory", str(models))
            assert str(state["state"]) == "needs-discovery"
            await advance("discover", None)
            assert str(state["state"]) == "needs-model-selection"
            model_id = state["models"][0]["model_id"]  # type: ignore[index]
            await advance("select-model", model_id)
            assert str(state["state"]) == "needs-essential-settings"
            await advance("essential-settings", {"reasoning": "low", "context_window": 4096})
            assert str(state["state"]) == "validating"
            state = await _result(
                client,
                "setup.validate",
                profile_id=profile.profile_id,
                payload={
                    "session_token": state["session_token"],
                    "expected_revision": state["revision"],
                },
            )
            assert state["state"] == "ready"
            with pytest.raises(ClientOperationError, match="setup.completed"):
                await _result(
                    client,
                    "setup.validate",
                    profile_id=profile.profile_id,
                    payload={
                        "session_token": state["session_token"],
                        "expected_revision": state["revision"],
                    },
                )
            assert provider.captured_requests == []
            with SQLiteDatabase(database) as opened:
                count = (
                    opened.connection().execute("SELECT COUNT(*) FROM learning_state").fetchone()
                )
            assert count == (0,)
        finally:
            await client.close()
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)

    asyncio.run(scenario())
