from __future__ import annotations

import asyncio
import struct
from dataclasses import replace
from pathlib import Path

import pytest

from jarvis.config.defaults import DefaultsRegistry
from jarvis.foundation.bootstrap import DATABASE_FILENAME, initialize_foundation
from jarvis.foundation.clock import SystemClock
from jarvis.llm.fake import FakeLLMProvider
from jarvis.llm.provider import RuntimeHandle
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.models import CreateProfile, Profile
from jarvis.profiles.service import ProfileService
from jarvis.runtimes.errors import (
    RuntimeAlreadyActiveError,
    RuntimeOwnershipError,
    RuntimeStartupError,
)
from jarvis.runtimes.manager import RuntimeManager
from jarvis.runtimes.models import RuntimeState
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


def _setup(tmp_path: Path) -> tuple[RuntimeManager, FakeLLMProvider, Profile, Profile]:
    initialize_foundation()
    paths = resolve_xdg_paths()
    database_path = paths.data / DATABASE_FILENAME
    defaults = DefaultsRegistry.load_packaged()
    models = ModelRegistryService(database_path, SystemClock(), defaults=defaults)
    root = tmp_path / "models"
    root.mkdir()
    model_path = root / "tiny.gguf"
    _fixture(model_path)
    models.update_runtime_location((str(root),), "/usr/bin/gnutrue")
    record = models.refresh().records[0]
    profiles = ProfileService(database_path, defaults=defaults)
    jarvis = profiles.ensure_jarvis().profile
    other = profiles.create_profile(CreateProfile("Other")).profile
    models.select(jarvis.profile_id, record.model_id, 0)
    models.select(other.profile_id, record.model_id, 0)
    provider = FakeLLMProvider()
    manager = RuntimeManager(
        database_path=database_path,
        runtime_root=paths.runtime,
        models=models,
        provider=provider,
        defaults=defaults,
    )
    return manager, provider, jarvis, other


def test_same_gguf_runs_independently_for_two_profiles_and_stop_is_idempotent(
    tmp_path: Path,
) -> None:
    manager, provider, jarvis, other = _setup(tmp_path)

    async def run() -> None:
        first, second = await asyncio.gather(
            manager.start(jarvis.profile_id),
            manager.start(other.profile_id),
        )
        assert first.state is second.state is RuntimeState.READY
        assert first.runtime_id != second.runtime_id
        assert first.model_id == second.model_id
        assert len(provider.starts) == 2
        assert len({item.port for item in provider.starts}) == 2
        stopped = await manager.stop(jarvis.profile_id)
        repeated = await manager.stop(jarvis.profile_id)
        assert stopped == repeated
        assert (await manager.status(other.profile_id)).state is RuntimeState.READY
        await manager.close()

    asyncio.run(run())


def test_same_profile_double_start_linearizes_and_capacity_is_non_destructive(
    tmp_path: Path,
) -> None:
    manager, provider, jarvis, _other = _setup(tmp_path)

    async def run() -> None:
        first = await manager.start(jarvis.profile_id)
        with pytest.raises(RuntimeAlreadyActiveError) as caught:
            await manager.start(jarvis.profile_id)
        assert getattr(caught.value, "code", "") == "runtime.already_active"
        assert (await manager.status(jarvis.profile_id)).runtime_id == first.runtime_id
        assert len(provider.stops) == 0
        await manager.close()

    asyncio.run(run())


def test_endpoint_collision_retries_with_a_new_reserved_port(tmp_path: Path) -> None:
    manager, provider, jarvis, _other = _setup(tmp_path)
    provider.endpoint_failures = 1

    async def run() -> None:
        result = await manager.start(jarvis.profile_id)
        assert result.state is RuntimeState.READY
        assert len(provider.starts) == 2
        assert provider.starts[0].port != provider.starts[1].port
        await manager.close()

    asyncio.run(run())


