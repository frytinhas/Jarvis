"""Core-owned, per-profile runtime state machine and capacity coordinator."""

from __future__ import annotations

import asyncio
import os
import secrets
import signal
import sqlite3
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from jarvis.config.defaults import DefaultsRegistry, RuntimeManagerDefaults
from jarvis.diagnostics.events import InfrastructureEvent, Severity
from jarvis.diagnostics.sink import InfrastructureDiagnosticSink
from jarvis.foundation.clock import Clock, SystemClock, format_utc
from jarvis.foundation.identifiers import IdGenerator, RandomIdGenerator
from jarvis.llm.provider import (
    ExecutableIdentity,
    LLMProvider,
    ProcessEvidence,
    ProviderChatRequest,
    ProviderStreamEvent,
    RuntimeHandle,
    RuntimeSpecification,
)
from jarvis.models.errors import ModelError
from jarvis.models.models import ModelId, ModelRuntimeConfig
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.models import ProfileId
from jarvis.runtimes.artifacts import (
    RuntimeArtifacts,
    allocate_loopback_port,
    executable_identity,
    owned_listener,
    process_matches,
    process_owns_file,
)
from jarvis.runtimes.errors import (
    RuntimeAlreadyActiveError,
    RuntimeCapacityError,
    RuntimeDatabaseError,
    RuntimeEndpointError,
    RuntimeManagerError,
    RuntimeNotConfiguredError,
    RuntimeOwnershipError,
    RuntimeStartupError,
)
from jarvis.runtimes.models import (
    RuntimeEventKind,
    RuntimeHealthClass,
    RuntimeId,
    RuntimePolicy,
    RuntimeSnapshot,
    RuntimeState,
    is_legal_transition,
)
from jarvis.runtimes.repository import RuntimeRepository
from jarvis.storage.database import SQLiteDatabase

StateCallback = Callable[[RuntimeSnapshot], Awaitable[None]]

_SAFE_STARTUP_REASONS = frozenset(
    {
        "model_load_failed",
        "argument_incompatible",
        "resource_exhausted",
        "startup_timeout",
        "process_exit",
    }
)


def _safe_startup_reason(reason: str) -> str:
    if reason in _SAFE_STARTUP_REASONS:
        return reason
    if "timeout" in reason:
        return "startup_timeout"
    return "process_exit"


class GenerationCoordinator(Protocol):
    async def quiesce(self, profile_id: ProfileId, *, cancel: bool) -> str: ...

    async def hold(self, profile_id: ProfileId, *, cancel: bool) -> _GenerationHold: ...


class _GenerationHold(Protocol):
    async def __aenter__(self) -> str: ...

    async def __aexit__(self, *_exc: object) -> None: ...


class _IdleGenerationHold:
    async def __aenter__(self) -> str:
        return "idle"

    async def __aexit__(self, *_exc: object) -> None:
        return None


class IdleGenerationCoordinator:
    async def quiesce(self, profile_id: ProfileId, *, cancel: bool) -> str:
        del profile_id, cancel
        return "idle"

    async def hold(self, profile_id: ProfileId, *, cancel: bool) -> _GenerationHold:
        del profile_id, cancel
        return _IdleGenerationHold()


@dataclass(slots=True)
class _Admission:
    ticket: object
    profile_id: ProfileId
    cancelled: bool = False


@dataclass(slots=True)
class _ActiveRuntime:
    handle: RuntimeHandle | None
    artifacts: RuntimeArtifacts
    config: ModelRuntimeConfig
    profile_model_revision: int
    snapshot: RuntimeSnapshot
    monitor_task: asyncio.Task[None] | None = None
    allocated_port: int | None = None
    ownership_ambiguous: bool = False


