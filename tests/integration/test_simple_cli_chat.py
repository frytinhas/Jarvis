from __future__ import annotations

import asyncio
import io
import struct
from dataclasses import replace
from pathlib import Path

import pytest

from jarvis.cli.chat_application import ChatArguments, SimpleChatClient, run_chat
from jarvis.cli.commands import parse_slash_command
from jarvis.cli.presenter import TerminalPresenter
from jarvis.core.runtime import JarvisCore
from jarvis.foundation.bootstrap import initialize_foundation
from jarvis.llm.fake import FakeLLMProvider
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.configuration import UpdateProfileConfiguration
from jarvis.profiles.models import CreateProfile, VisibleLoggingMode
from jarvis.profiles.service import ProfileConfigService, ProfileService
from jarvis.storage.database import SQLiteDatabase
from jarvis.storage.xdg import resolve_xdg_paths

pytestmark = pytest.mark.integration


def _gguf(path: Path) -> None:
    key = b"general.name"
    name = b"CLI Test"
    path.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + struct.pack("<Q", len(key))
        + key
        + struct.pack("<I", 8)
        + struct.pack("<Q", len(name))
        + name
    )


def _seed(tmp_path: Path, *, alias_profile: bool = False) -> tuple[str, str]:
    initialize_foundation()
    database = resolve_xdg_paths().data / "jarvis.sqlite3"
    profiles = ProfileService(database)
    jarvis = profiles.ensure_jarvis().profile
    selected = profiles.create_profile(CreateProfile("Work")).profile if alias_profile else jarvis
    model_root = tmp_path / "models"
    model_root.mkdir(exist_ok=True)
    _gguf(model_root / "cli.gguf")
    models = ModelRegistryService(database)
    models.update_runtime_location((str(model_root),), "/usr/bin/gnutrue")
    model = models.refresh().records[0]
    models.select(jarvis.profile_id, model.model_id, 0)
    if selected.profile_id != jarvis.profile_id:
        models.select(selected.profile_id, model.model_id, 0)
    return selected.command_alias, str(model.model_id)


async def _start(provider: FakeLLMProvider) -> tuple[JarvisCore, asyncio.Task[None]]:
    core = JarvisCore(provider=provider)
    task = asyncio.create_task(core.run())
    socket_path = resolve_xdg_paths().runtime / "core.sock"
    for _ in range(400):
        if socket_path.exists():
            return core, task
        await asyncio.sleep(0.005)
    raise AssertionError("Core did not start")


async def _stop(core: JarvisCore, task: asyncio.Task[None]) -> None:
    await core.request_shutdown()
    await asyncio.wait_for(task, 5)


def test_one_shot_streams_learning_and_latest_session_continuity(tmp_path: Path) -> None:
    alias, _model_id = _seed(tmp_path)
    provider = FakeLLMProvider(chat_deltas=("olá ", "senhor"))

    async def scenario() -> None:
        core, core_task = await _start(provider)
        output = io.StringIO()
        presenter = TerminalPresenter(stdin=io.StringIO(), stdout=output)
        try:
            assert await run_chat(ChatArguments(alias, "olá"), presenter) == 0
            assert "olá senhor" in output.getvalue()
            assert "Learning session" in output.getvalue()
            assert len(provider.captured_requests) == 1

            client = await SimpleChatClient.connect(presenter, alias)
            try:
                await client.submit("segunda mensagem")
                first_session = client.session_id
                await client.submit("terceira mensagem")
                assert client.session_id == first_session
                assert any(
                    message.content == "segunda mensagem"
                    for message in provider.captured_requests[-1].messages
                )
                clear = parse_slash_command("/clear")
                assert clear is not None
                assert await client.execute(clear)
                await client.submit("nova sessão")
                assert client.session_id != first_session
            finally:
                await client.close()
        finally:
            await _stop(core, core_task)

    asyncio.run(scenario())


def test_every_slash_route_is_intercepted_and_never_submitted(tmp_path: Path) -> None:
    alias, _model_id = _seed(tmp_path, alias_profile=True)
    provider = FakeLLMProvider(chat_deltas=("answer",))

    async def scenario() -> None:
        core, core_task = await _start(provider)
        output = io.StringIO()
        presenter = TerminalPresenter(stdin=io.StringIO(), stdout=output)
        client = await SimpleChatClient.connect(presenter, alias)
        try:
            await client.submit("create a diagnostic turn")
            baseline = len(provider.captured_requests)
            for raw in (
                "/help",
                "/model",
                "/reasoning",
                "/context",
                "/status",
                "/server",
                "/config",
                "/license",
                "/logs",
                "/learning status",
                "/learning finish",
                "/learning start",
                "/clear",
            ):
                command = parse_slash_command(raw)
                assert command is not None
                assert await client.execute(command)
            assert len(provider.captured_requests) == baseline
            assert "Diagnostic summary (human-only)" in output.getvalue()
            assert "Learning: FINISHED" in output.getvalue()
            assert "Learning: ACTIVE" in output.getvalue()
            assert "history remains" in output.getvalue()
        finally:
            await client.close()
            await _stop(core, core_task)

    asyncio.run(scenario())


