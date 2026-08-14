from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.core.requests import RequestContext
from jarvis.core.runtime import JarvisCore
from jarvis.ipc.codec import encode_frame
from jarvis.ipc.models import CORE_CONTROL, EVENT_REPLAY, SESSION_RESUME, ConnectionId
from jarvis.ipc.server import IpcServer, LogicalSession
from jarvis.storage.xdg import resolve_xdg_paths
from tests.support.ipc_client import RawTestClient

pytestmark = pytest.mark.integration


async def _start(handler: object) -> tuple[JarvisCore, asyncio.Task[None], Path]:
    core = JarvisCore(handlers={"test.block": handler})  # type: ignore[dict-item]
    task = asyncio.create_task(core.run())
    path = resolve_xdg_paths().runtime / "core.sock"
    for _ in range(200):
        if path.exists():
            return core, task, path
        await asyncio.sleep(0.005)
    raise AssertionError("Core did not start")


def test_disconnect_resume_status_replay_and_token_rotation() -> None:
    release = asyncio.Event()

    async def handler(_context: RequestContext) -> dict[str, object]:
        await release.wait()
        return {"done": True}

    async def run() -> None:
        core, task, path = await _start(handler)
        caps = (SESSION_RESUME, EVENT_REPLAY, CORE_CONTROL)
        first = await RawTestClient.connect(path, optional_capabilities=caps)
        assert first.hello is not None
        first_hello = first.hello
        request_id = str(uuid4())
        await first.send(
            {
                "type": "request",
                "protocol_version": 1,
                "request_id": request_id,
                "operation": "test.block",
                "payload": {},
            }
        )
        assert (await first.receive())["sequence"] == 1
        assert (await first.receive())["sequence"] == 2
        await first.close()
        release.set()
        for _ in range(100):
            if core.in_flight_count == 0:
                break
            await asyncio.sleep(0.005)
        proof = {
            "expected_core_instance_id": first_hello["core_instance_id"],
            "connection_id": first_hello["connection_id"],
            "resume_token": first_hello["resume_token"],
        }
        resumed = await RawTestClient.connect(path, optional_capabilities=caps, resume=proof)
        assert resumed.hello is not None
        assert resumed.hello["connection_id"] == first_hello["connection_id"]
        assert resumed.hello["resume_token"] != first_hello["resume_token"]
        await resumed.send(
            {
                "type": "request.status",
                "protocol_version": 1,
                "request_id": request_id,
            }
        )
        status = await resumed.receive()
        assert status["request"]["state"] == "COMPLETED"  # type: ignore[index]
        await resumed.send(
            {
                "type": "replay",
                "protocol_version": 1,
                "request_id": request_id,
                "after_sequence": 0,
            }
        )
        replay = await resumed.receive()
        replay_events = replay["events"]
        assert isinstance(replay_events, list)
        assert all(isinstance(event, dict) for event in replay_events)
        assert [event["sequence"] for event in replay_events] == [1, 2, 3]
        assert replay_events[-1]["terminal"] is True

        forged = await RawTestClient.connect(path, optional_capabilities=caps, resume=proof)
        assert forged.hello is not None
        assert forged.hello["type"] == "hello.error"
        assert forged.hello["error"]["code"] == "ipc.resume_unavailable"  # type: ignore[index]
        await forged.close()
        await resumed.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_wrong_session_cannot_status_or_replay() -> None:
    async def handler(_context: RequestContext) -> dict[str, object]:
        return {"done": True}

    async def run() -> None:
        core, task, path = await _start(handler)
        caps = (SESSION_RESUME, EVENT_REPLAY, CORE_CONTROL)
        owner = await RawTestClient.connect(path, optional_capabilities=caps)
        stranger = await RawTestClient.connect(path, optional_capabilities=caps)
        request_id = str(uuid4())
        events = await owner.request(request_id=request_id, operation="test.block")
        assert events[-1]["terminal"] is True
        for kind in ("request.status", "replay"):
            message: dict[str, object] = {
                "type": kind,
                "protocol_version": 1,
                "request_id": request_id,
            }
            if kind == "replay":
                message["after_sequence"] = 0
            await stranger.send(message)
            error = await stranger.receive()
            assert error["error"]["code"] == "ipc.request_not_owned"  # type: ignore[index]
        await owner.close()
        await stranger.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_resume_never_survives_core_restart() -> None:
    async def handler(_context: RequestContext) -> dict[str, object]:
        return {"done": True}

    async def run() -> None:
        caps = (SESSION_RESUME, EVENT_REPLAY, CORE_CONTROL)
        first_core, first_task, path = await _start(handler)
        first = await RawTestClient.connect(path, optional_capabilities=caps)
        assert first.hello is not None
        proof = {
            "expected_core_instance_id": first.hello["core_instance_id"],
            "connection_id": first.hello["connection_id"],
            "resume_token": first.hello["resume_token"],
        }
        await first.close()
        await first_core.request_shutdown()
        await asyncio.wait_for(first_task, 5)

        second_core, second_task, second_path = await _start(handler)
        attempted = await RawTestClient.connect(
            second_path, optional_capabilities=caps, resume=proof
        )
        assert attempted.hello is not None
        assert attempted.hello["type"] == "hello.error"
        assert attempted.hello["error"]["code"] == "ipc.resume_unavailable"  # type: ignore[index]
        await attempted.close()
        await second_core.request_shutdown()
        await asyncio.wait_for(second_task, 5)

    asyncio.run(run())


def test_replaced_transport_cannot_consume_buffered_operations() -> None:
    """A resumed session must discard bytes already buffered on its old transport."""

    async def run() -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(encode_frame({"type": "request"}))
        reader.feed_eof()
        server = object.__new__(IpcServer)
        attached = object()
        displaced = object()
        session = LogicalSession(
            connection_id=ConnectionId(uuid4()),
            capabilities=frozenset(),
            resume_token="test-token",
            transport=attached,  # type: ignore[arg-type]
        )
        await server._read_loop(reader, session, displaced)  # type: ignore[arg-type]

    asyncio.run(run())
