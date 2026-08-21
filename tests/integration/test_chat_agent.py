from __future__ import annotations

import asyncio
import struct
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.chat.agent import AgentEngine, AgentStreamEvent
from jarvis.chat.coordinator import GenerationCoordinator
from jarvis.chat.diagnostics import ChatDiagnosticService
from jarvis.chat.errors import ChatStorageError, ProviderStreamError
from jarvis.chat.models import TurnState
from jarvis.chat.repository import ConversationRepository
from jarvis.config.defaults import DefaultsRegistry
from jarvis.foundation.bootstrap import DATABASE_FILENAME, initialize_foundation
from jarvis.foundation.clock import SystemClock
from jarvis.llm.fake import FakeLLMProvider
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.destructive import ConfirmDestructiveOperation, ResetScope
from jarvis.profiles.models import CreateProfile, Profile
from jarvis.profiles.service import ProfileConfigService, ProfileService
from jarvis.runtimes.lifecycle import ProfileRuntimeLifecycleCoordinator
from jarvis.runtimes.manager import RuntimeManager
from jarvis.runtimes.models import RuntimeState
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.xdg import resolve_xdg_paths

pytestmark = pytest.mark.integration


class Signal:
    def __init__(self) -> None:
        self.event = asyncio.Event()

    @property
    def requested(self) -> bool:
        return self.event.is_set()

    async def wait(self) -> None:
        await self.event.wait()

    def request(self) -> bool:
        first = not self.event.is_set()
        self.event.set()
        return first


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


def _setup(
    tmp_path: Path,
) -> tuple[
    AgentEngine, RuntimeManager, FakeLLMProvider, Profile, Profile, Path, GenerationCoordinator
]:
    initialize_foundation()
    paths = resolve_xdg_paths()
    database_path = paths.data / DATABASE_FILENAME
    defaults = DefaultsRegistry.load_packaged()
    clock = SystemClock()
    models = ModelRegistryService(database_path, clock, defaults=defaults)
    root = tmp_path / "models"
    root.mkdir()
    model_path = root / "tiny.gguf"
    _fixture(model_path)
    models.update_runtime_location((str(root),), "/usr/bin/gnutrue")
    record = models.refresh().records[0]
    profile_service = ProfileService(database_path, defaults=defaults)
    jarvis = profile_service.ensure_jarvis().profile
    other = profile_service.create_profile(CreateProfile("Other")).profile
    models.select(jarvis.profile_id, record.model_id, 0)
    models.select(other.profile_id, record.model_id, 0)
    provider = FakeLLMProvider(chat_deltas=("hello ", "world"))
    coordinator = GenerationCoordinator()
    manager = RuntimeManager(
        database_path=database_path,
        runtime_root=paths.runtime,
        models=models,
        provider=provider,
        defaults=defaults,
        generations=coordinator,
    )
    conversations = ConversationRepository(database_path)
    diagnostics = ChatDiagnosticService(
        database_path,
        defaults.current().chat,
        defaults.current().foundation_diagnostics,
        clock,
    )
    agent = AgentEngine(
        conversations=conversations,
        diagnostics=diagnostics,
        coordinator=coordinator,
        runtime_manager=manager,
        profiles=ProfileConfigService(database_path, defaults=defaults),
        models=models,
        defaults=defaults,
        clock=clock,
    )
    return agent, manager, provider, jarvis, other, database_path, coordinator


