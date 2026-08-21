"""Disposable installed-wheel M006A walkthrough using the deterministic fake provider."""

from __future__ import annotations

import asyncio
import json
import os
import stat
import struct
import sys
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from jarvis.chat.agent import AgentStreamEvent
from jarvis.core.requests import CancellationController
from jarvis.core.runtime import JarvisCore
from jarvis.foundation.bootstrap import DATABASE_FILENAME, initialize_foundation
from jarvis.ipc.models import (
    CHAT_V1,
    CORE_HEALTH,
    EVENT_REPLAY,
    MODEL_REGISTRY,
    REQUEST_CANCEL,
    SESSION_RESUME,
)
from jarvis.llm.fake import FakeLLMProvider
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.destructive import ConfirmDestructiveOperation, ResetScope
from jarvis.profiles.models import CreateProfile
from jarvis.profiles.service import ProfileService
from jarvis.runtimes.lifecycle import ProfileRuntimeLifecycleCoordinator
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.xdg import resolve_xdg_paths
from tests.support.ipc_client import RawTestClient


def _gguf(path: Path, name: bytes) -> None:
    key = b"general.name"
    path.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + struct.pack("<Q", len(key))
        + key
        + struct.pack("<I", 8)
        + struct.pack("<Q", len(name))
        + name
    )


async def _wait_until(predicate: Any) -> None:
    for _ in range(2_000):
        value = predicate()
        if asyncio.iscoroutine(value):
            value = await value
        if value:
            return
        await asyncio.sleep(0.001)
    raise AssertionError("deterministic walkthrough condition was not reached")


async def _connect(socket_path: Path) -> RawTestClient:
    return await RawTestClient.connect(
        socket_path,
        optional_capabilities=(
            CHAT_V1,
            CORE_HEALTH,
            MODEL_REGISTRY,
            REQUEST_CANCEL,
            SESSION_RESUME,
            EVENT_REPLAY,
        ),
    )


