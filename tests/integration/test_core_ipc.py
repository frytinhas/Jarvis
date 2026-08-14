from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.core.requests import RequestContext
from jarvis.core.runtime import JarvisCore
from jarvis.ipc.models import CORE_CONTROL, CORE_HEALTH, PROFILE_CATALOG, REQUEST_CANCEL
from jarvis.storage.xdg import resolve_xdg_paths
from tests.support.ipc_client import RawTestClient

pytestmark = pytest.mark.integration


async def _running_core(
    *, handlers: dict[str, object] | None = None
) -> tuple[JarvisCore, asyncio.Task[None], Path]:
    typed_handlers = handlers  # keep call sites concise while handlers are test-only
    core = JarvisCore(handlers=typed_handlers)  # type: ignore[arg-type]
    task = asyncio.create_task(core.run())
    socket_path = resolve_xdg_paths().runtime / "core.sock"
    for _ in range(200):
        if socket_path.exists():
            return core, task, socket_path
        if task.done():
            await task
        await asyncio.sleep(0.005)
    raise AssertionError("Core did not publish its socket")


async def _stop(core: JarvisCore, task: asyncio.Task[None]) -> None:
    await core.request_shutdown()
    await asyncio.wait_for(task, 5)


def test_handshake_health_and_exact_profile_catalog() -> None:
    async def run() -> None:
        core, task, socket_path = await _running_core()
        client = await RawTestClient.connect(
            socket_path,
            optional_capabilities=(CORE_HEALTH, PROFILE_CATALOG, CORE_CONTROL),
        )
        try:
            assert client.hello is not None
            assert client.hello["type"] == "hello.ok"
            health = await client.request(request_id=str(uuid4()), operation="core.health")
            assert [event["sequence"] for event in health] == [1, 2, 3]
            result = health[-1]["payload"]
            assert isinstance(result, dict)
            assert result["state"] == "READY"
            listed = await client.request(request_id=str(uuid4()), operation="profiles.list")
            payload = listed[-1]["payload"]
            assert isinstance(payload, dict)
            profiles = payload["profiles"]
            assert isinstance(profiles, list)
            assert len(profiles) == 1
            profile = profiles[0]
            assert isinstance(profile, dict)
            assert set(profile) == {
                "profile_id",
                "kind",
                "display_name",
                "command_alias",
                "identity_revision",
            }
            assert profile["command_alias"] == "jarvis"
            got = await client.request(
                request_id=str(uuid4()),
                operation="profiles.get",
                profile_id=str(profile["profile_id"]),
            )
            got_payload = got[-1]["payload"]
            assert isinstance(got_payload, dict)
            assert got_payload["profile"] == profile
        finally:
            await client.close()
            await _stop(core, task)

    asyncio.run(run())


def test_request_collision_and_wrong_profile_identifier_are_preacceptance_errors() -> None:
    async def wait_handler(context: RequestContext) -> dict[str, object]:
        await context.cancellation.wait()
        return {"unexpected": True}

    async def run() -> None:
        core, task, socket_path = await _running_core(handlers={"test.wait": wait_handler})
        client = await RawTestClient.connect(
            socket_path, optional_capabilities=(REQUEST_CANCEL, CORE_CONTROL)
        )
        request_id = str(uuid4())
        try:
            await client.send(
                {
                    "type": "request",
                    "protocol_version": 1,
                    "request_id": request_id,
                    "operation": "test.wait",
                    "payload": {},
                }
            )
            assert (await client.receive())["event_type"] == "request.accepted"
            assert (await client.receive())["event_type"] == "request.started"
            await client.send(
                {
                    "type": "request",
                    "protocol_version": 1,
                    "request_id": request_id,
                    "operation": "test.wait",
                    "payload": {},
                }
            )
            conflict = await client.receive()
            assert conflict["type"] == "error"
            assert conflict["error"]["code"] == "ipc.request_id_conflict"  # type: ignore[index]
            await client.send(
                {
                    "type": "cancel",
                    "protocol_version": 1,
                    "request_id": request_id,
                }
            )
            assert (await client.receive())["type"] == "cancel.result"
            assert (await client.receive())["event_type"] == "request.cancelled"
            assert core.in_flight_count == 0
        finally:
            await client.close()
            await _stop(core, task)

    asyncio.run(run())


def test_disconnect_does_not_cancel_accepted_work() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    observed: list[bool] = []

    async def handler(context: RequestContext) -> dict[str, object]:
        started.set()
        await release.wait()
        observed.append(context.cancellation.requested)
        return {"done": True}

    async def run() -> None:
        core, task, socket_path = await _running_core(handlers={"test.block": handler})
        client = await RawTestClient.connect(socket_path, optional_capabilities=(CORE_CONTROL,))
        await client.send(
            {
                "type": "request",
                "protocol_version": 1,
                "request_id": str(uuid4()),
                "operation": "test.block",
                "payload": {},
            }
        )
        await client.receive()
        await client.receive()
        await started.wait()
        await client.close()
        release.set()
        for _ in range(100):
            if observed:
                break
            await asyncio.sleep(0.005)
        assert observed == [False]
        await _stop(core, task)

    asyncio.run(run())


def test_shutdown_terminal_is_observed_before_server_closure() -> None:
    async def run() -> None:
        _core, task, socket_path = await _running_core()
        client = await RawTestClient.connect(socket_path, optional_capabilities=(CORE_CONTROL,))
        events = await client.request(request_id=str(uuid4()), operation="core.shutdown")
        assert events[-1]["event_type"] == "request.completed"
        assert events[-1]["payload"] == {"shutdown_scheduled": True}
        await asyncio.wait_for(task, 5)
        assert not socket_path.exists()

    asyncio.run(run())
