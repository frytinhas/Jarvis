from __future__ import annotations

import asyncio
import struct
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.core.runtime import JarvisCore
from jarvis.foundation.bootstrap import initialize_foundation
from jarvis.ipc.models import (
    MODEL_REGISTRY,
    PROFILE_MANAGEMENT,
    REQUEST_CANCEL,
    RUNTIME_MANAGER,
    SESSION_RESUME,
)
from jarvis.llm.fake import FakeLLMProvider
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.service import ProfileService
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


def test_runtime_capability_policy_and_lifecycle_are_core_owned(tmp_path: Path) -> None:
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
    provider = FakeLLMProvider()

    async def run() -> None:
        core = JarvisCore(provider=provider)
        task = asyncio.create_task(core.run())
        socket_path = paths.runtime / "core.sock"
        for _ in range(200):
            if socket_path.exists():
                break
            await asyncio.sleep(0.005)
        client = await RawTestClient.connect(
            socket_path,
            optional_capabilities=(MODEL_REGISTRY, PROFILE_MANAGEMENT, RUNTIME_MANAGER),
        )
        try:
            policy = await client.request(
                request_id=str(uuid4()), operation="installation.runtime.policy.get"
            )
            assert policy[-1]["payload"]["max_concurrent_runtimes"] == 2
            started = await client.request(
                request_id=str(uuid4()),
                operation="profiles.runtime.start",
                profile_id=str(profile.profile_id),
            )
            assert [item["event_type"] for item in started] == [
                "request.accepted",
                "request.started",
                "runtime.state_changed",
                "runtime.state_changed",
                "request.completed",
            ]
            snapshot = started[-1]["payload"]
            assert snapshot["state"] == "READY"
            assert set(snapshot) == {
                "runtime_id",
                "model_id",
                "state",
                "health",
                "started_at_utc",
                "ready_at_utc",
                "stopped_at_utc",
            }
            stopped = await client.request(
                request_id=str(uuid4()),
                operation="profiles.runtime.stop",
                profile_id=str(profile.profile_id),
            )
            assert stopped[-1]["payload"]["state"] == "STOPPED"
            await client.request(
                request_id=str(uuid4()),
                operation="profiles.runtime.start",
                profile_id=str(profile.profile_id),
            )
            preview_events = await client.request(
                request_id=str(uuid4()),
                operation="profiles.reset.preview",
                profile_id=str(profile.profile_id),
                payload={"scope": "whole-profile"},
            )
            preview = preview_events[-1]["payload"]["preview"]
            runtime_items = [item for item in preview["items"] if item["key"] == "runtime"]
            assert runtime_items == [
                {
                    "key": "runtime",
                    "action": "quiesce",
                    "current_count": 1,
                    "target_count": 0,
                    "will_change": True,
                }
            ]
            confirmed = await client.request(
                request_id=str(uuid4()),
                operation="profiles.reset.confirm",
                profile_id=str(profile.profile_id),
                payload={
                    "operation_id": preview["operation_id"],
                    "scope": "whole-profile",
                    "confirmation_token": preview["confirmation_token"],
                },
            )
            assert confirmed[-1]["event_type"] == "request.completed"
            assert len(provider.stops) == 2
            status = await client.request(
                request_id=str(uuid4()),
                operation="profiles.runtime.status",
                profile_id=str(profile.profile_id),
            )
            assert status[-1]["payload"]["state"] == "STOPPED"
            created = await client.request(
                request_id=str(uuid4()),
                operation="profiles.create",
                payload={"display_name": "Disposable Runtime"},
            )
            disposable_id = created[-1]["payload"]["profile"]["profile_id"]
            await client.request(
                request_id=str(uuid4()),
                operation="profiles.models.select",
                profile_id=disposable_id,
                payload={
                    "model_id": str(model.model_id),
                    "expected_profile_model_revision": 0,
                },
            )
            await client.request(
                request_id=str(uuid4()),
                operation="profiles.runtime.start",
                profile_id=disposable_id,
            )
            deletion = await client.request(
                request_id=str(uuid4()),
                operation="profiles.delete.preview",
                profile_id=disposable_id,
            )
            delete_preview = deletion[-1]["payload"]["preview"]
            deleted = await client.request(
                request_id=str(uuid4()),
                operation="profiles.delete.confirm",
                profile_id=disposable_id,
                payload={
                    "operation_id": delete_preview["operation_id"],
                    "confirmation_token": delete_preview["confirmation_token"],
                },
            )
            assert deleted[-1]["payload"]["deleted_profile_id"] == disposable_id
            assert len(provider.stops) == 3
        finally:
            await client.close()
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_runtime_operations_require_negotiated_capability() -> None:
    async def run() -> None:
        core = JarvisCore(provider=FakeLLMProvider())
        task = asyncio.create_task(core.run())
        socket_path = resolve_xdg_paths().runtime / "core.sock"
        for _ in range(200):
            if socket_path.exists():
                break
            await asyncio.sleep(0.005)
        client = await RawTestClient.connect(socket_path, optional_capabilities=(MODEL_REGISTRY,))
        try:
            response = await client.request(
                request_id=str(uuid4()), operation="installation.runtime.policy.get"
            )
            assert response[0]["error"]["code"] == "ipc.capability_mismatch"
        finally:
            await client.close()
        runtime_only = await RawTestClient.connect(
            socket_path, optional_capabilities=(RUNTIME_MANAGER,)
        )
        try:
            response = await runtime_only.request(
                request_id=str(uuid4()),
                operation="profiles.runtime.status",
                profile_id=str(
                    ProfileService(resolve_xdg_paths().data / "jarvis.sqlite3")
                    .ensure_jarvis()
                    .profile.profile_id
                ),
            )
            assert response[0]["error"]["code"] == "ipc.capability_mismatch"
        finally:
            await runtime_only.close()
        try:
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)
        finally:
            if not task.done():
                await core.request_shutdown()
                await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_disconnecting_client_does_not_cancel_accepted_core_runtime_start(
    tmp_path: Path,
) -> None:
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
    provider = FakeLLMProvider()
    provider.start_gate.clear()

    async def run() -> None:
        core = JarvisCore(provider=provider)
        task = asyncio.create_task(core.run())
        socket_path = paths.runtime / "core.sock"
        for _ in range(200):
            if socket_path.exists():
                break
            await asyncio.sleep(0.005)
        capabilities = (MODEL_REGISTRY, RUNTIME_MANAGER, SESSION_RESUME)
        client = await RawTestClient.connect(socket_path, optional_capabilities=capabilities)
        await client.send(
            {
                "type": "request",
                "protocol_version": 1,
                "request_id": str(uuid4()),
                "operation": "profiles.runtime.start",
                "profile_id": str(profile.profile_id),
                "payload": {},
            }
        )
        assert (await client.receive())["event_type"] == "request.accepted"
        assert (await client.receive())["event_type"] == "request.started"
        starting_event = await client.receive()
        assert isinstance(starting_event["payload"], dict)
        assert starting_event["payload"]["state"] == "STARTING"
        await client.close()
        provider.start_gate.set()
        for _ in range(200):
            if core.in_flight_count == 0:
                break
            await asyncio.sleep(0.005)
        assert core.in_flight_count == 0
        assert core.resources is not None
        snapshot = await core.resources.runtime_manager.status(profile.profile_id)
        assert snapshot.state.value == "READY"
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)
        assert len(provider.stops) == 1

    asyncio.run(run())