async def _walk(root: Path) -> dict[str, object]:
    paths = resolve_xdg_paths()
    initialize_foundation()
    for path in (
        Path(os.environ["HOME"]),
        paths.config,
        paths.data,
        paths.state,
        paths.cache,
        paths.runtime,
    ):
        assert root in path.parents or path == root
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
    database_path = paths.data / DATABASE_FILENAME
    models = ModelRegistryService(database_path)
    model_root = root / "models"
    model_root.mkdir(mode=0o700)
    _gguf(model_root / "one.gguf", b"One")
    _gguf(model_root / "two.gguf", b"Two")
    models.update_runtime_location((str(model_root),), "/usr/bin/gnutrue")
    records = models.refresh().records
    one = next(item for item in records if item.metadata.get("general.name") == "One")
    two = next(item for item in records if item.metadata.get("general.name") == "Two")
    profiles = ProfileService(database_path)
    jarvis = profiles.ensure_jarvis().profile
    other = profiles.create_profile(CreateProfile("Other")).profile
    models.select(jarvis.profile_id, one.model_id, 0)
    models.select(other.profile_id, one.model_id, 0)

    provider = FakeLLMProvider(chat_deltas=("installed ", "wheel"))
    core = JarvisCore(provider=provider)
    core_task = asyncio.create_task(core.run())
    socket_path = paths.runtime / "core.sock"
    await _wait_until(socket_path.exists)
    client = await _connect(socket_path)
    basic = await client.request(
        request_id=str(uuid4()),
        operation="chat.submit",
        profile_id=str(jarvis.profile_id),
        payload={"content": "ordinary tool-like text"},
    )
    assert [item["event_type"] for item in basic][-3:] == [
        "text_delta",
        "text_delta",
        "response_completed",
    ]
    terminal = basic[-1]["payload"]
    assert terminal["state"] == "completed"
    learning = await client.request(
        request_id=str(uuid4()),
        operation="chat.learning.status",
        profile_id=str(jarvis.profile_id),
        payload={"model_id": str(one.model_id)},
    )
    assert learning[-1]["payload"]["status"] == "ACTIVE"
    diagnostics = await client.request(
        request_id=str(uuid4()),
        operation="chat.diagnostics.summary",
        profile_id=str(jarvis.profile_id),
        payload={"turn_id": terminal["turn_id"]},
    )
    assert diagnostics[-1]["payload"]["items"]

    assert core.resources is not None
    resources = core.resources

    async def emit(_event: AgentStreamEvent) -> None:
        return None

    provider.chat_gate.clear()
    provider.chat_entered.clear()
    first = asyncio.create_task(
        resources.agent.chat(
            profile_id=jarvis.profile_id,
            request_id=str(uuid4()),
            content="fifo-first",
            cancellation=CancellationController(),
            emit=emit,
        )
    )
    await provider.chat_entered.wait()
    second = asyncio.create_task(
        resources.agent.chat(
            profile_id=jarvis.profile_id,
            request_id=str(uuid4()),
            content="fifo-second",
            cancellation=CancellationController(),
            emit=emit,
        )
    )
    cross = asyncio.create_task(
        resources.agent.chat(
            profile_id=other.profile_id,
            request_id=str(uuid4()),
            content="cross-profile",
            cancellation=CancellationController(),
            emit=emit,
        )
    )
    await _wait_until(lambda: resources.generation_coordinator.queued_count(jarvis.profile_id))
    await _wait_until(lambda: len(provider.starts) == 2)
    provider.chat_gate.set()
    await asyncio.gather(first, second, cross)
    assert [item.messages[-1].content for item in provider.captured_requests[-3:]] == [
        "fifo-first",
        "cross-profile",
        "fifo-second",
    ]

    provider.chat_gate.clear()
    provider.chat_entered.clear()
    active_signal = CancellationController()
    active = asyncio.create_task(
        resources.agent.chat(
            profile_id=jarvis.profile_id,
            request_id=str(uuid4()),
            content="active-cancel",
            cancellation=active_signal,
            emit=emit,
        )
    )
    await provider.chat_entered.wait()
    queued_signal = CancellationController()
    queued = asyncio.create_task(
        resources.agent.chat(
            profile_id=jarvis.profile_id,
            request_id=str(uuid4()),
            content="queued-cancel",
            cancellation=queued_signal,
            emit=emit,
        )
    )
    await _wait_until(lambda: resources.generation_coordinator.queued_count(jarvis.profile_id))
    queued_signal.request()
    active_signal.request()
    for task in (queued, active):
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancelled generation unexpectedly completed")

    provider.chat_gate.clear()
    provider.chat_entered.clear()
    disconnected = await _connect(socket_path)
    assert disconnected.hello is not None
    proof = {
        "expected_core_instance_id": disconnected.hello["core_instance_id"],
        "connection_id": disconnected.hello["connection_id"],
        "resume_token": disconnected.hello["resume_token"],
    }
    disconnected_request = str(uuid4())
    await disconnected.send(
        {
            "type": "request",
            "protocol_version": 1,
            "request_id": disconnected_request,
            "operation": "chat.submit",
            "profile_id": str(jarvis.profile_id),
            "payload": {"content": "survive-disconnect"},
        }
    )
    assert (await disconnected.receive())["event_type"] == "request.accepted"
    await provider.chat_entered.wait()
    await disconnected.close()
    provider.chat_gate.set()
    await _wait_until(lambda: core.in_flight_count == 0)
    resumed = await RawTestClient.connect(
        socket_path,
        optional_capabilities=(CHAT_V1, SESSION_RESUME, EVENT_REPLAY),
        resume=proof,
    )
    await resumed.send(
        {
            "type": "replay",
            "protocol_version": 1,
            "request_id": disconnected_request,
            "after_sequence": 0,
        }
    )
    replay = await resumed.receive()
    replay_events = cast(list[dict[str, object]], replay["events"])
    assert replay_events[-1]["event_type"] == "response_completed"
    await resumed.close()

    models.ensure_runtime_association(jarvis.profile_id, two.model_id)
    switched = await resources.runtime_manager.switch(jarvis.profile_id, two.model_id, 1)
    assert switched.model_id == two.model_id

    lifecycle = ProfileRuntimeLifecycleCoordinator(
        resources.profiles, resources.profile_configuration, resources.runtime_manager
    )
    reset_preview, _ = await lifecycle.preview_reset(jarvis.profile_id, ResetScope.WHOLE_PROFILE)
    await lifecycle.confirm_reset(
        ConfirmDestructiveOperation(
            reset_preview.operation_id,
            reset_preview.target,
            jarvis.profile_id,
            reset_preview.confirmation_token,
        )
    )
    delete_preview, _ = await lifecycle.preview_delete(other.profile_id)
    await lifecycle.confirm_delete(
        ConfirmDestructiveOperation(
            delete_preview.operation_id,
            delete_preview.target,
            other.profile_id,
            delete_preview.confirmation_token,
        )
    )
    with SQLiteDatabase(database_path) as database:
        connection = database.connection()
        assert connection.execute("SELECT COUNT(*) FROM chat_turns").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM learning_state").fetchone()[0] == 0

    await client.close()
    await core.request_shutdown()
    await asyncio.wait_for(core_task, 5)
    restarted = JarvisCore(provider=FakeLLMProvider())
    restarted_task = asyncio.create_task(restarted.run())
    await _wait_until(socket_path.exists)
    restart_client = await _connect(socket_path)
    health = await restart_client.request(request_id=str(uuid4()), operation="core.health")
    assert health[-1]["payload"]["database_schema_version"] == 5
    await restart_client.close()
    await restarted.request_shutdown()
    await asyncio.wait_for(restarted_task, 5)
    return {
        "schema": 5,
        "streamed": "installed wheel",
        "fifo": True,
        "cross_profile": True,
        "queued_and_active_cancel": True,
        "disconnect_replay": True,
        "switch_reset_delete_restart": True,
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: manual_chat_walkthrough.py ROOT")
    root = Path(sys.argv[1]).resolve()
    print(json.dumps(asyncio.run(_walk(root)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
