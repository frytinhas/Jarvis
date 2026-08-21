from __future__ import annotations

import asyncio
import json
import sqlite3
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest

from jarvis.config.defaults import DefaultsRegistry
from jarvis.core.runtime import JarvisCore
from jarvis.diagnostics.sink import InfrastructureDiagnosticSink
from jarvis.foundation.bootstrap import initialize_foundation
from jarvis.foundation.clock import SystemClock
from jarvis.foundation.identifiers import RandomIdGenerator
from jarvis.ipc.client import JarvisIpcClient
from jarvis.ipc.models import (
    EVENT_REPLAY,
    MODEL_REGISTRY,
    PROFILE_CATALOG,
    REQUEST_CANCEL,
    REQUEST_STREAM,
    RequestId,
)
from jarvis.models.errors import (
    ConcurrentModelModificationError,
    InvalidRuntimeLocationError,
    ModelDatabaseError,
    ModelUnavailableError,
)
from jarvis.models.models import ModelRuntimeConfig
from jarvis.models.repository import ModelRepository
from jarvis.models.scanner import ScanResult, scan_directories
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.destructive import ConfirmDestructiveOperation, DestructivePreview, ResetScope
from jarvis.profiles.errors import ConfirmationStaleError, ProfileNotFoundError
from jarvis.profiles.models import CreateProfile, ProfileId
from jarvis.profiles.service import ProfileConfigService, ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.xdg import resolve_xdg_paths

pytestmark = pytest.mark.integration


def _fixture(path: Path, name: bytes = b"Tiny") -> None:
    def string(value: bytes) -> bytes:
        return struct.pack("<Q", len(value)) + value

    path.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + string(b"general.name")
        + struct.pack("<I", 8)
        + string(name)
    )


def _confirm(preview: DestructivePreview) -> ConfirmDestructiveOperation:
    return ConfirmDestructiveOperation(
        preview.operation_id, preview.target, preview.profile_id, preview.confirmation_token
    )


