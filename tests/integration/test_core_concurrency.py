from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.core.requests import RequestContext
from jarvis.core.runtime import JarvisCore
from jarvis.ipc.models import CORE_CONTROL, CORE_HEALTH, REQUEST_CANCEL
from jarvis.storage.xdg import resolve_xdg_paths
from tests.support.ipc_client import RawTestClient

pytestmark = pytest.mark.integration


async def _start(
    handlers: dict[str, object],
) -> tuple[JarvisCore, asyncio.Task[None], Path]:
    core = JarvisCore(handlers=handlers)  # type: ignore[arg-type]
    task = asyncio.create_task(core.run())
    path = resolve_xdg_paths().runtime / "core.sock"
    for _ in range(200):
        if path.exists():
            return core, task, path
        await asyncio.sleep(0.005)
    raise AssertionError("Core did not start")


async def _request_start(client: RawTestClient, request_id: str, operation: str) -> None:
    await client.send(
        {
            "type": "request",
            "protocol_version": 1,
            "request_id": request_id,
            "operation": operation,
            "payload": {},
        }
    )
    assert (await client.receive())["event_type"] == "request.accepted"
    assert (await client.receive())["event_type"] == "request.started"


def test_two_sessions_are_isolated_for_collision_cancel_and_completion() -> None:
    releases = {"test.one": asyncio.Event(), "test.two": asyncio.Event()}

    async def handler(context: RequestContext) -> dict[str, object]:
        await releases[context.request.operation].wait()
        return {"operation": context.request.operation}

    async def run() -> None:
        core, core_task, path = await _start({"test.one": handler, "test.two": handler})
        capabilities = (REQUEST_CANCEL, CORE_CONTROL)
        first = await RawTestClient.connect(path, optional_capabilities=capabilities)
        second = await RawTestClient.connect(path, optional_capabilities=capabilities)
        first_id = str(uuid4())
        second_id = str(uuid4())
        try:
            await asyncio.gather(
                _request_start(first, first_id, "test.one"),
                _request_start(second, second_id, "test.two"),
            )
            await second.send(
                {
                    "type": "cancel",
                    "protocol_version": 1,
                    "request_id": first_id,
                }
            )
            wrong_owner = await second.receive()
            assert wrong_owner["error"]["code"] == "ipc.request_not_owned"  # type: ignore[index]
            await second.send(
                {
                    "type": "request",
                    "protocol_version": 1,
                    "request_id": first_id,
                    "operation": "test.one",
                    "payload": {},
                }
            )
            conflict = await second.receive()
            assert conflict["error"]["code"] == "ipc.request_id_conflict"  # type: ignore[index]
            await first.send({"type": "cancel", "protocol_version": 1, "request_id": first_id})
            assert (await first.receive())["outcome"] == "requested"
            assert (await first.receive())["event_type"] == "request.cancelled"
            releases["test.two"].set()
            terminal = await second.receive()
            assert terminal["event_type"] == "request.completed"
            assert terminal["payload"] == {"operation": "test.two"}
        finally:
            releases["test.one"].set()
            await first.close()
            await second.close()
            await core.request_shutdown()
            await asyncio.wait_for(core_task, 5)

    asyncio.run(run())


def test_preacceptance_errors_do_not_create_state_or_close_connection() -> None:
    async def run() -> None:
        core, core_task, path = await _start({})
        client = await RawTestClient.connect(
            path, optional_capabilities=(CORE_HEALTH, CORE_CONTROL)
        )
        try:
            bad_id = str(uuid4())
            await client.send(
                {
                    "type": "request",
                    "protocol_version": 1,
                    "request_id": bad_id,
                    "operation": "future.unsupported",
                    "payload": {},
                }
            )
            error = await client.receive()
            assert error["error"]["code"] == "ipc.operation_not_supported"  # type: ignore[index]
            health = await client.request(request_id=str(uuid4()), operation="core.health")
            assert health[-1]["event_type"] == "request.completed"
            assert core.resources is not None
        finally:
            await client.close()
            await core.request_shutdown()
            await asyncio.wait_for(core_task, 5)

    asyncio.run(run())