def test_agent_autostarts_streams_persists_learning_and_neutral_provenance(
    tmp_path: Path,
) -> None:
    agent, manager, provider, jarvis, _other, database_path, _coordinator = _setup(tmp_path)

    async def run() -> None:
        events: list[AgentStreamEvent] = []

        async def emit(event: AgentStreamEvent) -> None:
            events.append(event)

        turn = await agent.chat(
            profile_id=jarvis.profile_id,
            request_id=str(uuid4()),
            content="analyze offensive-security malware sample",
            cancellation=Signal(),
            emit=emit,
        )
        assert turn.state is TurnState.COMPLETED
        assert [event.event_type for event in events] == [
            "response_started",
            "text_delta",
            "text_delta",
            "response_completed",
        ]
        assert len(provider.starts) == 1
        assert (await manager.status(jarvis.profile_id)).state is RuntimeState.READY
        request = provider.captured_requests[0]
        assert [message.provenance for message in request.messages] == [
            "CORE_PROTOCOL",
            "PROFILE_PERSONA",
            "PROFILE_CONTEXT",
            "USER_CONFIGURED",
            "TECHNICAL_FORMATTING",
            "USER_REQUEST",
        ]
        joined = "\n".join(message.content for message in request.messages)
        assert "offensive-security malware" in joined
        assert "OpenAI policy" not in joined
        await manager.close()

    asyncio.run(run())
    with SQLiteDatabase(database_path) as database:
        connection = database.connection()
        assert connection.execute("SELECT status FROM learning_state").fetchone()[0] == "ACTIVE"
        assert connection.execute(
            "SELECT role, content FROM chat_messages ORDER BY ordinal"
        ).fetchall() == [
            ("user", "analyze offensive-security malware sample"),
            ("assistant", "hello world"),
        ]
        assert (
            connection.execute("SELECT COUNT(*) FROM chat_diagnostics WHERE closed = 1").fetchone()[
                0
            ]
            >= 3
        )


def test_agent_active_cancellation_is_durable_and_runtime_returns_ready(tmp_path: Path) -> None:
    agent, manager, provider, jarvis, _other, database_path, _coordinator = _setup(tmp_path)
    provider.chat_gate.clear()

    async def run() -> None:
        signal = Signal()

        async def emit(_event: AgentStreamEvent) -> None:
            return None

        task = asyncio.create_task(
            agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="cancel me",
                cancellation=signal,
                emit=emit,
            )
        )
        await provider.chat_entered.wait()
        signal.request()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await manager.status(jarvis.profile_id)).state is RuntimeState.READY
        await manager.close()

    asyncio.run(run())
    with SQLiteDatabase(database_path) as database:
        row = database.connection().execute("SELECT state, failure_code FROM chat_turns").fetchone()
        assert row == ("cancelled", "chat.cancelled")
        assert (
            database.connection()
            .execute("SELECT COUNT(*) FROM chat_messages WHERE role = 'assistant'")
            .fetchone()[0]
            == 0
        )


def test_simulated_enospc_aborts_before_chat_admission_or_runtime_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent, _manager, provider, jarvis, _other, database_path, _coordinator = _setup(tmp_path)

    def fail_reservation(
        _service: ChatDiagnosticService, _profile_id: object, _model_id: object
    ) -> object:
        raise ChatStorageError("simulated_enospc")

    monkeypatch.setattr(ChatDiagnosticService, "reserve", fail_reservation)

    async def run() -> None:
        async def emit(_event: AgentStreamEvent) -> None:
            return None

        with pytest.raises(ChatStorageError) as caught:
            await agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="must not start",
                cancellation=Signal(),
                emit=emit,
            )
        assert caught.value.safe_details["reason"] == "simulated_enospc"

    asyncio.run(run())
    assert provider.starts == []
    with SQLiteDatabase(database_path) as database:
        assert database.connection().execute("SELECT COUNT(*) FROM chat_turns").fetchone()[0] == 0


def test_same_profile_fifo_and_cross_profile_concurrency(tmp_path: Path) -> None:
    agent, manager, provider, jarvis, other, _database_path, coordinator = _setup(tmp_path)
    provider.chat_gate.clear()

    async def run() -> None:
        async def emit(_event: AgentStreamEvent) -> None:
            return None

        first = asyncio.create_task(
            agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="first",
                cancellation=Signal(),
                emit=emit,
            )
        )
        await provider.chat_entered.wait()
        second = asyncio.create_task(
            agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="second",
                cancellation=Signal(),
                emit=emit,
            )
        )
        other_task = asyncio.create_task(
            agent.chat(
                profile_id=other.profile_id,
                request_id=str(uuid4()),
                content="other",
                cancellation=Signal(),
                emit=emit,
            )
        )
        while await coordinator.queued_count(jarvis.profile_id) != 1:
            await asyncio.sleep(0)
        # Other profile reaches its own runtime even while Jarvis remains blocked.
        while len(provider.starts) != 2:
            await asyncio.sleep(0)
        assert not other_task.done()
        provider.chat_gate.set()
        await asyncio.gather(first, second, other_task)
        assert [request.messages[-1].content for request in provider.captured_requests] == [
            "first",
            "other",
            "second",
        ]
        await manager.close()

    asyncio.run(run())