async def _request(
    client: JarvisIpcClient,
    operation: str,
    *,
    payload: dict[str, object] | None = None,
    profile_id: ProfileId | None = None,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    request = client.request(
        operation,
        payload=payload,
        profile_id=profile_id,
    )
    async with asyncio.timeout(2):
        async for event in request:
            events.append(event)
    return events


async def _start_core() -> tuple[JarvisCore, asyncio.Task[None], Path]:
    core = JarvisCore()
    task = asyncio.create_task(core.run())
    socket_path = resolve_xdg_paths().runtime / "core.sock"
    for _ in range(200):
        if socket_path.exists():
            return core, task, socket_path
        if task.done():
            await task
        await asyncio.sleep(0.005)
    raise AssertionError("Core did not publish its socket")


async def _stop_core(core: JarvisCore, task: asyncio.Task[None]) -> None:
    await core.request_shutdown()
    await asyncio.wait_for(task, 5)


def test_profile_model_selection_terminates_through_real_core_ipc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    for key in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(key, str(tmp_path / key))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    models = tmp_path / "models"
    models.mkdir()
    _fixture(models / "tiny.gguf")

    async def run() -> None:
        core, core_task, socket_path = await _start_core()
        client = await JarvisIpcClient.connect(
            socket_path,
            optional_capabilities=(MODEL_REGISTRY, PROFILE_CATALOG),
        )
        try:
            profiles = await _request(client, "profiles.list")
            profile_rows = profiles[-1]["payload"]["profiles"]  # type: ignore[index]
            profile_id = ProfileId.parse(profile_rows[0]["profile_id"])
            await _request(
                client,
                "installation.runtime.update",
                payload={"directories": [str(models)], "runtime_path": None},
            )
            refreshed = await _request(client, "models.refresh")
            model_id = refreshed[-1]["payload"]["models"][0]["model_id"]  # type: ignore[index]

            selected = await _request(
                client,
                "profiles.models.select",
                profile_id=profile_id,
                payload={"model_id": model_id, "expected_profile_model_revision": 0},
            )

            assert [event["event_type"] for event in selected] == [
                "request.accepted",
                "request.started",
                "request.completed",
            ]
            assert sum(event["terminal"] is True for event in selected) == 1
            associations = selected[-1]["payload"]["associations"]  # type: ignore[index]
            assert associations[0]["model_id"] == model_id
            assert associations[0]["selected"] is True
        finally:
            await client.close()
            await _stop_core(core, core_task)

    asyncio.run(run())


def test_all_model_registry_routes_capabilities_errors_and_restart_over_real_ipc(
    tmp_path: Path,
) -> None:
    models = tmp_path / "ipc-models"
    models.mkdir()
    _fixture(models / "tiny.gguf")

    async def run() -> None:
        core, task, socket_path = await _start_core()
        unprivileged = await JarvisIpcClient.connect(socket_path)
        client = await JarvisIpcClient.connect(
            socket_path,
            optional_capabilities=(MODEL_REGISTRY, PROFILE_CATALOG),
        )
        profile_id: ProfileId
        model_id: str
        try:
            mismatch = await _request(unprivileged, "models.list")
            assert len(mismatch) == 1 and mismatch[0]["type"] == "error"
            assert mismatch[0]["error"]["code"] == "ipc.capability_mismatch"  # type: ignore[index]
            malformed = await _request(
                client,
                "profiles.models.select",
                profile_id=ProfileId.parse("10000000-0000-4000-8000-000000000001"),
                payload={"model_id": "invalid", "expected_profile_model_revision": 0},
            )
            assert len(malformed) == 1 and malformed[0]["type"] == "error"
            missing_profile = await _request(
                client,
                "profiles.models.list",
                profile_id=ProfileId.parse("10000000-0000-4000-8000-000000000099"),
            )
            assert [event.get("event_type") for event in missing_profile] == [
                "request.accepted",
                "request.started",
                "error",
            ]
            assert missing_profile[-1]["error"]["code"] == "profile.not_found"  # type: ignore[index]

            profiles = await _request(client, "profiles.list")
            rows = profiles[-1]["payload"]["profiles"]  # type: ignore[index]
            profile_id = ProfileId.parse(rows[0]["profile_id"])
            updated_location = await _request(
                client,
                "installation.runtime.update",
                payload={"directories": [str(models)], "runtime_path": None},
            )
            assert updated_location[-1]["event_type"] == "request.completed"
            assert (await _request(client, "installation.runtime.get"))[-1]["payload"] == (
                updated_location[-1]["payload"]
            )
            refreshed = await _request(client, "models.refresh")
            model = refreshed[-1]["payload"]["models"][0]  # type: ignore[index]
            model_id = str(model["model_id"])
            assert (await _request(client, "models.list"))[-1]["event_type"] == "request.completed"
            detail = await _request(client, "models.get", payload={"model_id": model_id})
            assert detail[-1]["payload"]["model"] == model  # type: ignore[index]

            selected = await _request(
                client,
                "profiles.models.select",
                profile_id=profile_id,
                payload={"model_id": model_id, "expected_profile_model_revision": 0},
            )
            association = selected[-1]["payload"]["associations"][0]  # type: ignore[index]
            assert association["config"]["temperature"] == "0.8"
            listed = await _request(client, "profiles.models.list", profile_id=profile_id)
            assert listed[-1]["payload"]["associations"] == [association]  # type: ignore[index]
            config = await _request(
                client,
                "profiles.models.config.get",
                profile_id=profile_id,
                payload={"model_id": model_id},
            )
            wire_config = dict(config[-1]["payload"]["config"])  # type: ignore[index]
            wire_config.update({"reasoning": "high", "context_window": 4096, "temperature": "0.25"})
            configured = await _request(
                client,
                "profiles.models.config.update",
                profile_id=profile_id,
                payload={
                    "model_id": model_id,
                    "config": wire_config,
                    "expected_profile_model_revision": 1,
                },
            )
            assert configured[-1]["payload"]["revision"] == 2  # type: ignore[index]
            assert configured[-1]["payload"]["config"]["temperature"] == "0.25"  # type: ignore[index]
            stale = await _request(
                client,
                "profiles.models.config.update",
                profile_id=profile_id,
                payload={
                    "model_id": model_id,
                    "config": wire_config,
                    "expected_profile_model_revision": 1,
                },
            )
            assert [event.get("event_type") for event in stale] == [
                "request.accepted",
                "request.started",
                "error",
            ]
            assert stale[-1]["error"]["code"] == "model.concurrent_modification"  # type: ignore[index]
        finally:
            await unprivileged.close()
            await client.close()
            await _stop_core(core, task)

        restarted, restarted_task, restarted_socket = await _start_core()
        restarted_client = await JarvisIpcClient.connect(
            restarted_socket, required_capabilities=(REQUEST_STREAM, MODEL_REGISTRY)
        )
        try:
            persisted = await _request(
                restarted_client,
                "profiles.models.config.get",
                profile_id=profile_id,
                payload={"model_id": model_id},
            )
            assert persisted[-1]["payload"]["config"]["reasoning"] == "high"  # type: ignore[index]
            assert persisted[-1]["payload"]["config"]["temperature"] == "0.25"  # type: ignore[index]
        finally:
            await restarted_client.close()
            await _stop_core(restarted, restarted_task)

    asyncio.run(run())


def test_cancelled_selection_has_one_terminal_and_another_request_is_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    models = tmp_path / "cancel-models"
    models.mkdir()
    _fixture(models / "tiny.gguf")
    entered = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    original = ModelRegistryService.select

    def blocked_select(self: ModelRegistryService, *args: object) -> None:
        entered.set()
        assert release.wait(2)
        try:
            original(self, *args)  # type: ignore[arg-type]
        finally:
            finished.set()

    monkeypatch.setattr(ModelRegistryService, "select", blocked_select)

    async def run() -> None:
        core, task, socket_path = await _start_core()
        client = await JarvisIpcClient.connect(
            socket_path,
            optional_capabilities=(MODEL_REGISTRY, PROFILE_CATALOG, REQUEST_CANCEL, EVENT_REPLAY),
        )
        try:
            profiles = await _request(client, "profiles.list")
            rows = profiles[-1]["payload"]["profiles"]  # type: ignore[index]
            profile_id = ProfileId.parse(rows[0]["profile_id"])
            await _request(
                client,
                "installation.runtime.update",
                payload={"directories": [str(models)], "runtime_path": None},
            )
            refreshed = await _request(client, "models.refresh")
            model_id = refreshed[-1]["payload"]["models"][0]["model_id"]  # type: ignore[index]
            request_id = RequestId(uuid4())
            events: list[dict[str, object]] = []

            async def consume() -> None:
                async for event in client.request(
                    "profiles.models.select",
                    profile_id=profile_id,
                    payload={"model_id": model_id, "expected_profile_model_revision": 0},
                    request_id=request_id,
                ):
                    events.append(event)

            consumer = asyncio.create_task(consume())
            assert await asyncio.to_thread(entered.wait, 1)
            independent = await _request(client, "models.list")
            assert independent[-1]["event_type"] == "request.completed"
            cancelled = await client.cancel(request_id)
            assert cancelled["outcome"] == "requested"
            release.set()
            await asyncio.wait_for(consumer, 2)
            assert [event.get("event_type") for event in events] == [
                "request.accepted",
                "request.started",
                "request.cancelled",
            ]
            await asyncio.sleep(0)
            replay = await client.replay(request_id, after_sequence=0)
            replay_events = replay["events"]
            assert isinstance(replay_events, list)
            assert [event["event_type"] for event in replay_events] == [
                "request.accepted",
                "request.started",
                "request.cancelled",
            ]
            assert await asyncio.to_thread(finished.wait, 2)
            associations = await _request(client, "profiles.models.list", profile_id=profile_id)
            assert associations[-1]["payload"]["associations"][0]["selected"] is True  # type: ignore[index]
        finally:
            release.set()
            await client.close()
            await _stop_core(core, task)

    asyncio.run(run())


def test_refresh_reconciles_missing_replacement_and_profile_specific_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    initialize_foundation()
    database = tmp_path / "data" / "jarvis-cli" / "jarvis.sqlite3"
    profiles = ProfileService(database)
    jarvis = profiles.ensure_jarvis()
    work = profiles.create_profile(CreateProfile("Work"))
    models = tmp_path / "models"
    models.mkdir()
    model = models / "tiny.gguf"
    _fixture(model)
    registry = ModelRegistryService(database)
    registry.update_runtime_location((str(models),), None)
    first = registry.refresh().records
    assert len(first) == 1 and first[0].availability.value == "available"
    registry.select(jarvis.profile.profile_id, first[0].model_id, 0)
    registry.select(work.profile.profile_id, first[0].model_id, 0)
    registry.update_config(
        work.profile.profile_id, first[0].model_id, ModelRuntimeConfig(reasoning="high"), 1
    )
    jarvis_config = cast(
        dict[str, object],
        registry.get_config(jarvis.profile.profile_id, first[0].model_id)["config"],
    )
    work_config = cast(
        dict[str, object], registry.get_config(work.profile.profile_id, first[0].model_id)["config"]
    )
    assert jarvis_config["reasoning"] == "medium"
    assert work_config["reasoning"] == "high"
    model.unlink()
    missing = registry.refresh().records
    assert missing[0].availability.value == "missing"
    with pytest.raises(ModelUnavailableError):
        registry.select(jarvis.profile.profile_id, first[0].model_id, 1)
    _fixture(model, b"Replacement")
    replacement = registry.refresh().records
    assert {record.availability.value for record in replacement} == {"available", "missing"}
    assert registry.get(first[0].model_id).availability_reason == "replaced"
    assert registry.associations(jarvis.profile.profile_id)[0]["availability"] == "missing"
    assert (
        next(record for record in replacement if record.availability.value == "available").model_id
        != first[0].model_id
    )


def test_partial_refresh_preserves_known_models_that_were_not_scanned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_foundation()
    database = resolve_xdg_paths().data / "jarvis.sqlite3"
    models = tmp_path / "bounded-models"
    models.mkdir()
    _fixture(models / "a.gguf", b"A")
    _fixture(models / "b.gguf", b"B")
    registry = ModelRegistryService(database)
    registry.update_runtime_location((str(models),), None)

    complete = registry.refresh()
    assert complete.partial_reason is None
    assert len(complete.records) == 2
    known_ids = {record.model_id for record in complete.records}

    monkeypatch.setattr("jarvis.models.scanner.MAX_CANDIDATES", 1)
    partial = registry.refresh()
    assert partial.partial_reason == "candidates"
    assert len(partial.records) == 2
    assert {record.model_id for record in partial.records} == known_ids
    assert {record.availability.value for record in partial.records} == {"available"}


def test_depth_limited_refresh_preserves_previously_known_nested_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_foundation()
    database = resolve_xdg_paths().data / "jarvis.sqlite3"
    models = tmp_path / "depth-limited-models"
    nested = models / "nested"
    nested.mkdir(parents=True)
    _fixture(nested / "candidate.gguf")
    registry = ModelRegistryService(database)
    registry.update_runtime_location((str(models),), None)
    complete = registry.refresh()
    assert len(complete.records) == 1

    monkeypatch.setattr("jarvis.models.scanner.MAX_DEPTH", 0)
    partial = registry.refresh()
    assert partial.partial_reason == "depth"
    assert len(partial.records) == 1
    assert partial.records[0].availability.value == "available"


def test_runtime_location_rejects_configured_symlink_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    for key in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(key, str(tmp_path / key))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    initialize_foundation()
    registry = ModelRegistryService(tmp_path / "XDG_DATA_HOME" / "jarvis-cli" / "jarvis.sqlite3")
    directory = tmp_path / "directory"
    directory.mkdir()
    executable = tmp_path / "runtime-bin"
    executable.write_text("not run")
    directory_link = tmp_path / "directory-link"
    directory_link.symlink_to(directory, target_is_directory=True)
    executable_link = tmp_path / "runtime-link"
    executable_link.symlink_to(executable)
    with pytest.raises(InvalidRuntimeLocationError):
        registry.update_runtime_location((str(directory_link),), None)
    with pytest.raises(InvalidRuntimeLocationError):
        registry.update_runtime_location((), str(executable_link))
    with pytest.raises(InvalidRuntimeLocationError):
        registry.update_runtime_location(tuple(str(directory) for _ in range(33)), None)
    deduplicated = registry.update_runtime_location((str(directory), f"{directory}/."), None)
    assert deduplicated.model_directories == (directory.resolve(),)


def test_runtime_location_rejects_directory_and_runtime_identity_swaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_foundation()
    registry = ModelRegistryService(resolve_xdg_paths().data / "jarvis.sqlite3")
    directory = tmp_path / "configured-models"
    directory.mkdir()
    moved_directory = tmp_path / "original-models"
    original_resolve = Path.resolve
    swapped = False

    def swap_directory_on_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        nonlocal swapped
        if self == directory and not swapped:
            swapped = True
            directory.rename(moved_directory)
            directory.mkdir()
        return original_resolve(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "resolve", swap_directory_on_resolve)
    with pytest.raises(InvalidRuntimeLocationError):
        registry.update_runtime_location((str(directory),), None)
    monkeypatch.setattr(Path, "resolve", original_resolve)

    runtime = tmp_path / "llama-server"
    runtime.write_text("original")
    moved_runtime = tmp_path / "original-llama-server"
    swapped = False

    def swap_runtime_on_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        nonlocal swapped
        if self == runtime and not swapped:
            swapped = True
            runtime.rename(moved_runtime)
            runtime.write_text("replacement")
        return original_resolve(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "resolve", swap_runtime_on_resolve)
    with pytest.raises(InvalidRuntimeLocationError):
        registry.update_runtime_location((), str(runtime))


def test_profile_model_clone_missing_reset_and_delete_lifecycle(tmp_path: Path) -> None:
    initialize_foundation()
    database = resolve_xdg_paths().data / "jarvis.sqlite3"
    profiles = ProfileService(database)
    configs = ProfileConfigService(database)
    jarvis = profiles.ensure_jarvis()
    models = tmp_path / "lifecycle-models"
    models.mkdir()
    candidate = models / "tiny.gguf"
    _fixture(candidate)
    registry = ModelRegistryService(database)
    registry.update_runtime_location((str(models),), None)
    model = registry.refresh().records[0]
    registry.select(jarvis.profile.profile_id, model.model_id, 0)
    registry.update_config(
        jarvis.profile.profile_id,
        model.model_id,
        ModelRuntimeConfig(reasoning="high", context_window=4096),
        1,
    )

    clone = profiles.create_profile(CreateProfile("Clone"))
    cloned = registry.associations(clone.profile.profile_id)
    assert len(cloned) == 1
    assert cloned[0]["selected"] is True
    assert cloned[0]["revision"] == 1
    assert (
        cloned[0]["config"]
        == registry.get_config(jarvis.profile.profile_id, model.model_id)["config"]
    )

    candidate.unlink()
    registry.refresh()
    missing_clone = profiles.create_profile(CreateProfile("Missing Clone"))
    inherited = registry.associations(missing_clone.profile.profile_id)
    assert inherited[0]["selected"] is True
    assert inherited[0]["availability"] == "missing"

    stale_reset = configs.preview_reset(clone.profile.profile_id, ResetScope.WHOLE_PROFILE)
    registry.update_config(
        clone.profile.profile_id,
        model.model_id,
        ModelRuntimeConfig(reasoning="low"),
        1,
    )
    with pytest.raises(ConfirmationStaleError):
        configs.confirm_reset(_confirm(stale_reset))
    reset = configs.preview_reset(clone.profile.profile_id, ResetScope.WHOLE_PROFILE)
    assert (
        next(item.current_count for item in reset.items if item.key == "profile-model-associations")
        == 1
    )
    configs.confirm_reset(_confirm(reset))
    assert registry.associations(clone.profile.profile_id) == ()

    deletion = profiles.preview_delete(missing_clone.profile.profile_id)
    profiles.confirm_delete(_confirm(deletion))
    with pytest.raises(ProfileNotFoundError):
        registry.associations(missing_clone.profile.profile_id)
    with SQLiteDatabase(database) as store:
        assert (
            store.connection()
            .execute(
                "SELECT count(*) FROM profile_models WHERE profile_id = ?",
                (str(missing_clone.profile.profile_id),),
            )
            .fetchone()[0]
            == 0
        )
    with pytest.raises(ProfileNotFoundError):
        profiles.get_profile(missing_clone.profile.profile_id)


def test_concurrent_profile_model_update_reset_and_delete_remain_atomic(tmp_path: Path) -> None:
    initialize_foundation()
    database = resolve_xdg_paths().data / "jarvis.sqlite3"
    profiles = ProfileService(database)
    configs = ProfileConfigService(database)
    profiles.ensure_jarvis()
    models = tmp_path / "race-models"
    models.mkdir()
    _fixture(models / "tiny.gguf")
    registry = ModelRegistryService(database)
    registry.update_runtime_location((str(models),), None)
    model = registry.refresh().records[0]

    reset_target = profiles.create_profile(CreateProfile("Reset Target"))
    registry.select(reset_target.profile.profile_id, model.model_id, 0)
    reset = _confirm(
        configs.preview_reset(reset_target.profile.profile_id, ResetScope.WHOLE_PROFILE)
    )
    barrier = threading.Barrier(2)

    def update() -> str:
        barrier.wait()
        try:
            registry.update_config(
                reset_target.profile.profile_id,
                model.model_id,
                ModelRuntimeConfig(reasoning="max"),
                1,
            )
            return "updated"
        except ConcurrentModelModificationError:
            return "stale"

    def reset_profile() -> str:
        barrier.wait()
        try:
            configs.confirm_reset(reset)
            return "reset"
        except ConfirmationStaleError:
            return "stale_preview"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = {pool.submit(update), pool.submit(reset_profile)}
        reset_outcomes = {future.result(timeout=5) for future in outcomes}
        assert reset_outcomes <= {"updated", "stale", "reset", "stale_preview"}
    remaining = registry.associations(reset_target.profile.profile_id)
    if remaining:
        assert remaining[0]["revision"] == 2
        assert remaining[0]["config"]["reasoning"] == "max"  # type: ignore[index]

    delete_target = profiles.create_profile(CreateProfile("Delete Target"))
    registry.select(delete_target.profile.profile_id, model.model_id, 0)
    deletion = _confirm(profiles.preview_delete(delete_target.profile.profile_id))
    barrier = threading.Barrier(2)

    def select_again() -> str:
        barrier.wait()
        try:
            registry.select(delete_target.profile.profile_id, model.model_id, 1)
            return "selected"
        except (ModelDatabaseError, ProfileNotFoundError):
            return "deleted_first"

    def delete_profile() -> str:
        barrier.wait()
        try:
            profiles.confirm_delete(deletion)
            return "deleted"
        except ConfirmationStaleError:
            return "stale_preview"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(select_again), pool.submit(delete_profile)]
        assert {future.result(timeout=5) for future in results} <= {
            "selected",
            "deleted_first",
            "deleted",
            "stale_preview",
        }
    try:
        profiles.get_profile(delete_target.profile.profile_id)
    except ProfileNotFoundError:
        with pytest.raises(ProfileNotFoundError):
            registry.associations(delete_target.profile.profile_id)
    else:
        surviving = registry.associations(delete_target.profile.profile_id)
        assert surviving[0]["revision"] == 2


