from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.core.requests import RequestContext
from jarvis.core.runtime import JarvisCore
from jarvis.ipc.client import JarvisIpcClient
from jarvis.ipc.errors import IpcError
from jarvis.ipc.models import (
    CORE_CONTROL,
    CORE_HEALTH,
    EVENT_REPLAY,
    REQUEST_CANCEL,
    SESSION_RESUME,
    RequestId,
)
from jarvis.storage.xdg import resolve_xdg_paths

pytestmark = pytest.mark.integration


async def _start(handler: object | None = None) -> tuple[JarvisCore, asyncio.Task[None], Path]:
    handlers = None if handler is None else {"test.wait": handler}
    core = JarvisCore(handlers=handlers)  # type: ignore[arg-type]
    task = asyncio.create_task(core.run())
    path = resolve_xdg_paths().runtime / "core.sock"
    for _ in range(200):
        if path.exists():
            return core, task, path
        await asyncio.sleep(0.005)
    raise AssertionError("Core did not start")


def test_internal_client_streams_and_resumes_without_repository_access() -> None:
    async def run() -> None:
        core, task, path = await _start()
        capabilities = (CORE_HEALTH, CORE_CONTROL, SESSION_RESUME, EVENT_REPLAY)
        client = await JarvisIpcClient.connect(path, optional_capabilities=capabilities)
        try:
            events = [event async for event in client.request("core.health")]
            assert [event["sequence"] for event in events] == [1, 2, 3]
            assert events[-1]["terminal"] is True
            resumed = await client.resume()
            try:
                assert resumed.handshake.connection_id == client.handshake.connection_id
                assert resumed.handshake.resume_token != client.handshake.resume_token
            finally:
                await resumed.close()
        finally:
            await client.close()
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_internal_client_cancels_only_named_request() -> None:
    async def handler(context: RequestContext) -> dict[str, object]:
        await context.cancellation.wait()
        return {"unexpected": True}

    async def run() -> None:
        core, task, path = await _start(handler)
        capabilities = (REQUEST_CANCEL, CORE_CONTROL)
        client = await JarvisIpcClient.connect(path, optional_capabilities=capabilities)
        request_id = RequestId(uuid4())

        async def collect() -> list[dict[str, object]]:
            return [event async for event in client.request("test.wait", request_id=request_id)]

        collector = asyncio.create_task(collect())
        for _ in range(100):
            if core.in_flight_count == 1:
                break
            await asyncio.sleep(0.005)
        result = await client.cancel(request_id)
        assert result["outcome"] == "requested"
        events = await collector
        assert events[-1]["event_type"] == "request.cancelled"
        await client.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_per_session_request_limit_is_enforced_before_task_creation() -> None:
    release = asyncio.Event()

    async def handler(_context: RequestContext) -> dict[str, object]:
        await release.wait()
        return {"done": True}

    async def run() -> None:
        core, task, path = await _start(handler)
        client = await JarvisIpcClient.connect(path, optional_capabilities=(CORE_CONTROL,))

        async def collect(request_id: RequestId) -> list[dict[str, object]]:
            return [event async for event in client.request("test.wait", request_id=request_id)]

        collectors = [asyncio.create_task(collect(RequestId(uuid4()))) for _ in range(17)]
        for _ in range(200):
            if core.in_flight_count == 16 and any(collector.done() for collector in collectors):
                break
            await asyncio.sleep(0.005)
        assert core.in_flight_count == 16
        assert sum(collector.done() for collector in collectors) == 1
        release.set()
        results = await asyncio.gather(*collectors)
        errors = [
            result
            for result in results
            if result[-1].get("type") == "error"
            and result[-1]["error"]["code"] == "ipc.request_limit"  # type: ignore[index]
        ]
        assert len(errors) == 1
        assert all(result[-1].get("terminal") is True for result in results if result not in errors)
        await client.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_control_error_for_active_request_does_not_end_its_stream() -> None:
    release = asyncio.Event()

    async def handler(_context: RequestContext) -> dict[str, object]:
        await release.wait()
        return {"done": True}

    async def run() -> None:
        core, task, path = await _start(handler)
        capabilities = (EVENT_REPLAY, CORE_CONTROL)
        client = await JarvisIpcClient.connect(path, optional_capabilities=capabilities)
        request_id = RequestId(uuid4())

        async def collect() -> list[dict[str, object]]:
            return [event async for event in client.request("test.wait", request_id=request_id)]

        collector = asyncio.create_task(collect())
        for _ in range(100):
            if core.in_flight_count == 1:
                break
            await asyncio.sleep(0.005)
        with pytest.raises(IpcError) as caught:
            await client.replay(request_id, after_sequence=-1)
        assert caught.value.code == "ipc.invalid_message"

        release.set()
        events = await asyncio.wait_for(collector, 5)
        assert events[-1]["event_type"] == "request.completed"
        await client.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())