def test_queued_turn_context_contains_only_completed_prior_turns(tmp_path: Path) -> None:
    """Later admitted user input must never be prompt history for an earlier turn."""

    agent, manager, provider, jarvis, _other, _database_path, coordinator = _setup(tmp_path)
    provider.chat_gate.clear()

    async def run() -> None:
        async def emit(_event: AgentStreamEvent) -> None:
            return None

        first = asyncio.create_task(
            agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="first request",
                cancellation=Signal(),
                emit=emit,
            )
        )
        await provider.chat_entered.wait()
        second = asyncio.create_task(
            agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="second request",
                cancellation=Signal(),
                emit=emit,
            )
        )
        while await coordinator.queued_count(jarvis.profile_id) != 1:
            await asyncio.sleep(0)
        provider.chat_gate.set()
        await asyncio.gather(first, second)
        first_request, second_request = provider.captured_requests
        first_input = "\n".join(message.content for message in first_request.messages)
        second_input = "\n".join(message.content for message in second_request.messages)
        assert "second request" not in first_input
        assert "first request" in second_input
        assert "hello world" in second_input
        await manager.close()

    asyncio.run(run())


def test_queued_cancellation_never_reaches_provider_and_is_durable(tmp_path: Path) -> None:
    agent, manager, provider, jarvis, _other, database_path, coordinator = _setup(tmp_path)
    provider.chat_gate.clear()

    async def run() -> None:
        async def emit(_event: AgentStreamEvent) -> None:
            return None

        first = asyncio.create_task(
            agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="active",
                cancellation=Signal(),
                emit=emit,
            )
        )
        await provider.chat_entered.wait()
        queued_signal = Signal()
        queued = asyncio.create_task(
            agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="queued cancellation",
                cancellation=queued_signal,
                emit=emit,
            )
        )
        while await coordinator.queued_count(jarvis.profile_id) != 1:
            await asyncio.sleep(0)
        queued_signal.request()
        with pytest.raises(asyncio.CancelledError):
            await queued
        assert [request.messages[-1].content for request in provider.captured_requests] == [
            "active"
        ]
        provider.chat_gate.set()
        await first
        await manager.close()

    asyncio.run(run())
    with SQLiteDatabase(database_path) as database:
        assert database.connection().execute(
            "SELECT state, failure_code FROM chat_turns WHERE partial_text = ''"
        ).fetchone() == ("cancelled", "chat.cancelled")


def test_partial_provider_failure_is_failed_not_successful_and_cleans_busy(tmp_path: Path) -> None:
    agent, manager, provider, jarvis, _other, database_path, _coordinator = _setup(tmp_path)
    provider.fail_chat_after = 1

    async def run() -> None:
        async def emit(_event: AgentStreamEvent) -> None:
            return None

        with pytest.raises(ProviderStreamError) as caught:
            await agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="partial provider failure",
                cancellation=Signal(),
                emit=emit,
            )
        assert getattr(caught.value, "code", None) == "chat.provider_failed"
        assert (await manager.status(jarvis.profile_id)).state is RuntimeState.READY
        await manager.close()

    asyncio.run(run())
    with SQLiteDatabase(database_path) as database:
        connection = database.connection()
        assert connection.execute(
            "SELECT state, failure_code, partial_text FROM chat_turns"
        ).fetchone() == ("failed", "chat.provider_failed", "hello ")
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM chat_messages WHERE role = 'assistant'"
            ).fetchone()[0]
            == 0
        )