def test_registry_diagnostics_never_persist_private_sentinels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sentinel = "M004_PRIVATE_SENTINEL_DO_NOT_LOG"
    monkeypatch.setenv("M004_SECRET_TOKEN", sentinel)
    initialize_foundation()
    paths = resolve_xdg_paths()
    model_directory = tmp_path / f"models-{sentinel}"
    model_directory.mkdir()
    _fixture(model_directory / f"metadata-{sentinel}.gguf", sentinel.encode())
    runtime = tmp_path / f"runtime-{sentinel}"
    runtime.write_text(sentinel)
    sink = InfrastructureDiagnosticSink(
        paths.state,
        DefaultsRegistry.load_packaged().current().foundation_diagnostics,
        SystemClock(),
    )
    registry = ModelRegistryService(
        paths.data / "jarvis.sqlite3",
        diagnostics=sink,
        event_ids=RandomIdGenerator(),
    )
    registry.update_runtime_location((str(model_directory),), str(runtime))
    registry.refresh()

    def fail_with_private_exception(
        _self: ModelRepository,
        _records: object,
        _now: object,
        *,
        complete_scan: bool = True,
    ) -> None:
        del complete_scan
        raise sqlite3.OperationalError(sentinel)

    monkeypatch.setattr(ModelRepository, "reconcile", fail_with_private_exception)
    with pytest.raises(ModelDatabaseError):
        registry.refresh()
    sink.close()
    content = b"".join(path.read_bytes() for path in sink.directory.glob("*.jsonl"))
    assert sentinel.encode() not in content
    events = [json.loads(line) for line in content.splitlines()]
    registry_events = [event for event in events if event["subsystem"] == "models.registry"]
    assert registry_events
    allowed_fields = {
        "models.runtime_location_updated": {
            "directory_count",
            "runtime_path_configured",
            "revision",
        },
        "models.refreshed": {
            "directory_count",
            "record_count",
            "available_count",
            "missing_count",
            "invalid_count",
            "unreadable_count",
            "partial_reason",
            "duration_ms",
        },
        "models.refresh_failed": {"reason"},
    }
    for event in registry_events:
        assert set(event["fields"]) == allowed_fields[event["event_type"]]


