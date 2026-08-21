"""Core composition root for foundation, profiles, ownership, and diagnostics."""

from __future__ import annotations

import asyncio
import socket
from contextlib import suppress
from dataclasses import dataclass

from jarvis.chat.agent import AgentEngine
from jarvis.chat.coordinator import GenerationCoordinator
from jarvis.chat.diagnostics import ChatDiagnosticService
from jarvis.chat.learning import LearningService
from jarvis.chat.repository import ConversationRepository
from jarvis.config.defaults import DefaultsRegistry, DefaultsSnapshot
from jarvis.core.identity import CoreRuntimeIdentity
from jarvis.core.lifecycle import CoreLifecycle, CoreLifecycleState
from jarvis.core.ownership import RuntimeOwnership, classify_lock_loser
from jarvis.diagnostics.events import InfrastructureEvent, Severity
from jarvis.diagnostics.sink import InfrastructureDiagnosticSink
from jarvis.foundation.bootstrap import DATABASE_FILENAME, initialize_foundation
from jarvis.foundation.clock import Clock, SystemClock, format_utc
from jarvis.foundation.identifiers import IdGenerator, RandomIdGenerator
from jarvis.ipc.errors import IpcError
from jarvis.ipc.models import (
    SERVER_CAPABILITIES,
    CoreInstanceId,
    ProtocolIdGenerator,
    RandomProtocolIdGenerator,
)
from jarvis.ipc.server import Handler, IpcServer
from jarvis.llm.llama_cpp import LlamaCppProvider
from jarvis.llm.provider import LLMProvider
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.service import ProfileConfigService, ProfileService
from jarvis.runtimes.manager import RuntimeManager
from jarvis.storage.xdg import XdgPaths, initialize_xdg_directories, resolve_xdg_paths


@dataclass(slots=True)
class CoreResources:
    paths: XdgPaths
    defaults: DefaultsSnapshot
    lifecycle: CoreLifecycle
    core_instance_id: CoreInstanceId
    identity: CoreRuntimeIdentity
    ownership: RuntimeOwnership
    listener: socket.socket
    diagnostics: InfrastructureDiagnosticSink
    profiles: ProfileService
    profile_configuration: ProfileConfigService
    model_registry: ModelRegistryService
    runtime_manager: RuntimeManager
    conversations: ConversationRepository
    learning: LearningService
    chat_diagnostics: ChatDiagnosticService
    generation_coordinator: GenerationCoordinator
    agent: AgentEngine
    clock: Clock
    event_ids: IdGenerator
    _closed: bool = False

    @classmethod
    def start(
        cls,
        *,
        clock: Clock | None = None,
        event_ids: IdGenerator | None = None,
        protocol_ids: ProtocolIdGenerator | None = None,
        provider: LLMProvider | None = None,
    ) -> CoreResources:
        active_clock = SystemClock() if clock is None else clock
        active_event_ids = RandomIdGenerator() if event_ids is None else event_ids
        active_protocol_ids = RandomProtocolIdGenerator() if protocol_ids is None else protocol_ids
        lifecycle = CoreLifecycle()
        paths = resolve_xdg_paths()
        ownership: RuntimeOwnership | None = None
        listener: socket.socket | None = None
        diagnostics: InfrastructureDiagnosticSink | None = None
        try:
            initialize_xdg_directories(paths)
            try:
                ownership = RuntimeOwnership.acquire(paths.runtime)
            except IpcError as error:
                if error.code == "ipc.core_already_running":
                    classify_lock_loser(paths.runtime)
                raise
            initialize_foundation(clock=active_clock)
            defaults_registry = DefaultsRegistry.load_packaged()
            defaults = defaults_registry.current()
            core_instance_id = active_protocol_ids.new_core_instance_id()
            identity = CoreRuntimeIdentity.capture(
                core_instance_id,
                started_at_utc=format_utc(active_clock.now()),
            )
            ownership.publish_metadata(identity, lifecycle.state, sorted(SERVER_CAPABILITIES))
            diagnostics = InfrastructureDiagnosticSink(
                paths.state, defaults.foundation_diagnostics, active_clock
            )
            _emit(
                diagnostics,
                active_event_ids,
                active_clock,
                "core.starting",
                {"core_instance_id": str(core_instance_id), "state": lifecycle.state.value},
            )
            profiles = ProfileService(
                paths.data / DATABASE_FILENAME,
                defaults=defaults_registry,
                clock=active_clock,
            )
            profiles.ensure_jarvis()
            profile_configuration = ProfileConfigService(
                paths.data / DATABASE_FILENAME,
                defaults=defaults_registry,
                clock=active_clock,
            )
            model_registry = ModelRegistryService(
                paths.data / DATABASE_FILENAME,
                active_clock,
                diagnostics=diagnostics,
                event_ids=active_event_ids,
                defaults=defaults_registry,
            )
            generation_coordinator = GenerationCoordinator(defaults.chat.max_queued_generations)
            runtime_manager = RuntimeManager(
                database_path=paths.data / DATABASE_FILENAME,
                runtime_root=paths.runtime,
                models=model_registry,
                provider=LlamaCppProvider() if provider is None else provider,
                defaults=defaults_registry,
                clock=active_clock,
                event_ids=active_event_ids,
                generations=generation_coordinator,
                diagnostics=diagnostics,
            )
            conversations = ConversationRepository(paths.data / DATABASE_FILENAME)
            chat_diagnostics = ChatDiagnosticService(
                paths.data / DATABASE_FILENAME,
                defaults.chat,
                defaults.foundation_diagnostics,
                active_clock,
            )
            learning = LearningService(conversations, active_clock)
            agent = AgentEngine(
                conversations=conversations,
                diagnostics=chat_diagnostics,
                coordinator=generation_coordinator,
                runtime_manager=runtime_manager,
                profiles=profile_configuration,
                models=model_registry,
                defaults=defaults_registry,
                clock=active_clock,
            )
            listener = ownership.bind_socket()
            lifecycle.transition(CoreLifecycleState.READY)
            ownership.publish_metadata(identity, lifecycle.state, sorted(SERVER_CAPABILITIES))
            _emit(
                diagnostics,
                active_event_ids,
                active_clock,
                "core.ready",
                {"core_instance_id": str(core_instance_id), "state": lifecycle.state.value},
            )
            return cls(
                paths=paths,
                defaults=defaults,
                lifecycle=lifecycle,
                core_instance_id=core_instance_id,
                identity=identity,
                ownership=ownership,
                listener=listener,
                diagnostics=diagnostics,
                profiles=profiles,
                profile_configuration=profile_configuration,
                model_registry=model_registry,
                runtime_manager=runtime_manager,
                conversations=conversations,
                learning=learning,
                chat_diagnostics=chat_diagnostics,
                generation_coordinator=generation_coordinator,
                agent=agent,
                clock=active_clock,
                event_ids=active_event_ids,
            )
        except BaseException:
            if lifecycle.state is CoreLifecycleState.STARTING:
                lifecycle.transition(CoreLifecycleState.ERROR)
            if listener is not None:
                listener.close()
            if diagnostics is not None:
                diagnostics.abandon()
            if ownership is not None:
                ownership.close()
            raise

    def begin_stopping(self) -> None:
        if self.lifecycle.state is CoreLifecycleState.READY:
            self.lifecycle.transition(CoreLifecycleState.STOPPING)
            self.ownership.publish_metadata(
                self.identity, self.lifecycle.state, sorted(SERVER_CAPABILITIES)
            )
            _emit(
                self.diagnostics,
                self.event_ids,
                self.clock,
                "core.stopping",
                {
                    "core_instance_id": str(self.core_instance_id),
                    "state": self.lifecycle.state.value,
                },
            )

    def close(self) -> None:
        if self._closed:
            return
        self.begin_stopping()
        self.listener.close()
        if self.lifecycle.state is CoreLifecycleState.ERROR:
            self.lifecycle.transition(CoreLifecycleState.STOPPING)
        if self.lifecycle.state is CoreLifecycleState.STOPPING:
            self.lifecycle.transition(CoreLifecycleState.STOPPED)
        _emit(
            self.diagnostics,
            self.event_ids,
            self.clock,
            "core.stopped",
            {
                "core_instance_id": str(self.core_instance_id),
                "state": self.lifecycle.state.value,
            },
        )
        self.diagnostics.close()
        self.ownership.close()
        self._closed = True

    def __enter__(self) -> CoreResources:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _emit(
    sink: InfrastructureDiagnosticSink,
    identifiers: IdGenerator,
    clock: Clock,
    event_type: str,
    fields: dict[str, object],
) -> None:
    sink.emit(
        InfrastructureEvent(
            event_id=identifiers.new_event_id(),
            timestamp_utc=clock.now(),
            event_type=event_type,
            subsystem="core.lifecycle",
            severity=Severity.INFO,
            fields=fields,
        )
    )