def test_runtime_crash_transitions_to_error_releases_capacity_and_allows_restart(
    tmp_path: Path,
) -> None:
    manager, provider, jarvis, _other = _setup(tmp_path)

    async def run() -> None:
        started = await manager.start(jarvis.profile_id)
        assert started.runtime_id is not None
        provider.unhealthy.add(started.runtime_id)
        failed = await manager.status(jarvis.profile_id)
        assert failed.state is RuntimeState.ERROR
        assert not manager.has_active(jarvis.profile_id)
        provider.unhealthy.clear()
        restarted = await manager.start(jarvis.profile_id)
        assert restarted.state is RuntimeState.READY
        assert restarted.runtime_id != started.runtime_id
        await manager.close()

    asyncio.run(run())


def test_ambiguous_crash_stop_retains_capacity_lock_and_artifacts_until_explicit_cleanup(
    tmp_path: Path,
) -> None:
    manager, provider, jarvis, _other = _setup(tmp_path)

    async def run() -> None:
        started = await manager.start(jarvis.profile_id)
        assert started.runtime_id is not None
        provider.unhealthy.add(started.runtime_id)
        provider.fail_stop_ownership = True
        failed = await manager.status(jarvis.profile_id)
        assert failed.state is RuntimeState.ERROR
        assert manager.has_active(jarvis.profile_id)
        metadata = (
            resolve_xdg_paths().runtime / "runtimes" / str(jarvis.profile_id) / "runtime.json"
        )
        assert metadata.exists()
        provider.fail_stop_ownership = False
        provider.unhealthy.clear()
        stopped = await manager.stop(jarvis.profile_id)
        assert stopped.state is RuntimeState.STOPPED
        assert not manager.has_active(jarvis.profile_id)
        assert not metadata.exists()

    asyncio.run(run())


def test_runtime_events_and_last_valid_are_metadata_only_and_reset_removes_them(
    tmp_path: Path,
) -> None:
    manager, _provider, jarvis, _other = _setup(tmp_path)

    async def run() -> None:
        await manager.start(jarvis.profile_id)
        await manager.stop(jarvis.profile_id)

    asyncio.run(run())
    from jarvis.profiles.destructive import ConfirmDestructiveOperation, ResetScope
    from jarvis.profiles.service import ProfileConfigService
    from jarvis.storage.database import SQLiteDatabase

    paths = resolve_xdg_paths()
    service = ProfileConfigService(paths.data / DATABASE_FILENAME)
    preview = service.preview_reset(jarvis.profile_id, ResetScope.WHOLE_PROFILE)
    service.confirm_reset(
        ConfirmDestructiveOperation(
            preview.operation_id,
            preview.target,
            preview.profile_id,
            preview.confirmation_token,
        )
    )
    with SQLiteDatabase(paths.data / DATABASE_FILENAME) as database:
        assert (
            database.connection().execute("SELECT COUNT(*) FROM runtime_events").fetchone()[0] == 0
        )
        assert (
            database.connection()
            .execute("SELECT COUNT(*) FROM profile_runtime_last_valid")
            .fetchone()[0]
            == 0
        )


def test_capacity_one_queues_fifo_without_stopping_existing_runtime(tmp_path: Path) -> None:
    manager, provider, jarvis, other = _setup(tmp_path)

    async def run() -> None:
        policy = await manager.update_policy(1, 1)
        assert policy.max_concurrent_runtimes == 1
        first = await manager.start(jarvis.profile_id)
        waiting = asyncio.create_task(manager.start(other.profile_id))
        for _ in range(100):
            if manager.pending_start_count == 1:
                break
            await asyncio.sleep(0)
        assert manager.pending_start_count == 1
        assert len(provider.starts) == 1 and not provider.stops
        await manager.stop(jarvis.profile_id)
        second = await asyncio.wait_for(waiting, 1)
        assert second.state is RuntimeState.READY
        assert second.runtime_id != first.runtime_id
        await manager.close()

    asyncio.run(run())


def test_stop_cancels_same_profile_pending_admission_without_touching_other_runtime(
    tmp_path: Path,
) -> None:
    manager, provider, jarvis, other = _setup(tmp_path)

    async def run() -> None:
        await manager.update_policy(1, 1)
        first = await manager.start(jarvis.profile_id)
        waiting = asyncio.create_task(manager.start(other.profile_id))
        for _ in range(200):
            if manager.pending_start_count == 1:
                break
            await asyncio.sleep(0.005)
        stopped = await asyncio.wait_for(manager.stop(other.profile_id), 1)
        assert stopped.state is RuntimeState.STOPPED
        with pytest.raises(RuntimeStartupError):
            await waiting
        assert manager.pending_start_count == 0
        assert (await manager.status(jarvis.profile_id)).runtime_id == first.runtime_id
        assert not provider.stops
        await manager.close()

    asyncio.run(run())


