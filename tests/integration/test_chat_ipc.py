from __future__ import annotations

import asyncio
import struct
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from jarvis.chat.models import TurnId
from jarvis.core.runtime import JarvisCore
from jarvis.foundation.bootstrap import initialize_foundation
from jarvis.ipc.models import CHAT_V1, EVENT_REPLAY, MODEL_REGISTRY, SESSION_RESUME
from jarvis.llm.fake import FakeLLMProvider
from jarvis.models.models import ModelRecord
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.models import Profile
from jarvis.profiles.service import ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.xdg import resolve_xdg_paths
from tests.support.ipc_client import RawTestClient

pytestmark = pytest.mark.integration


def _fixture(path: Path) -> None:
    key = b"general.name"
    name = b"Tiny"
    path.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + struct.pack("<Q", len(key))
        + key
        + struct.pack("<I", 8)
        + struct.pack("<Q", len(name))
        + name
    )


def _seed(tmp_path: Path) -> tuple[Profile, ModelRecord]:
    initialize_foundation()
    paths = resolve_xdg_paths()
    database = paths.data / "jarvis.sqlite3"
    models = ModelRegistryService(database)
    root = tmp_path / "models"
    root.mkdir()
    _fixture(root / "model.gguf")
    models.update_runtime_location((str(root),), "/usr/bin/gnutrue")
    model = models.refresh().records[0]
    profile = ProfileService(database).ensure_jarvis().profile
    models.select(profile.profile_id, model.model_id, 0)
    return profile, model


async def _start(provider: FakeLLMProvider) -> tuple[JarvisCore, asyncio.Task[None], Path]:
    core = JarvisCore(provider=provider)
    task = asyncio.create_task(core.run())
    socket_path = resolve_xdg_paths().runtime / "core.sock"
    for _ in range(200):
        if socket_path.exists():
            return core, task, socket_path
        await asyncio.sleep(0.005)
    raise AssertionError("Core did not start")