def test_concurrent_refreshes_serialize_and_reconcile_one_stable_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initialize_foundation()
    database = resolve_xdg_paths().data / "jarvis.sqlite3"
    models = tmp_path / "refresh-models"
    models.mkdir()
    _fixture(models / "tiny.gguf")
    registry = ModelRegistryService(database)
    registry.update_runtime_location((str(models),), None)
    first_entered = threading.Event()
    release_first = threading.Event()
    second_attempted = threading.Event()
    calls = 0
    calls_lock = threading.Lock()

    def controlled_scan(roots: tuple[Path, ...]) -> ScanResult:
        nonlocal calls
        with calls_lock:
            calls += 1
            call = calls
        if call == 1:
            first_entered.set()
            assert release_first.wait(2)
        return scan_directories(roots)

    monkeypatch.setattr("jarvis.models.service.scan_directories", controlled_scan)

    def second_refresh() -> ScanResult:
        second_attempted.set()
        return registry.refresh()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(registry.refresh)
        assert first_entered.wait(1)
        second = pool.submit(second_refresh)
        assert second_attempted.wait(1)
        assert calls == 1
        release_first.set()
        first_result = first.result(timeout=5)
        second_result = second.result(timeout=5)
    assert calls == 2
    assert len(first_result.records) == len(second_result.records) == 1
    assert first_result.records[0].model_id == second_result.records[0].model_id