class RuntimeManager:
    def __init__(
        self,
        *,
        database_path: Path,
        runtime_root: Path,
        models: ModelRegistryService,
        provider: LLMProvider,
        defaults: DefaultsRegistry | None = None,
        clock: Clock | None = None,
        event_ids: IdGenerator | None = None,
        generations: GenerationCoordinator | None = None,
        diagnostics: InfrastructureDiagnosticSink | None = None,
    ) -> None:
        self._database_path = database_path
        self._runtime_root = runtime_root
        self._models = models
        self._provider = provider
        self._defaults = DefaultsRegistry.load_packaged() if defaults is None else defaults
        self._clock = SystemClock() if clock is None else clock
        self._event_ids = RandomIdGenerator() if event_ids is None else event_ids
        self._generations = IdleGenerationCoordinator() if generations is None else generations
        self._diagnostics = diagnostics
        self._profile_locks: dict[ProfileId, asyncio.Lock] = {}
        self._registry_lock = asyncio.Lock()
        self._capacity_changed = asyncio.Condition(self._registry_lock)
        self._pending: deque[_Admission] = deque()
        self._active: dict[ProfileId, _ActiveRuntime] = {}
        self._start_tasks: dict[ProfileId, asyncio.Task[object]] = {}
        self._reservations = 0
        self._last_snapshots: dict[ProfileId, RuntimeSnapshot] = {}
        self._allocated_ports: set[int] = set()
        self._closed = False

    def _profile_lock(self, profile_id: ProfileId) -> asyncio.Lock:
        return self._profile_locks.setdefault(profile_id, asyncio.Lock())

    def _runtime_defaults(self) -> RuntimeManagerDefaults:
        return self._defaults.current().runtime_manager

    def policy(self) -> RuntimePolicy:
        defaults = self._runtime_defaults()
        try:
            with (
                SQLiteDatabase(self._database_path) as database,
                database.transaction(immediate=True),
            ):
                return RuntimeRepository(database.connection()).policy(
                    defaults.max_concurrent_runtimes, self._clock.now()
                )
        except sqlite3.Error as error:
            raise RuntimeDatabaseError() from error

    async def update_policy(self, capacity: int, expected_revision: int) -> RuntimePolicy:
        if not 1 <= capacity <= 16:
            raise RuntimeManagerError("runtime.invalid_policy", "capacity")
        try:
            with (
                SQLiteDatabase(self._database_path) as database,
                database.transaction(immediate=True),
            ):
                repository = RuntimeRepository(database.connection())
                repository.policy(
                    self._runtime_defaults().max_concurrent_runtimes, self._clock.now()
                )
                result = repository.update_policy(capacity, expected_revision, self._clock.now())
        except sqlite3.Error as error:
            raise RuntimeDatabaseError() from error
        async with self._capacity_changed:
            self._capacity_changed.notify_all()
        return result

    async def _admit(self, profile_id: ProfileId) -> None:
        admission = _Admission(object(), profile_id)
        async with self._capacity_changed:
            if len(self._pending) >= self._runtime_defaults().max_pending_starts:
                raise RuntimeCapacityError()
            self._pending.append(admission)
            try:
                while True:
                    if admission.cancelled:
                        raise RuntimeStartupError("admission_cancelled")
                    capacity = await asyncio.to_thread(self.policy)
                    if (
                        self._pending[0] is admission
                        and len(self._active) + self._reservations
                        < capacity.max_concurrent_runtimes
                    ):
                        self._pending.popleft()
                        self._reservations += 1
                        return
                    await self._capacity_changed.wait()
            except BaseException:
                with suppress(ValueError):
                    self._pending.remove(admission)
                self._capacity_changed.notify_all()
                raise

    async def _cancel_pending_admission(self, profile_id: ProfileId) -> None:
        async with self._capacity_changed:
            for admission in tuple(self._pending):
                if admission.profile_id == profile_id:
                    admission.cancelled = True
            self._capacity_changed.notify_all()

    async def start(
        self, profile_id: ProfileId, *, on_state: StateCallback | None = None
    ) -> RuntimeSnapshot:
        task = asyncio.current_task()
        assert task is not None
        async with self._profile_lock(profile_id):
            self._start_tasks[profile_id] = task
            try:
                return await self._start_locked(
                    profile_id, None, on_state=on_state, persist_ready=True
                )
            finally:
                if self._start_tasks.get(profile_id) is task:
                    self._start_tasks.pop(profile_id, None)

    async def _start_locked(
        self,
        profile_id: ProfileId,
        model_id: ModelId | None,
        *,
        on_state: StateCallback | None,
        persist_ready: bool,
    ) -> RuntimeSnapshot:
        if self._closed:
            raise RuntimeStartupError("manager_closed")
        async with self._registry_lock:
            if profile_id in self._active:
                raise RuntimeAlreadyActiveError()
        await self._admit(profile_id)
        runtime_id = RuntimeId.new()
        artifacts: RuntimeArtifacts | None = None
        model_fd: int | None = None
        api_key_fd: int | None = None
        admitted = True
        resolved_model_id: ModelId | None = model_id
        try:
            try:
                record, config, revision = await asyncio.to_thread(
                    self._models.runtime_association, profile_id, model_id
                )
                resolved_model_id = record.model_id
            except ModelError as error:
                raise RuntimeNotConfiguredError(
                    str(error.safe_details.get("reason", "model"))
                ) from error
            location = await asyncio.to_thread(self._models.runtime_location)
            if location.llama_server_path is None:
                raise RuntimeNotConfiguredError("llama_server_path")
            executable = await asyncio.to_thread(executable_identity, location.llama_server_path)
            model_fd = await asyncio.to_thread(self._models.open_revalidated_model, record)
            artifacts = await asyncio.to_thread(
                RuntimeArtifacts.acquire, self._runtime_root, str(profile_id)
            )
            api_key = secrets.token_urlsafe(48)
            api_key_path = await asyncio.to_thread(artifacts.write_secret, api_key)
            starting = RuntimeSnapshot(
                runtime_id,
                record.model_id,
                RuntimeState.STARTING,
                RuntimeHealthClass.UNKNOWN,
                started_at_utc=format_utc(self._clock.now()),
            )
            placeholder = _ActiveRuntime(
                # Replaced immediately after provider.start; never observed outside the lock.
                handle=None,
                artifacts=artifacts,
                config=config,
                profile_model_revision=revision,
                snapshot=starting,
                monitor_task=None,
                allocated_port=None,
            )
            async with self._capacity_changed:
                self._active[profile_id] = placeholder
                self._reservations -= 1
                admitted = False
                self._capacity_changed.notify_all()
            await self._transition(profile_id, starting, RuntimeEventKind.START_REQUESTED, on_state)
            last_error = "endpoint_unavailable"
            for _attempt in range(self._runtime_defaults().endpoint_allocation_attempts):
                if model_fd is None:
                    model_fd = await asyncio.to_thread(self._models.open_revalidated_model, record)
                port = await self._allocate_endpoint()
                placeholder.allocated_port = port
                api_key_fd = await asyncio.to_thread(artifacts.open_secret_descriptor)
                specification = RuntimeSpecification(
                    runtime_id,
                    profile_id,
                    record.model_id,
                    model_fd,
                    location.llama_server_path,
                    executable,
                    artifacts.directory,
                    "127.0.0.1",
                    port,
                    api_key_path,
                    api_key_fd,
                    api_key,
                    config,
                    self._runtime_defaults().stream_capture_bytes,
                )
                try:
                    handle = await asyncio.wait_for(
                        self._provider.start(specification), config.startup_timeout_seconds
                    )
                    os.close(api_key_fd)
                    api_key_fd = None
                    os.close(model_fd)
                    model_fd = None
                    placeholder.handle = handle
                    await asyncio.to_thread(
                        artifacts.write_metadata,
                        {
                            "runtime_id": str(runtime_id),
                            "profile_id": str(profile_id),
                            "model_id": str(record.model_id),
                            "boot_id": handle.evidence.boot_id,
                            "pid": handle.evidence.pid,
                            "start_ticks": handle.evidence.start_ticks,
                            "process_group_id": handle.evidence.process_group_id,
                            "executable_device": handle.evidence.executable.device,
                            "executable_inode": handle.evidence.executable.inode,
                            "model_device": record.device,
                            "model_inode": record.inode,
                            "endpoint_host": "127.0.0.1",
                            "endpoint_port": port,
                            "state": RuntimeState.STARTING.value,
                        },
                    )
                    readiness = await self._wait_ready(handle, config)
                    if readiness == "ready":
                        # A configured zero is not a usable prompt budget.  The server has
                        # completed authenticated readiness, so it is now safe to obtain its
                        # model-derived value without retaining any other /props data.
                        effective_context = (
                            config.context_window
                            if config.context_window > 0
                            else await self._provider.effective_context(
                                handle, config.network_timeout_seconds
                            )
                        )
                        if (
                            type(effective_context) is not int
                            or not 1 <= effective_context <= 1_000_000
                        ):
                            raise RuntimeStartupError("effective_context_invalid")
                        now = self._clock.now()
                        snapshot = RuntimeSnapshot(
                            runtime_id,
                            record.model_id,
                            RuntimeState.READY,
                            RuntimeHealthClass.HEALTHY,
                            starting.started_at_utc,
                            format_utc(now),
                            effective_context_window=effective_context,
                        )
                        placeholder.snapshot = snapshot
                        # Raw startup stderr exists only while it can classify a failed start.
                        # Stop the capture before exposing the ready runtime to chat.
                        handle.startup_stderr_capture.clear()
                        handle.startup_stderr_tail.clear()
                        if persist_ready:
                            await self._persist_ready(
                                profile_id, record.model_id, runtime_id, revision, now
                            )
                        await self._transition(
                            profile_id, snapshot, RuntimeEventKind.READY, on_state
                        )
                        placeholder.monitor_task = asyncio.create_task(
                            self._monitor(profile_id, runtime_id)
                        )
                        await asyncio.to_thread(artifacts.remove_secret_if_owned)
                        return snapshot
                    last_error = (
                        "endpoint_process_exit"
                        if readiness == "error"
                        else "startup_health_timeout"
                    )
                    if readiness == "error":
                        last_error = await self._provider.startup_failure_reason(
                            handle, "process_exit"
                        )
                    await self._provider.stop(handle, config.shutdown_timeout_seconds)
                    placeholder.handle = None
                    if readiness == "error":
                        await self._release_endpoint(port)
                        placeholder.allocated_port = None
                        continue
                except TimeoutError:
                    last_error = "startup_timeout"
                    if placeholder.handle is not None:
                        await self._provider.stop(
                            placeholder.handle, config.shutdown_timeout_seconds
                        )
                        placeholder.handle = None
                except RuntimeEndpointError as error:
                    last_error = str(error.safe_details.get("reason", "endpoint_unavailable"))
                    await self._release_endpoint(port)
                    placeholder.allocated_port = None
                    continue
                finally:
                    if api_key_fd is not None:
                        os.close(api_key_fd)
                        api_key_fd = None
                break
            raise RuntimeStartupError(_safe_startup_reason(last_error))
        except BaseException as error:
            ownership_error: RuntimeOwnershipError | None = (
                error if isinstance(error, RuntimeOwnershipError) else None
            )
            if artifacts is not None:
                active_for_cleanup = self._active.get(profile_id)
                if active_for_cleanup is not None and active_for_cleanup.handle is not None:
                    try:
                        await self._provider.stop(
                            active_for_cleanup.handle,
                            active_for_cleanup.config.shutdown_timeout_seconds,
                        )
                    except RuntimeOwnershipError as caught:
                        ownership_error = caught
                    except BaseException:
                        pass
                if ownership_error is None:
                    await asyncio.to_thread(artifacts.cleanup)
            async with self._capacity_changed:
                if ownership_error is None:
                    active_for_release = self._active.pop(profile_id, None)
                    if (
                        active_for_release is not None
                        and active_for_release.allocated_port is not None
                    ):
                        self._allocated_ports.discard(active_for_release.allocated_port)
                if admitted:
                    self._reservations -= 1
                    admitted = False
                self._capacity_changed.notify_all()
            if ownership_error is not None:
                ambiguous = self._active.get(profile_id)
                if ambiguous is not None:
                    ambiguous.ownership_ambiguous = True
            if model_fd is not None:
                os.close(model_fd)
            if api_key_fd is not None:
                os.close(api_key_fd)
            reported = ownership_error or error
            error_snapshot = RuntimeSnapshot(
                runtime_id,
                resolved_model_id,
                RuntimeState.ERROR,
                RuntimeHealthClass.UNHEALTHY,
                stopped_at_utc=format_utc(self._clock.now()),
            )
            if resolved_model_id is not None:
                with suppress(BaseException):
                    await self._transition(
                        profile_id,
                        error_snapshot,
                        RuntimeEventKind.ERROR,
                        on_state,
                        reason_class=(
                            str(reported.safe_details.get("reason", "runtime_failure"))
                            if isinstance(reported, RuntimeManagerError)
                            else "startup_failure"
                        ),
                    )
            else:
                self._last_snapshots[profile_id] = error_snapshot
            if isinstance(error, asyncio.CancelledError):
                raise
            if isinstance(reported, RuntimeStartupError):
                raise RuntimeStartupError(
                    _safe_startup_reason(str(reported.safe_details.get("reason", "process_exit")))
                ) from None
            if isinstance(reported, RuntimeManagerError):
                raise reported from None
            raise RuntimeStartupError("startup_failed") from reported

    async def _wait_ready(self, handle: RuntimeHandle, config: ModelRuntimeConfig) -> str:
        deadline = asyncio.get_running_loop().time() + config.startup_timeout_seconds
        while (remaining := deadline - asyncio.get_running_loop().time()) > 0:
            try:
                health = await asyncio.wait_for(
                    self._provider.health(handle, config.network_timeout_seconds),
                    timeout=remaining,
                )
            except TimeoutError:
                return "timeout"
            if health.state is RuntimeState.READY and health.health is RuntimeHealthClass.HEALTHY:
                return "ready"
            if health.state is RuntimeState.ERROR:
                return "error"
            await asyncio.sleep(0.02)
        return "timeout"

    async def status(self, profile_id: ProfileId) -> RuntimeSnapshot:
        async with self._profile_lock(profile_id):
            active = self._active.get(profile_id)
            if active is None:
                return self._last_snapshots.get(
                    profile_id,
                    RuntimeSnapshot(None, None, RuntimeState.STOPPED, RuntimeHealthClass.STOPPED),
                )
            if active.handle is None:
                return active.snapshot
            health = await self._provider.health(
                active.handle, active.config.network_timeout_seconds
            )
            if health.state is RuntimeState.ERROR:
                return await self._fail_active_locked(
                    profile_id, active, health.reason_class or "health_failure"
                )
            return active.snapshot

    async def context_window(self, profile_id: ProfileId, configured: int) -> int:
        """Return an explicit budget, or start and read the ready Auto runtime budget."""

        if configured > 0:
            return configured
        if configured != 0:
            raise RuntimeStartupError("effective_context_invalid")
        with suppress(RuntimeAlreadyActiveError):
            await self.start(profile_id)
        async with self._profile_lock(profile_id):
            active = self._active.get(profile_id)
            if (
                active is None
                or active.snapshot.state not in {RuntimeState.READY, RuntimeState.BUSY}
                or type(active.snapshot.effective_context_window) is not int
                or active.snapshot.effective_context_window <= 0
            ):
                raise RuntimeStartupError("effective_context_unavailable")
            return active.snapshot.effective_context_window

    async def stop(
        self, profile_id: ProfileId, *, on_state: StateCallback | None = None
    ) -> RuntimeSnapshot:
        await self._cancel_pending_admission(profile_id)
        self._cancel_start(profile_id)
        async with (
            await self._generations.hold(profile_id, cancel=False),
            self._profile_lock(profile_id),
        ):
            return await self._stop_locked(profile_id, on_state=on_state)

    def _cancel_start(self, profile_id: ProfileId) -> None:
        # Pending admissions are cancelled through their ticket.  Cancelling
        # their task directly would change the established typed admission
        # failure into an unstructured CancelledError.
        if profile_id not in self._active:
            return
        task = self._start_tasks.get(profile_id)
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()

    async def _stop_locked(
        self, profile_id: ProfileId, *, on_state: StateCallback | None
    ) -> RuntimeSnapshot:
        """Finish owned cleanup before propagating request cancellation.

        An IPC cancellation may stop waiting for a result, but it must never
        abandon a Core-owned process midway through STOPPING.
        """

        task = asyncio.create_task(self._stop_locked_impl(profile_id, on_state=on_state))
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(task)
                break
            except asyncio.CancelledError:
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError
        return result

    async def _stop_locked_impl(
        self, profile_id: ProfileId, *, on_state: StateCallback | None
    ) -> RuntimeSnapshot:
        active = self._active.get(profile_id)
        if active is None:
            snapshot = self._last_snapshots.get(
                profile_id,
                RuntimeSnapshot(None, None, RuntimeState.STOPPED, RuntimeHealthClass.STOPPED),
            )
            if snapshot.state is not RuntimeState.STOPPED:
                snapshot = RuntimeSnapshot(
                    snapshot.runtime_id,
                    snapshot.model_id,
                    RuntimeState.STOPPED,
                    RuntimeHealthClass.STOPPED,
                    snapshot.started_at_utc,
                    snapshot.ready_at_utc,
                    snapshot.stopped_at_utc or format_utc(self._clock.now()),
                )
            return snapshot
        if active.ownership_ambiguous:
            raise RuntimeOwnershipError("stop_identity_ambiguous")
        stopping = active.snapshot
        if active.snapshot.state is not RuntimeState.STOPPING:
            stopping = RuntimeSnapshot(
                active.snapshot.runtime_id,
                active.snapshot.model_id,
                RuntimeState.STOPPING,
                RuntimeHealthClass.UNKNOWN,
                active.snapshot.started_at_utc,
                active.snapshot.ready_at_utc,
            )
            await self._transition(profile_id, stopping, RuntimeEventKind.STOP_REQUESTED, on_state)
        if active.handle is not None:
            await self._provider.stop(active.handle, active.config.shutdown_timeout_seconds)
            self._diagnose_output(active.handle)
        if active.monitor_task is not None and active.monitor_task is not asyncio.current_task():
            active.monitor_task.cancel()
            await asyncio.gather(active.monitor_task, return_exceptions=True)
        await asyncio.to_thread(active.artifacts.cleanup)
        stopped = RuntimeSnapshot(
            stopping.runtime_id,
            stopping.model_id,
            RuntimeState.STOPPED,
            RuntimeHealthClass.STOPPED,
            stopping.started_at_utc,
            stopping.ready_at_utc,
            format_utc(self._clock.now()),
        )
        async with self._capacity_changed:
            self._active.pop(profile_id, None)
            if active.allocated_port is not None:
                self._allocated_ports.discard(active.allocated_port)
            self._capacity_changed.notify_all()
        await self._transition(profile_id, stopped, RuntimeEventKind.STOPPED, on_state)
        return stopped

    async def switch(
        self,
        profile_id: ProfileId,
        model_id: ModelId,
        expected_revision: int,
        *,
        on_state: StateCallback | None = None,
    ) -> RuntimeSnapshot:
        await self._cancel_pending_admission(profile_id)
        self._cancel_start(profile_id)
        async with (
            await self._generations.hold(profile_id, cancel=False),
            self._profile_lock(profile_id),
        ):
            revision = await asyncio.to_thread(
                self._models.ensure_runtime_association, profile_id, model_id
            )
            if revision != expected_revision:
                from jarvis.models.errors import ConcurrentModelModificationError

                raise ConcurrentModelModificationError("profile_model_revision_mismatch")
            prior = self._last_snapshots.get(profile_id)
            if prior is not None and prior.runtime_id is not None and prior.model_id is not None:
                await asyncio.to_thread(
                    self._record_event,
                    profile_id,
                    prior,
                    RuntimeEventKind.SWITCH_REQUESTED,
                    None,
                )
            await self._stop_locked(profile_id, on_state=on_state)
            candidate = await self._start_locked(
                profile_id, model_id, on_state=on_state, persist_ready=False
            )
            try:
                promoted = await asyncio.to_thread(
                    self._models.promote_runtime_selection,
                    profile_id,
                    model_id,
                    expected_revision,
                )
                active = self._active[profile_id]
                active.profile_model_revision = promoted
                await self._persist_ready(
                    profile_id,
                    model_id,
                    candidate.runtime_id,
                    promoted,
                    self._clock.now(),
                )
                return candidate
            except BaseException:
                await self._stop_locked(profile_id, on_state=on_state)
                raise

    async def quiesce_profile(self, profile_id: ProfileId, *, cancel: bool = True) -> str:
        async with self.profile_lifecycle_guard(profile_id, cancel=cancel) as outcome:
            return outcome

    @asynccontextmanager
    async def profile_lifecycle_guard(
        self, profile_id: ProfileId, *, cancel: bool = True
    ) -> AsyncIterator[str]:
        """Keep a profile quiescent until its destructive DB operation finishes."""

        await self._cancel_pending_admission(profile_id)
        self._cancel_start(profile_id)
        async with (
            await self._generations.hold(profile_id, cancel=cancel) as outcome,
            self._profile_lock(profile_id),
        ):
            stopped = await self._stop_locked(profile_id, on_state=None)
            if stopped.runtime_id is not None and stopped.model_id is not None:
                await asyncio.to_thread(
                    self._record_event,
                    profile_id,
                    stopped,
                    RuntimeEventKind.QUIESCED,
                    outcome,
                )
            yield outcome

    async def close(self) -> None:
        self._closed = True
        profile_ids = (
            set(self._active)
            | set(self._start_tasks)
            | {admission.profile_id for admission in self._pending}
        )
        for profile_id in profile_ids:
            with suppress(BaseException):
                await self.stop(profile_id)

    async def stream_chat(
        self, profile_id: ProfileId, request: ProviderChatRequest
    ) -> AsyncIterator[ProviderStreamEvent]:
        """Auto-start, mark BUSY, and restore READY around one coordinated generation."""

        async with self._profile_lock(profile_id):
            active = self._active.get(profile_id)
        if active is None:
            with suppress(RuntimeAlreadyActiveError):
                await self.start(profile_id)
        async with self._profile_lock(profile_id):
            active = self._active.get(profile_id)
            if active is None or active.handle is None:
                raise RuntimeStartupError("runtime_not_ready")
            if active.snapshot.state is not RuntimeState.READY:
                raise RuntimeStartupError("runtime_not_ready")
            runtime_id = active.snapshot.runtime_id
            busy = RuntimeSnapshot(
                active.snapshot.runtime_id,
                active.snapshot.model_id,
                RuntimeState.BUSY,
                RuntimeHealthClass.HEALTHY,
                active.snapshot.started_at_utc,
                active.snapshot.ready_at_utc,
                effective_context_window=active.snapshot.effective_context_window,
            )
            await self._transition(profile_id, busy, RuntimeEventKind.BUSY, None)
            handle = active.handle
        try:
            async for event in self._provider.chat(handle, request):
                yield event
        finally:
            async with self._profile_lock(profile_id):
                current = self._active.get(profile_id)
                if (
                    current is not None
                    and current.snapshot.runtime_id == runtime_id
                    and current.handle is not None
                    and current.snapshot.state is RuntimeState.BUSY
                ):
                    health = await self._provider.health(
                        current.handle, current.config.network_timeout_seconds
                    )
                    if health.state is RuntimeState.ERROR:
                        await self._fail_active_locked(
                            profile_id,
                            current,
                            health.reason_class or "generation_runtime_failure",
                        )
                    else:
                        ready = RuntimeSnapshot(
                            current.snapshot.runtime_id,
                            current.snapshot.model_id,
                            RuntimeState.READY,
                            RuntimeHealthClass.HEALTHY,
                            current.snapshot.started_at_utc,
                            current.snapshot.ready_at_utc,
                            effective_context_window=current.snapshot.effective_context_window,
                        )
                        await self._transition(profile_id, ready, RuntimeEventKind.READY, None)

    async def _monitor(self, profile_id: ProfileId, runtime_id: RuntimeId) -> None:
        try:
            while True:
                await asyncio.sleep(1.0)
                async with self._profile_lock(profile_id):
                    active = self._active.get(profile_id)
                    if (
                        active is None
                        or active.snapshot.runtime_id != runtime_id
                        or active.handle is None
                    ):
                        return
                    health = await self._provider.health(
                        active.handle, active.config.network_timeout_seconds
                    )
                    if health.state is not RuntimeState.ERROR:
                        continue
                    await self._fail_active_locked(
                        profile_id, active, health.reason_class or "health_failure"
                    )
                    return
        except asyncio.CancelledError:
            raise

    async def _fail_active_locked(
        self, profile_id: ProfileId, active: _ActiveRuntime, reason: str
    ) -> RuntimeSnapshot:
        assert active.snapshot.runtime_id is not None and active.handle is not None
        error_snapshot = RuntimeSnapshot(
            active.snapshot.runtime_id,
            active.snapshot.model_id,
            RuntimeState.ERROR,
            RuntimeHealthClass.UNHEALTHY,
            active.snapshot.started_at_utc,
            active.snapshot.ready_at_utc,
            format_utc(self._clock.now()),
        )
        if active.snapshot.state is not RuntimeState.ERROR:
            await self._transition(
                profile_id,
                error_snapshot,
                RuntimeEventKind.ERROR,
                None,
                reason_class=reason,
            )
        try:
            await self._provider.stop(active.handle, active.config.shutdown_timeout_seconds)
        except RuntimeOwnershipError:
            # Preserve the capacity reservation, lock, and evidence for explicit recovery.
            return error_snapshot
        self._diagnose_output(active.handle)
        await asyncio.to_thread(active.artifacts.cleanup)
        if active.monitor_task is not None and active.monitor_task is not asyncio.current_task():
            active.monitor_task.cancel()
            await asyncio.gather(active.monitor_task, return_exceptions=True)
        async with self._capacity_changed:
            self._active.pop(profile_id, None)
            if active.allocated_port is not None:
                self._allocated_ports.discard(active.allocated_port)
            self._capacity_changed.notify_all()
        return error_snapshot

    def _diagnose_output(self, handle: RuntimeHandle) -> None:
        if self._diagnostics is None:
            return
        for task in (handle.stdout_task, handle.stderr_task):
            if not task.done() or task.cancelled():
                continue
            with suppress(BaseException):
                summary = task.result()
                self._diagnostics.emit(
                    InfrastructureEvent(
                        self._event_ids.new_event_id(),
                        self._clock.now(),
                        "runtime.server_output",
                        "runtimes.manager",
                        Severity.INFO,
                        {
                            "runtime_id": str(handle.runtime_id),
                            "stream": summary.stream,
                            "byte_count": summary.byte_count,
                            "dropped_bytes": summary.dropped_bytes,
                        },
                    )
                )

    async def recover_stale(self) -> None:
        """Recover only conclusively identified orphaned runtimes from a previous Core."""

        def profile_ids() -> tuple[ProfileId, ...]:
            with (
                SQLiteDatabase(self._database_path) as database,
                database.transaction(immediate=False),
            ):
                rows = database.connection().execute("SELECT profile_id FROM profiles").fetchall()
                return tuple(ProfileId.parse(str(row[0])) for row in rows)

        for profile_id in await asyncio.to_thread(profile_ids):
            directory = self._runtime_root / "runtimes" / str(profile_id)
            if not directory.exists():
                continue
            artifacts = await asyncio.to_thread(
                RuntimeArtifacts.acquire, self._runtime_root, str(profile_id)
            )
            try:
                metadata = await asyncio.to_thread(artifacts.read_metadata)
                if metadata is None:
                    unexpected = {
                        name
                        for name in os.listdir(artifacts.directory_fd)
                        if name != "runtime.lock"
                    }
                    if unexpected:
                        raise RuntimeManagerError(
                            "runtime.artifact_invalid", "orphan_artifact_without_metadata"
                        )
                    await asyncio.to_thread(artifacts.cleanup)
                    continue
                expected = {
                    "runtime_id",
                    "profile_id",
                    "model_id",
                    "boot_id",
                    "pid",
                    "start_ticks",
                    "process_group_id",
                    "executable_device",
                    "executable_inode",
                    "model_device",
                    "model_inode",
                    "endpoint_host",
                    "endpoint_port",
                    "state",
                }
                if set(metadata) != expected or metadata["profile_id"] != str(profile_id):
                    raise RuntimeManagerError("runtime.artifact_invalid", "metadata_fields")
                try:
                    RuntimeId.parse(str(metadata["runtime_id"]))
                    ModelId.parse(str(metadata["model_id"]))
                    RuntimeState(str(metadata["state"]))
                except (TypeError, ValueError) as error:
                    raise RuntimeManagerError(
                        "runtime.artifact_invalid", "metadata_identity"
                    ) from error
                if metadata["endpoint_host"] != "127.0.0.1":
                    raise RuntimeManagerError("runtime.artifact_invalid", "non_loopback_endpoint")
                boot = metadata["boot_id"]
                if not isinstance(boot, str) or len(boot) != 36:
                    raise RuntimeManagerError("runtime.artifact_invalid", "boot_id")
                evidence = ProcessEvidence(
                    _metadata_int(metadata, "pid"),
                    _metadata_int(metadata, "process_group_id"),
                    boot,
                    _metadata_int(metadata, "start_ticks"),
                    ExecutableIdentity(
                        _metadata_int(metadata, "executable_device"),
                        _metadata_int(metadata, "executable_inode"),
                    ),
                )
                pid_exists = Path(f"/proc/{evidence.pid}").exists()
                if not pid_exists:
                    await asyncio.to_thread(artifacts.cleanup)
                    continue
                port = _metadata_int(metadata, "endpoint_port")
                if port > 65_535:
                    raise RuntimeManagerError("runtime.artifact_invalid", "endpoint_port")
                if not (
                    process_matches(evidence)
                    and evidence.process_group_id == evidence.pid
                    and owned_listener(evidence.pid, port)
                    and process_owns_file(
                        evidence.pid,
                        _metadata_int(metadata, "model_device"),
                        _metadata_int(metadata, "model_inode"),
                    )
                ):
                    raise RuntimeManagerError("runtime.ownership_ambiguous", "stale_evidence")
                os.killpg(evidence.process_group_id, signal.SIGTERM)
                deadline = asyncio.get_running_loop().time() + 5.0
                while process_matches(evidence) and asyncio.get_running_loop().time() < deadline:
                    await asyncio.sleep(0.02)
                if process_matches(evidence):
                    os.killpg(evidence.process_group_id, signal.SIGKILL)
                    kill_deadline = asyncio.get_running_loop().time() + 1.0
                    while (
                        process_matches(evidence)
                        and asyncio.get_running_loop().time() < kill_deadline
                    ):
                        await asyncio.sleep(0.02)
                if process_matches(evidence):
                    raise RuntimeManagerError(
                        "runtime.ownership_ambiguous", "stale_process_survived"
                    )
                await asyncio.to_thread(artifacts.cleanup)
            except BaseException:
                # Retain suspicious evidence and release only the held lock.
                with suppress(OSError):
                    artifacts.release_lock()
                raise

    @property
    def pending_start_count(self) -> int:
        return len(self._pending)

    async def _allocate_endpoint(self) -> int:
        async with self._registry_lock:
            for _ in range(self._runtime_defaults().endpoint_allocation_attempts):
                port = await asyncio.to_thread(allocate_loopback_port)
                if port not in self._allocated_ports:
                    self._allocated_ports.add(port)
                    return port
        raise RuntimeEndpointError()

    async def _release_endpoint(self, port: int) -> None:
        async with self._capacity_changed:
            self._allocated_ports.discard(port)
            self._capacity_changed.notify_all()

    def has_active(self, profile_id: ProfileId) -> bool:
        return profile_id in self._active

    async def _transition(
        self,
        profile_id: ProfileId,
        snapshot: RuntimeSnapshot,
        kind: RuntimeEventKind,
        callback: StateCallback | None,
        *,
        reason_class: str | None = None,
    ) -> None:
        active = self._active.get(profile_id)
        previous = self._last_snapshots.get(profile_id)
        previous_state = None if previous is None else previous.state
        if not is_legal_transition(previous_state, snapshot.state):
            raise RuntimeManagerError(
                "runtime.invalid_transition",
                f"{previous_state}->{snapshot.state.value}",
            )
        if active is not None:
            active.snapshot = snapshot
        self._last_snapshots[profile_id] = snapshot
        if snapshot.runtime_id is not None and snapshot.model_id is not None:
            await asyncio.to_thread(self._record_event, profile_id, snapshot, kind, reason_class)
        if callback is not None:
            await callback(snapshot)

    def _record_event(
        self,
        profile_id: ProfileId,
        snapshot: RuntimeSnapshot,
        kind: RuntimeEventKind,
        reason_class: str | None,
    ) -> None:
        assert snapshot.runtime_id is not None and snapshot.model_id is not None
        try:
            with (
                SQLiteDatabase(self._database_path) as database,
                database.transaction(immediate=True),
            ):
                RuntimeRepository(database.connection()).add_event(
                    event_id=str(self._event_ids.new_event_id()),
                    profile_id=profile_id,
                    model_id=snapshot.model_id,
                    runtime_id=snapshot.runtime_id,
                    state=snapshot.state,
                    event_kind=kind,
                    reason_class=reason_class,
                    occurred_at=self._clock.now(),
                    retention_count=self._runtime_defaults().event_retention_count,
                )
        except sqlite3.Error as error:
            raise RuntimeDatabaseError() from error

    async def _persist_ready(
        self,
        profile_id: ProfileId,
        model_id: ModelId,
        runtime_id: RuntimeId | None,
        revision: int,
        now: datetime,
    ) -> None:
        assert runtime_id is not None

        def persist() -> None:
            with (
                SQLiteDatabase(self._database_path) as database,
                database.transaction(immediate=True),
            ):
                RuntimeRepository(database.connection()).set_last_valid(
                    profile_id=profile_id,
                    model_id=model_id,
                    profile_model_revision=revision,
                    runtime_id=runtime_id,
                    ready_at=now,
                )

        try:
            await asyncio.to_thread(persist)
        except sqlite3.Error as error:
            raise RuntimeDatabaseError() from error


def _metadata_int(metadata: dict[str, object], key: str) -> int:
    value = metadata[key]
    if type(value) is not int or value <= 0:
        raise RuntimeManagerError("runtime.artifact_invalid", key)
    return value
