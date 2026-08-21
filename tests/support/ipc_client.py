from __future__ import annotations

import asyncio
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

from jarvis.ipc.codec import read_frame, write_frame
from jarvis.ipc.models import REQUEST_STREAM


class RawTestClient:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader = reader
        self.writer = writer
        self.hello: dict[str, object] | None = None

    @classmethod
    async def connect(
        cls,
        path: Path,
        *,
        optional_capabilities: Iterable[str] = (),
        resume: dict[str, object] | None = None,
    ) -> RawTestClient:
        reader, writer = await asyncio.open_unix_connection(path)
        client = cls(reader, writer)
        await client.send(
            {
                "type": "hello",
                "supported_versions": [1],
                "required_capabilities": [REQUEST_STREAM],
                "optional_capabilities": list(optional_capabilities),
                "client_name": "m002-test-client",
                "resume": resume,
            }
        )
        client.hello = await client.receive()
        return client

    async def send(self, value: dict[str, object]) -> None:
        await write_frame(self.writer, value)

    async def receive(self) -> dict[str, object]:
        return await read_frame(self.reader)

    async def request(
        self,
        *,
        request_id: str,
        operation: str,
        profile_id: str | None = None,
    ) -> list[dict[str, object]]:
        request: dict[str, object] = {
            "type": "request",
            "protocol_version": 1,
            "request_id": request_id,
            "operation": operation,
            "payload": {},
        }
        if profile_id is not None:
            request["profile_id"] = profile_id
        await self.send(request)
        events: list[dict[str, object]] = []
        while True:
            event = await self.receive()
            events.append(event)
            if event.get("terminal") is True or event.get("type") == "error":
                return events

    async def close(self) -> None:
        self.writer.close()
        # A peer is allowed to reject a pre-admission connection immediately.
        # CPython 3.12 reports that normal close as ECONNRESET for Unix sockets.
        with suppress(ConnectionError, OSError):
            await self.writer.wait_closed()