def test_stop_cancels_an_active_start_and_waits_for_owned_cleanup(tmp_path: Path) -> None:
    manager, provider, jarvis, _other = _setup(tmp_path)
    provider.start_gate.clear()

    async def run() -> None:
        starting = asyncio.create_task(manager.start(jarvis.profile_id))
        await asyncio.wait_for(provider.start_entered.wait(), 1)
        assert provider.starts
        stopped = await asyncio.wait_for(manager.stop(jarvis.profile_id), 1)
        with pytest.raises(asyncio.CancelledError):
            await starting
        assert stopped.state is RuntimeState.STOPPED
        assert not manager.has_active(jarvis.profile_id)
        assert manager.pending_start_count == 0

    asyncio.run(run())


def test_cancelled_stop_completes_cleanup_before_propagating_cancellation(tmp_path: Path) -> None:
    class BlockingStopProvider(FakeLLMProvider):
        def __init__(self) -> None:
            super().__init__()
            self.stop_gate = asyncio.Event()

        async def stop(self, runtime: RuntimeHandle, timeout_seconds: int) -> None:
            await self.stop_gate.wait()
            await super().stop(runtime, timeout_seconds)

    manager, _provider, jarvis, _other = _setup(tmp_path)
    provider = BlockingStopProvider()
    manager._provider = provider

    async def run() -> None:
        await manager.start(jarvis.profile_id)
        stopping = asyncio.create_task(manager.stop(jarvis.profile_id))
        for _ in range(200):
            snapshot = manager._last_snapshots.get(jarvis.profile_id)
            if snapshot is not None and snapshot.state is RuntimeState.STOPPING:
                break
            await asyncio.sleep(0)
        stopping.cancel()
        await asyncio.sleep(0)
        assert not stopping.done()
        provider.stop_gate.set()
        with pytest.raises(asyncio.CancelledError):
            await stopping
        assert not manager.has_active(jarvis.profile_id)
        assert (await manager.status(jarvis.profile_id)).state is RuntimeState.STOPPED

    asyncio.run(run())


def test_profile_lifecycle_guard_prevents_a_start_between_quiesce_and_mutation(
    tmp_path: Path,
) -> None:
    manager, provider, jarvis, _other = _setup(tmp_path)

    async def run() -> None:
        await manager.start(jarvis.profile_id)
        async with manager.profile_lifecycle_guard(jarvis.profile_id):
            assert not manager.has_active(jarvis.profile_id)
            competing = asyncio.create_task(manager.start(jarvis.profile_id))
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(competing), 0.05)
            assert not competing.done()
        restarted = await asyncio.wait_for(competing, 1)
        assert restarted.state is RuntimeState.READY
        assert len(provider.starts) == 2
        await manager.close()

    asyncio.run(run())


def test_ambiguous_startup_ownership_retains_capacity_and_artifacts(tmp_path: Path) -> None:
    manager, provider, jarvis, _other = _setup(tmp_path)
    provider.fail_start_ownership = True

    async def run() -> None:
        with pytest.raises(RuntimeOwnershipError):
            await manager.start(jarvis.profile_id)
        assert manager.has_active(jarvis.profile_id)
        with pytest.raises(RuntimeOwnershipError):
            await manager.stop(jarvis.profile_id)
        artifacts = manager._active[jarvis.profile_id].artifacts
        assert (artifacts.directory / "api-key").exists()
        artifacts.release_lock()

    asyncio.run(run())


