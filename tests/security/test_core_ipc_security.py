from __future__ import annotations

import asyncio
import struct
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.core.ownership import SOCKET_FILENAME, RuntimeOwnership
from jarvis.core.requests import RequestContext
from jarvis.core.runtime import JarvisCore
from jarvis.ipc.codec import read_frame
from jarvis.ipc.errors import IpcError
from jarvis.ipc.models import CORE_CONTROL, REQUEST_STREAM
from jarvis.ipc.server import IpcServer
from jarvis.storage.xdg import initialize_xdg_directories, resolve_xdg_paths
from tests.support.ipc_client import RawTestClient

pytestmark = pytest.mark.security


class _NoSocketWriter:
    def get_extra_info(self, _name: str) -> None:
        return None


def test_missing_peer_credentials_fail_closed() -> None:
    server = object.__new__(IpcServer)
    with pytest.raises(IpcError) as caught:
        server._validate_peer(_NoSocketWriter())  # type: ignore[arg-type]
    assert caught.value.code == "ipc.core_unavailable"


def test_header_slowloris_deadline_is_typed() -> None:
    async def run() -> None:
        reader = asyncio.StreamReader()
        with pytest.raises(IpcError) as caught:
            await read_frame(reader, timeout=0.001)
        assert caught.value.code == "ipc.invalid_frame"

    asyncio.run(run())


def test_connection_limit_rejects_before_session_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        monkeypatch.setattr("jarvis.ipc.server.MAX_CONNECTIONS", 1)
        core = JarvisCore()
        task = asyncio.create_task(core.run())
        path = resolve_xdg_paths().runtime / "core.sock"
        for _ in range(200):
            if path.exists():
                break
            await asyncio.sleep(0.005)
        first = await RawTestClient.connect(path, optional_capabilities=(CORE_CONTROL,))
        second = await RawTestClient.connect(path, optional_capabilities=(CORE_CONTROL,))
        assert second.hello is not None
        assert second.hello["type"] == "hello.error"
        assert second.hello["error"]["code"] == "ipc.connection_limit"  # type: ignore[index]
        await second.close()
        await first.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_connection_limit_admission_is_atomic_under_concurrent_handshakes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        monkeypatch.setattr("jarvis.ipc.server.MAX_CONNECTIONS", 2)
        core = JarvisCore()
        task = asyncio.create_task(core.run())
        path = resolve_xdg_paths().runtime / "core.sock"
        for _ in range(200):
            if path.exists():
                break
            await asyncio.sleep(0.005)

        gate = asyncio.Event()

        async def connect() -> RawTestClient:
            await gate.wait()
            return await RawTestClient.connect(path, optional_capabilities=(CORE_CONTROL,))

        attempts = [asyncio.create_task(connect()) for _ in range(12)]
        gate.set()
        clients = await asyncio.gather(*attempts)
        successful = [
            client
            for client in clients
            if client.hello is not None and client.hello["type"] == "hello.ok"
        ]
        rejected = [
            client
            for client in clients
            if client.hello is not None and client.hello["type"] == "hello.error"
        ]
        assert len(successful) <= 2
        assert len(successful) + len(rejected) == 12
        assert all(client.hello["error"]["code"] == "ipc.connection_limit" for client in rejected)  # type: ignore[index]

        for client in clients:
            await client.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_disconnected_logical_sessions_are_globally_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def run() -> None:
        monkeypatch.setattr("jarvis.ipc.server.MAX_LOGICAL_SESSIONS", 1)
        core = JarvisCore()
        task = asyncio.create_task(core.run())
        path = resolve_xdg_paths().runtime / "core.sock"
        for _ in range(200):
            if path.exists():
                break
            await asyncio.sleep(0.005)

        first = await RawTestClient.connect(path, optional_capabilities=(CORE_CONTROL,))
        await first.close()
        second = await RawTestClient.connect(path, optional_capabilities=(CORE_CONTROL,))
        assert second.hello is not None
        assert second.hello["type"] == "hello.error"
        assert second.hello["error"]["code"] == "ipc.connection_limit"  # type: ignore[index]
        await second.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_socket_replacement_is_not_removed_during_cleanup() -> None:
    paths = resolve_xdg_paths()
    initialize_xdg_directories(paths)
    ownership = RuntimeOwnership.acquire(paths.runtime)
    server = ownership.bind_socket()
    path = paths.runtime / SOCKET_FILENAME
    server.close()
    path.unlink()
    path.write_text("replacement")
    path.chmod(0o600)
    ownership.close()
    assert path.read_text() == "replacement"


def test_malformed_handshake_frame_returns_safe_error_and_no_raw_input() -> None:
    async def run() -> None:
        core = JarvisCore()
        task = asyncio.create_task(core.run())
        path = resolve_xdg_paths().runtime / "core.sock"
        for _ in range(200):
            if path.exists():
                break
            await asyncio.sleep(0.005)
        reader, writer = await asyncio.open_unix_connection(path)
        raw = b'{"type":"hello","type":"duplicate"}'
        writer.write(struct.pack(">I", len(raw)) + raw)
        await writer.drain()
        response = await read_frame(reader)
        assert response["type"] == "hello.error"
        serialized = str(response)
        assert "duplicate" not in serialized
        writer.close()
        await writer.wait_closed()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_raw_handler_exception_and_resume_tokens_never_reach_diagnostics() -> None:
    private_text = "/private/home/path bearer synthetic-secret"

    async def handler(_context: RequestContext) -> dict[str, object]:
        raise RuntimeError(private_text)

    async def run() -> Path:
        core = JarvisCore(handlers={"test.fail": handler})
        task = asyncio.create_task(core.run())
        paths = resolve_xdg_paths()
        for _ in range(200):
            if (paths.runtime / "core.sock").exists():
                break
            await asyncio.sleep(0.005)
        client = await RawTestClient.connect(
            paths.runtime / "core.sock", optional_capabilities=(CORE_CONTROL,)
        )
        assert client.hello is not None
        resume_token = str(client.hello["resume_token"])
        events = await client.request(request_id=str(uuid4()), operation="test.fail")
        assert events[-1]["error"]["code"] == "ipc.internal_error"  # type: ignore[index]
        assert private_text not in str(events)
        await client.close()
        await core.request_shutdown()
        await asyncio.wait_for(task, 5)
        diagnostics = paths.state / "diagnostics"
        persisted = b"".join(path.read_bytes() for path in diagnostics.iterdir())
        assert resume_token.encode() not in persisted
        assert private_text.encode() not in persisted
        return diagnostics

    assert asyncio.run(run()).is_dir()


def test_protocol_vocabulary_contains_no_control_token_artifact() -> None:
    source = Path("src").read_text() if Path("src").is_file() else ""
    assert "core-control.token" not in source
    assert not list(Path("src").rglob("*control*token*"))
    assert REQUEST_STREAM == "request-stream-v1"
