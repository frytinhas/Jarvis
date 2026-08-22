from __future__ import annotations

import asyncio
import errno
from pathlib import Path

import pytest

from jarvis.ipc.client import ActivationPolicy, JarvisIpcClient
from jarvis.ipc.errors import IpcError, ipc_error

pytestmark = pytest.mark.unit


def test_activation_connector_retries_until_protocol_hello(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    attempts = 0

    async def connect(*_args: object, **_kwargs: object) -> object:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise OSError(errno.ENOENT, "not active")
        return sentinel

    monkeypatch.setattr(JarvisIpcClient, "connect", connect)

    async def scenario() -> None:
        result = await JarvisIpcClient.connect_ready(
            Path("/tmp/test.sock"),
            policy=ActivationPolicy(0.2, 0.05, 0.001, 0.002),
        )
        assert result is sentinel

    asyncio.run(scenario())
    assert attempts == 3


def test_activation_connector_types_protocol_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def connect(*_args: object, **_kwargs: object) -> object:
        raise ipc_error("ipc.invalid_message")

    monkeypatch.setattr(JarvisIpcClient, "connect", connect)
    with pytest.raises(IpcError, match="ipc.activation_protocol_failed"):
        asyncio.run(
            JarvisIpcClient.connect_ready(
                Path("/tmp/test.sock"),
                policy=ActivationPolicy(0.05, 0.01, 0.001, 0.002),
            )
        )