def test_whole_profile_reset_cancels_active_generation_without_deadlock(tmp_path: Path) -> None:
    agent, manager, provider, jarvis, _other, database_path, _coordinator = _setup(tmp_path)
    provider.chat_gate.clear()
    profiles = ProfileService(database_path)
    configurations = ProfileConfigService(database_path)
    lifecycle = ProfileRuntimeLifecycleCoordinator(profiles, configurations, manager)

    async def run() -> None:
        async def emit(_event: AgentStreamEvent) -> None:
            return None

        generation = asyncio.create_task(
            agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="reset during generation",
                cancellation=Signal(),
                emit=emit,
            )
        )
        await provider.chat_entered.wait()
        preview = await asyncio.to_thread(
            configurations.preview_reset, jarvis.profile_id, ResetScope.WHOLE_PROFILE
        )
        reset_task = asyncio.create_task(
            lifecycle.confirm_reset(
                ConfirmDestructiveOperation(
                    preview.operation_id,
                    preview.target,
                    jarvis.profile_id,
                    preview.confirmation_token,
                )
            )
        )
        result = await asyncio.wait_for(reset_task, 2)
        assert result.profile_id == jarvis.profile_id
        with pytest.raises(asyncio.CancelledError):
            await generation
        assert (await manager.status(jarvis.profile_id)).state is RuntimeState.STOPPED
        await manager.close()

    asyncio.run(run())
    with SQLiteDatabase(database_path) as database:
        connection = database.connection()
        for table in ("chat_sessions", "chat_turns", "chat_messages", "learning_state"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_model_switch_waits_for_generation_then_replaces_runtime(tmp_path: Path) -> None:
    agent, manager, provider, jarvis, _other, database_path, _coordinator = _setup(tmp_path)
    models = ModelRegistryService(database_path)
    _fixture(tmp_path / "models" / "second.gguf", b"Second")
    second = next(
        record
        for record in models.refresh().records
        if record.metadata.get("general.name") == "Second"
    )
    provider.chat_gate.clear()

    async def run() -> None:
        async def emit(_event: AgentStreamEvent) -> None:
            return None

        generation = asyncio.create_task(
            agent.chat(
                profile_id=jarvis.profile_id,
                request_id=str(uuid4()),
                content="finish on original model",
                cancellation=Signal(),
                emit=emit,
            )
        )
        await provider.chat_entered.wait()
        switch = asyncio.create_task(manager.switch(jarvis.profile_id, second.model_id, 1))
        await asyncio.sleep(0)
        assert not switch.done()
        assert len(provider.starts) == 1
        provider.chat_gate.set()
        completed, switched = await asyncio.gather(generation, switch)
        assert completed.model_id != second.model_id
        assert switched.model_id == second.model_id
        assert [start.model_id for start in provider.starts] == [
            completed.model_id,
            second.model_id,
        ]
        await manager.close()

    asyncio.run(run())
    selected = [item for item in models.associations(jarvis.profile_id) if item["selected"]]
    assert selected[0]["model_id"] == str(second.model_id)


def test_profile_delete_cancels_active_generation_and_cascades_chat_state(tmp_path: Path) -> None:
    agent, manager, provider, _jarvis, other, database_path, _coordinator = _setup(tmp_path)
    provider.chat_gate.clear()
    profiles = ProfileService(database_path)
    lifecycle = ProfileRuntimeLifecycleCoordinator(
        profiles, ProfileConfigService(database_path), manager
    )

    async def run() -> None:
        async def emit(_event: AgentStreamEvent) -> None:
            return None

        generation = asyncio.create_task(
            agent.chat(
                profile_id=other.profile_id,
                request_id=str(uuid4()),
                content="delete during generation",
                cancellation=Signal(),
                emit=emit,
            )
        )
        await provider.chat_entered.wait()
        preview, was_active = await lifecycle.preview_delete(other.profile_id)
        assert was_active
        result = await asyncio.wait_for(
            lifecycle.confirm_delete(
                ConfirmDestructiveOperation(
                    preview.operation_id,
                    preview.target,
                    other.profile_id,
                    preview.confirmation_token,
                )
            ),
            2,
        )
        assert result.profile_id == other.profile_id
        with pytest.raises(asyncio.CancelledError):
            await generation
        await manager.close()

    asyncio.run(run())
    with SQLiteDatabase(database_path) as database:
        connection = database.connection()
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM profiles WHERE profile_id = ?", (str(other.profile_id),)
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM chat_turns WHERE profile_id = ?", (str(other.profile_id),)
            ).fetchone()[0]
            == 0
        )