def test_runtime_start_cancellation_cleans_capacity_and_has_one_terminal(
    tmp_path: Path,
) -> None:
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
    provider = FakeLLMProvider()
    provider.start_gate.clear()

    async def run() -> None:
        core = JarvisCore(provider=provider)
        task = asyncio.create_task(core.run())
        socket_path = paths.runtime / "core.sock"
        for _ in range(200):
            if socket_path.exists():
                break
            await asyncio.sleep(0.005)
        client = await RawTestClient.connect(
            socket_path,
            optional_capabilities=(MODEL_REGISTRY, RUNTIME_MANAGER, REQUEST_CANCEL),
        )
        request_id = str(uuid4())
        await client.send(
            {
                "type": "request",
                "protocol_version": 1,
                "request_id": request_id,
                "operation": "profiles.runtime.start",
                "profile_id": str(profile.profile_id),
                "payload": {},
            }
        )
        assert (await client.receive())["event_type"] == "request.accepted"
        assert (await client.receive())["event_type"] == "request.started"
        starting_event = await client.receive()
        assert isinstance(starting_event["payload"], dict)
        assert starting_event["payload"]["state"] == "STARTING"
        await client.send({"type": "cancel", "protocol_version": 1, "request_id": request_id})
        assert (await client.receive())["type"] == "cancel.result"
        terminal = await client.receive()
        assert terminal["event_type"] == "request.cancelled"
        assert terminal["terminal"] is True
        assert core.resources is not None
        for _ in range(200):
            if not core.resources.runtime_manager.has_active(profile.profile_id):
                break
            await asyncio.sleep(0.005)
        assert not core.resources.runtime_manager.has_active(profile.profile_id)
        assert core.resources.runtime_manager.pending_start_count == 0
        await client.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())