class JarvisCore:
    """Foreground authoritative Core host."""

    def __init__(
        self,
        *,
        handlers: dict[str, Handler] | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self._handlers = handlers
        self._provider = provider
        self._shutdown = asyncio.Event()
        self._resources: CoreResources | None = None
        self._server: IpcServer | None = None

    @property
    def resources(self) -> CoreResources | None:
        return self._resources

    @property
    def in_flight_count(self) -> int:
        return 0 if self._server is None else self._server.registry.in_flight_count

    async def request_shutdown(self) -> None:
        self._shutdown.set()

    async def run(self) -> None:
        self._resources = CoreResources.start(provider=self._provider)
        resources = self._resources
        server = IpcServer(
            listener=resources.listener,
            core_instance_id=resources.core_instance_id,
            lifecycle=resources.lifecycle,
            profiles=resources.profiles,
            profile_configuration=resources.profile_configuration,
            model_registry=resources.model_registry,
            runtime_manager=resources.runtime_manager,
            agent=resources.agent,
            conversations=resources.conversations,
            learning=resources.learning,
            chat_diagnostics=resources.chat_diagnostics,
            defaults=resources.defaults,
            started_at_utc=resources.identity.started_at_utc,
            shutdown_callback=self.request_shutdown,
            handlers=self._handlers,
            diagnostics=resources.diagnostics,
            clock=resources.clock,
            event_ids=resources.event_ids,
        )
        self._server = server
        try:
            await resources.runtime_manager.recover_stale()
            await server.start()
            await self._shutdown.wait()
            resources.begin_stopping()
            await server.stop_accepting()
            await server.registry.cancel_all_unfinished()
            with suppress(TimeoutError):
                await asyncio.wait_for(self._wait_for_requests(), timeout=5.0)
            await server.close()
            await resources.generation_coordinator.close()
            await resources.runtime_manager.close()
        finally:
            resources.close()

    async def _wait_for_requests(self) -> None:
        while self._server is not None and self._server.registry.in_flight_count:
            await asyncio.sleep(0.01)