def test_concurrent_profile_creation_clones_one_atomic_selected_model_snapshot(
    tmp_path: Path,
) -> None:
    initialize_foundation()
    database = resolve_xdg_paths().data / "jarvis.sqlite3"
    profiles = ProfileService(database)
    jarvis = profiles.ensure_jarvis()
    models = tmp_path / "clone-race-models"
    models.mkdir()
    _fixture(models / "a.gguf", b"A")
    _fixture(models / "b.gguf", b"B")
    registry = ModelRegistryService(database)
    registry.update_runtime_location((str(models),), None)
    discovered = registry.refresh().records
    first, second = discovered
    registry.select(jarvis.profile.profile_id, first.model_id, 0)
    barrier = threading.Barrier(2)

    def create() -> ProfileId:
        barrier.wait()
        return profiles.create_profile(CreateProfile("Concurrent Clone")).profile.profile_id

    def switch() -> None:
        barrier.wait()
        registry.select(jarvis.profile.profile_id, second.model_id, 0)

    with ThreadPoolExecutor(max_workers=2) as pool:
        created = pool.submit(create)
        switched = pool.submit(switch)
        clone_id = created.result(timeout=5)
        switched.result(timeout=5)
    cloned = registry.associations(clone_id)
    assert len(cloned) == 1
    assert cloned[0]["selected"] is True
    assert cloned[0]["model_id"] in {str(first.model_id), str(second.model_id)}
    assert cloned[0]["revision"] == 1