def test_capacity_admission_is_fifo_for_multiple_competing_profiles(tmp_path: Path) -> None:
    manager, provider, jarvis, other = _setup(tmp_path)
    paths = resolve_xdg_paths()
    profiles = ProfileService(paths.data / DATABASE_FILENAME)
    third = profiles.create_profile(CreateProfile("Third")).profile
    models = ModelRegistryService(paths.data / DATABASE_FILENAME)

    async def run() -> None:
        await manager.update_policy(1, 1)
        await manager.start(jarvis.profile_id)
        second_task = asyncio.create_task(manager.start(other.profile_id))
        for _ in range(100):
            if manager.pending_start_count == 1:
                break
            await asyncio.sleep(0)
        third_task = asyncio.create_task(manager.start(third.profile_id))
        for _ in range(200):
            if manager.pending_start_count == 2:
                break
            await asyncio.sleep(0.005)
        assert manager.pending_start_count == 2
        await manager.stop(jarvis.profile_id)
        second = await asyncio.wait_for(second_task, 1)
        assert second.model_id == models.list()[0].model_id
        assert not third_task.done()
        await manager.stop(other.profile_id)
        await asyncio.wait_for(third_task, 1)
        assert [item.profile_id for item in provider.starts] == [
            jarvis.profile_id,
            other.profile_id,
            third.profile_id,
        ]
        await manager.close()

    asyncio.run(run())


def test_switch_promotes_only_ready_candidate_and_failure_preserves_selection(
    tmp_path: Path,
) -> None:
    manager, provider, jarvis, _other = _setup(tmp_path)
    paths = resolve_xdg_paths()
    models = ModelRegistryService(paths.data / DATABASE_FILENAME)
    root = tmp_path / "models"
    _fixture(root / "second.gguf", b"Second")
    records = models.refresh().records
    second = next(record for record in records if record.metadata.get("general.name") == "Second")

    async def run() -> None:
        await manager.start(jarvis.profile_id)
        switched = await manager.switch(jarvis.profile_id, second.model_id, 1)
        assert switched.model_id == second.model_id
        selected = [item for item in models.associations(jarvis.profile_id) if item["selected"]]
        assert selected[0]["model_id"] == str(second.model_id)
        await manager.stop(jarvis.profile_id)

        old = next(record for record in records if record.model_id != second.model_id)
        models.ensure_runtime_association(jarvis.profile_id, old.model_id)
        provider.fail_start = True
        with pytest.raises(RuntimeStartupError):
            await manager.switch(jarvis.profile_id, old.model_id, 1)
        selected_after = [
            item for item in models.associations(jarvis.profile_id) if item["selected"]
        ]
        assert selected_after[0]["model_id"] == str(second.model_id)
        assert (await manager.status(jarvis.profile_id)).state is RuntimeState.ERROR
        await manager.close()

    asyncio.run(run())


def test_model_is_revalidated_immediately_before_spawn_and_never_modified(
    tmp_path: Path,
) -> None:
    manager, provider, jarvis, _other = _setup(tmp_path)
    model = tmp_path / "models" / "tiny.gguf"
    original = model.read_bytes()
    replacement = model.with_suffix(".replacement")
    _fixture(replacement, b"Replacement")
    replacement.replace(model)
    changed = model.read_bytes()

    async def run() -> None:
        with pytest.raises(RuntimeStartupError):
            await manager.start(jarvis.profile_id)
        assert provider.starts == []

    asyncio.run(run())
    assert changed != original
    assert model.read_bytes() == changed


@pytest.mark.parametrize("blocked_phase", ["spawn", "health"])
def test_startup_and_health_deadlines_cleanup_without_leaking_capacity(
    tmp_path: Path, blocked_phase: str
) -> None:
    manager, provider, jarvis, _other = _setup(tmp_path)
    models = ModelRegistryService(resolve_xdg_paths().data / DATABASE_FILENAME)
    association = models.runtime_association(jarvis.profile_id)
    models.update_config(
        jarvis.profile_id,
        association[0].model_id,
        replace(association[1], startup_timeout_seconds=1),
        association[2],
    )
    if blocked_phase == "spawn":
        provider.start_gate.clear()
    else:
        provider.health_gate.clear()

    async def run() -> None:
        with pytest.raises(RuntimeStartupError):
            await asyncio.wait_for(manager.start(jarvis.profile_id), 2)
        assert not manager.has_active(jarvis.profile_id)
        assert manager.pending_start_count == 0
        if blocked_phase == "health":
            assert len(provider.stops) == 1

    asyncio.run(run())
