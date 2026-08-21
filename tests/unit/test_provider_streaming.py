from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import cast
from uuid import uuid4

import pytest

from jarvis.chat.errors import ProviderStreamError
from jarvis.llm.llama_cpp import LlamaCppProvider
from jarvis.llm.provider import (
    ExecutableIdentity,
    ProcessEvidence,
    ProviderChatRequest,
    ProviderMessage,
    ProviderMessageRole,
    ProviderStreamEvent,
    ProviderStreamEventKind,
    RuntimeHandle,
    StreamSummary,
)
from jarvis.models.models import ModelId
from jarvis.profiles.models import ProfileId
from jarvis.runtimes.models import RuntimeId

pytestmark = [pytest.mark.unit, pytest.mark.local_loopback]


def _request(**bounds: int) -> ProviderChatRequest:
    return ProviderChatRequest(
        messages=(
            ProviderMessage(
                ProviderMessageRole.USER,
                "offensive-security request remains ordinary text",
                "USER_REQUEST",
            ),
        ),
        temperature=0.8,
        top_p=0.95,
        top_k=40,
        min_p=0.0,
        repeat_penalty=1.1,
        generation_timeout_seconds=bounds.get("timeout", 2),
        request_id="request",
        session_id="session",
        turn_id="turn",
        max_delta_bytes=bounds.get("delta", 1024),
        max_sse_frame_bytes=bounds.get("frame", 4096),
        max_response_bytes=bounds.get("response", 8192),
    )


async def _summary(name: str) -> StreamSummary:
    return StreamSummary(name, 0, 0)


def _runtime(port: int) -> RuntimeHandle:
    process = cast(asyncio.subprocess.Process, object())
    return RuntimeHandle(
        RuntimeId.new(),
        ProfileId(uuid4()),
        ModelId.new(),
        process,
        ProcessEvidence(1, 1, "boot", 1, ExecutableIdentity(1, 1)),
        "127.0.0.1",
        port,
        "private-token",
        "2026-08-21T00:00:00.000000Z",
        asyncio.create_task(_summary("stdout")),
        asyncio.create_task(_summary("stderr")),
    )


async def _collect(stream: AsyncIterator[ProviderStreamEvent]) -> list[ProviderStreamEvent]:
    return [event async for event in stream]


def test_llama_provider_streams_authenticated_sse_and_completion_metadata() -> None:
    async def run() -> None:
        captured = b""

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            nonlocal captured
            head = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in head.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            captured = head + await reader.readexactly(length)
            body = (
                b'data: {"choices":[{"delta":{"content":"hello "}}]}\r\n\r\n'
                b'data: {"choices":[{"delta":{"content":"world"}}],'
                b'"usage":{"prompt_tokens":3,"completion_tokens":2}}\r\n\r\n'
                b"data: [DONE]\r\n\r\n"
            )
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + body
            )
            await writer.drain()
            writer.close()
            with suppress(ConnectionError, OSError):
                await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = int(server.sockets[0].getsockname()[1])
        runtime = _runtime(port)
        try:
            events = await _collect(LlamaCppProvider().chat(runtime, _request()))
        finally:
            server.close()
            await server.wait_closed()
        assert b"Authorization: Bearer private-token" in captured
        assert [event.kind for event in events] == [
            ProviderStreamEventKind.TEXT_DELTA,
            ProviderStreamEventKind.TEXT_DELTA,
            ProviderStreamEventKind.COMPLETED,
        ]
        assert "".join(event.text for event in events) == "hello world"
        assert events[-1].prompt_tokens == 3
        assert events[-1].completion_tokens == 2

    asyncio.run(run())


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b"data: {not-json}\n\n", "malformed_sse_json"),
        (b"data: \xff\n\n", "invalid_utf8"),
        (b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n', "provider_disconnected"),
    ],
)
def test_llama_provider_rejects_malformed_invalid_utf8_and_disconnect(
    body: bytes, reason: str
) -> None:
    async def run() -> None:
        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\n\r\n"
                + body
            )
            await writer.drain()
            writer.close()
            with suppress(ConnectionError, OSError):
                await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        runtime = _runtime(int(server.sockets[0].getsockname()[1]))
        try:
            with pytest.raises(ProviderStreamError) as caught:
                await _collect(LlamaCppProvider().chat(runtime, _request()))
            assert caught.value.safe_details["reason"] == reason
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


@pytest.mark.parametrize(
    ("body", "bounds", "reason"),
    [
        (
            b'data: {"choices":[{"delta":{"content":"oversized"}}]}\n\n',
            {"delta": 2},
            "delta_too_large",
        ),
        (b"data: " + (b"x" * 64), {"frame": 16}, "sse_frame_too_large"),
        (
            b'data: {"choices":[{"delta":{"content":"a"}}]}\n\n'
            b'data: {"choices":[{"delta":{"content":"b"}}]}\n\n',
            {"response": 32},
            "response_too_large",
        ),
    ],
)
def test_llama_provider_enforces_stream_bounds(
    body: bytes, bounds: dict[str, int], reason: str
) -> None:
    async def run() -> None:
        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\n\r\n"
                + body
            )
            await writer.drain()
            writer.close()
            with suppress(ConnectionError, OSError):
                await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        runtime = _runtime(int(server.sockets[0].getsockname()[1]))
        try:
            with pytest.raises(ProviderStreamError) as caught:
                await _collect(LlamaCppProvider().chat(runtime, _request(**bounds)))
            assert caught.value.safe_details["reason"] == reason
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_llama_provider_maps_timeout_and_oversized_headers_to_typed_failures() -> None:
    async def run_timeout() -> None:
        disconnected = asyncio.Event()

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                await reader.readuntil(b"\r\n\r\n")
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n")
                await writer.drain()
                await reader.read()
            finally:
                writer.close()
                with suppress(ConnectionError, OSError):
                    await writer.wait_closed()
                disconnected.set()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        runtime = _runtime(int(server.sockets[0].getsockname()[1]))
        try:
            with pytest.raises(ProviderStreamError) as caught:
                await _collect(LlamaCppProvider().chat(runtime, _request(timeout=1)))
            assert caught.value.safe_details["reason"] == "timeout"
            await asyncio.wait_for(disconnected.wait(), 1)
        finally:
            server.close()
            await server.wait_closed()

    async def run_headers() -> None:
        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(b"HTTP/1.1 200 OK\r\nX-Fill: " + (b"x" * 70_000))
            await writer.drain()
            writer.close()
            with suppress(ConnectionError, OSError):
                await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        runtime = _runtime(int(server.sockets[0].getsockname()[1]))
        try:
            with pytest.raises(ProviderStreamError) as caught:
                await _collect(LlamaCppProvider().chat(runtime, _request()))
            assert caught.value.safe_details["reason"] == "response_headers_too_large"
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run_timeout())
    asyncio.run(run_headers())


def test_llama_provider_cancellation_closes_the_http_stream() -> None:
    async def run() -> None:
        connected = asyncio.Event()
        disconnected = asyncio.Event()

        async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n")
            await writer.drain()
            connected.set()
            await reader.read()
            disconnected.set()
            writer.close()
            with suppress(ConnectionError, OSError):
                await writer.wait_closed()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        runtime = _runtime(int(server.sockets[0].getsockname()[1]))
        task = asyncio.create_task(_collect(LlamaCppProvider().chat(runtime, _request())))
        try:
            await connected.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.wait_for(disconnected.wait(), 1)
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(run())