def test_none_hides_operational_events_but_core_persists_diagnostics(tmp_path: Path) -> None:
    alias, _model_id = _seed(tmp_path)
    database = resolve_xdg_paths().data / "jarvis.sqlite3"
    profiles = ProfileService(database)
    profile = profiles.resolve_alias(alias)
    configs = ProfileConfigService(database)
    current = configs.get_configuration(profile.profile.profile_id)
    configs.update_configuration(
        UpdateProfileConfiguration(
            profile.profile.profile_id,
            profile.profile.identity_revision,
            current.configuration_revision,
            replace(current.values, visible_logging_mode=VisibleLoggingMode.NONE),
        )
    )
    provider = FakeLLMProvider(chat_deltas=("quiet answer",))

    async def scenario() -> None:
        core, core_task = await _start(provider)
        output = io.StringIO()
        try:
            result = await run_chat(
                ChatArguments(alias, "quiet request"),
                TerminalPresenter(stdin=io.StringIO(), stdout=output),
            )
            assert result == 0
            assert "quiet answer" in output.getvalue()
            assert "Generating response" not in output.getvalue()
        finally:
            await _stop(core, core_task)

    asyncio.run(scenario())
    with SQLiteDatabase(database) as opened:
        assert (
            opened.connection().execute("SELECT COUNT(*) FROM chat_diagnostics").fetchone()[0] > 0
        )


def test_one_shot_terminal_core_error_exits_nonzero(tmp_path: Path) -> None:
    alias, _model_id = _seed(tmp_path)
    provider = FakeLLMProvider(chat_deltas=("never",), fail_chat_after=0)

    async def scenario() -> None:
        core, core_task = await _start(provider)
        output = io.StringIO()
        try:
            result = await run_chat(
                ChatArguments(alias, "trigger a provider failure"),
                TerminalPresenter(stdin=io.StringIO(), stdout=output),
            )
            assert result == 1
            assert "Error: chat.provider_failed" in output.getvalue()
        finally:
            await _stop(core, core_task)

    asyncio.run(scenario())


def test_disconnect_resumes_original_request_without_cancellation_or_duplicate(
    tmp_path: Path,
) -> None:
    alias, _model_id = _seed(tmp_path)
    provider = FakeLLMProvider(chat_deltas=("survived",))
    provider.chat_gate.clear()

    async def scenario() -> None:
        core, core_task = await _start(provider)
        output = io.StringIO()
        client = await SimpleChatClient.connect(
            TerminalPresenter(stdin=io.StringIO(), stdout=output), alias
        )
        try:
            submitted = asyncio.create_task(client.submit("survive disconnect"))
            await asyncio.wait_for(provider.chat_entered.wait(), 2)
            await client.client.close()
            provider.chat_gate.set()
            assert await asyncio.wait_for(submitted, 5) == 0
            assert len(provider.captured_requests) == 1
            assert "Reconnected; attaching" in output.getvalue()
            assert "survived" in output.getvalue()
        finally:
            await client.close()
            await _stop(core, core_task)

    asyncio.run(scenario())


def test_task_cancellation_requests_core_cancellation(tmp_path: Path) -> None:
    alias, _model_id = _seed(tmp_path)
    provider = FakeLLMProvider(chat_deltas=("never",))
    provider.chat_gate.clear()
    database = resolve_xdg_paths().data / "jarvis.sqlite3"

    async def scenario() -> None:
        core, core_task = await _start(provider)
        output = io.StringIO()
        client = await SimpleChatClient.connect(
            TerminalPresenter(stdin=io.StringIO(), stdout=output), alias
        )
        try:
            submitted = asyncio.create_task(client.submit("cancel me"))
            await asyncio.wait_for(provider.chat_entered.wait(), 2)
            submitted.cancel()
            with pytest.raises(asyncio.CancelledError):
                await submitted
            for _ in range(400):
                with SQLiteDatabase(database) as opened:
                    row = (
                        opened.connection()
                        .execute(
                            "SELECT state FROM chat_turns ORDER BY created_at_utc DESC LIMIT 1"
                        )
                        .fetchone()
                    )
                if row == ("cancelled",):
                    break
                await asyncio.sleep(0.005)
            assert row == ("cancelled",)
            assert "Cancellation requested" in output.getvalue()
        finally:
            provider.chat_gate.set()
            await client.close()
            await _stop(core, core_task)

    asyncio.run(scenario())