def test_chat_v1_stream_terminal_status_learning_and_human_diagnostics(tmp_path: Path) -> None:
    profile, model = _seed(tmp_path)
    provider = FakeLLMProvider(chat_deltas=("one", " two"))

    async def run() -> None:
        core, task, path = await _start(provider)
        client = await RawTestClient.connect(
            path,
            optional_capabilities=(CHAT_V1, MODEL_REGISTRY, SESSION_RESUME, EVENT_REPLAY),
        )
        try:
            events = await client.request(
                request_id=str(uuid4()),
                operation="chat.submit",
                profile_id=str(profile.profile_id),
                payload={"content": 'tool-like JSON stays text: {"tool":"shell"}'},
            )
            assert [event["event_type"] for event in events] == [
                "request.accepted",
                "request.started",
                "response_started",
                "text_delta",
                "text_delta",
                "response_completed",
            ]
            assert sum(bool(event["terminal"]) for event in events) == 1
            terminal = events[-1]
            turn_id = terminal["payload"]["turn_id"]
            status = await client.request(
                request_id=str(uuid4()),
                operation="chat.turn.status",
                profile_id=str(profile.profile_id),
                payload={"turn_id": turn_id},
            )
            assert status[-1]["payload"]["state"] == "completed"
            assert status[-1]["payload"]["authoritative"] is True
            learning = await client.request(
                request_id=str(uuid4()),
                operation="chat.learning.status",
                profile_id=str(profile.profile_id),
                payload={"model_id": str(model.model_id)},
            )
            assert learning[-1]["payload"]["status"] == "ACTIVE"
            assert core.resources is not None
            turn = await asyncio.to_thread(
                core.resources.conversations.get_turn,
                TurnId.parse(str(turn_id)),
                profile.profile_id,
            )
            diagnostic_sentinel = "DIAGNOSTIC_SENTINEL_NEVER_MODEL_INPUT"
            await asyncio.to_thread(
                core.resources.chat_diagnostics.emit,
                turn,
                "sentinel",
                diagnostic_sentinel,
                closed=True,
            )
            diagnostics = await client.request(
                request_id=str(uuid4()),
                operation="chat.diagnostics.summary",
                profile_id=str(profile.profile_id),
                payload={"turn_id": turn_id},
            )
            assert diagnostics[-1]["payload"]["items"]
            assert diagnostic_sentinel in {
                item["summary"] for item in diagnostics[-1]["payload"]["items"]
            }
            await client.request(
                request_id=str(uuid4()),
                operation="chat.submit",
                profile_id=str(profile.profile_id),
                payload={"content": "next request must not receive diagnostics"},
            )
            captured = provider.captured_requests[-1]
            assert all(
                "diagnostic" not in message.provenance.casefold() for message in captured.messages
            )
            assert diagnostic_sentinel not in "\n".join(
                message.content for message in captured.messages
            )
            assert all(
                "tool broker" not in message.content.casefold() for message in captured.messages
            )
        finally:
            await client.close()
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_disconnect_does_not_cancel_chat_and_resume_replays_terminal(tmp_path: Path) -> None:
    profile, _model = _seed(tmp_path)
    provider = FakeLLMProvider(chat_deltas=("survived",))
    provider.chat_gate.clear()

    async def run() -> None:
        core, task, path = await _start(provider)
        caps = (CHAT_V1, MODEL_REGISTRY, SESSION_RESUME, EVENT_REPLAY)
        first = await RawTestClient.connect(path, optional_capabilities=caps)
        assert first.hello is not None
        proof = {
            "expected_core_instance_id": first.hello["core_instance_id"],
            "connection_id": first.hello["connection_id"],
            "resume_token": first.hello["resume_token"],
        }
        request_id = str(uuid4())
        await first.send(
            {
                "type": "request",
                "protocol_version": 1,
                "request_id": request_id,
                "operation": "chat.submit",
                "profile_id": str(profile.profile_id),
                "payload": {"content": "continue after disconnect"},
            }
        )
        assert (await first.receive())["event_type"] == "request.accepted"
        await provider.chat_entered.wait()
        await first.close()
        provider.chat_gate.set()
        for _ in range(200):
            if core.in_flight_count == 0:
                break
            await asyncio.sleep(0.005)
        resumed = await RawTestClient.connect(path, optional_capabilities=caps, resume=proof)
        await resumed.send(
            {
                "type": "replay",
                "protocol_version": 1,
                "request_id": request_id,
                "after_sequence": 0,
            }
        )
        replay = await resumed.receive()
        events = cast(list[dict[str, object]], replay["events"])
        assert events[-1]["event_type"] == "response_completed"
        assert sum(bool(event["terminal"]) for event in events) == 1
        await resumed.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_core_shutdown_cancels_active_chat_and_records_one_terminal_state(tmp_path: Path) -> None:
    profile, _model = _seed(tmp_path)
    provider = FakeLLMProvider(chat_deltas=("never emitted",))
    provider.chat_gate.clear()
    database_path = resolve_xdg_paths().data / "jarvis.sqlite3"

    async def run() -> None:
        core, task, path = await _start(provider)
        client = await RawTestClient.connect(
            path,
            optional_capabilities=(CHAT_V1, MODEL_REGISTRY, SESSION_RESUME, EVENT_REPLAY),
        )
        request_id = str(uuid4())
        await client.send(
            {
                "type": "request",
                "protocol_version": 1,
                "request_id": request_id,
                "operation": "chat.submit",
                "profile_id": str(profile.profile_id),
                "payload": {"content": "shutdown cancellation"},
            }
        )
        assert (await client.receive())["event_type"] == "request.accepted"
        await provider.chat_entered.wait()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)
        await client.close()

    asyncio.run(run())
    with SQLiteDatabase(database_path) as database:
        assert database.connection().execute(
            "SELECT state, failure_code FROM chat_turns"
        ).fetchone() == ("cancelled", "chat.cancelled")
