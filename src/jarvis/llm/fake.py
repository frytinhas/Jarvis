"""Barrier-controlled deterministic provider for runtime tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import cast

from jarvis.llm.provider import (
    ExecutableIdentity,
    ProcessEvidence,
    ProviderChatRequest,
    RuntimeHandle,
    RuntimeHealth,
    RuntimeSpecification,
    StreamSummary,
)
from jarvis.runtimes.models import RuntimeHealthClass, RuntimeState


@dataclass(slots=True)
class FakeLLMProvider:
    start_gate: asyncio.Event = field(default_factory=asyncio.Event)
    start_entered: asyncio.Event = field(default_factory=asyncio.Event)
    health_gate: asyncio.Event = field(default_factory=asyncio.Event)
    starts: list[RuntimeSpecification] = field(default_factory=list)
    stops: list[RuntimeSpecification] = field(default_factory=list)
    fail_start: bool = False
    fail_start_ownership: bool = False
    endpoint_failures: int = 0
    fail_stop_ownership: bool = False
    _specifications: dict[object, RuntimeSpecification] = field(default_factory=dict)
    _stopped: set[object] = field(default_factory=set)
    unhealthy: set[object] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.start_gate.set()
        self.health_gate.set()

    async def start(self, specification: RuntimeSpecification) -> RuntimeHandle:
        self.starts.append(specification)
        self.start_entered.set()
        await self.start_gate.wait()
        if self.endpoint_failures:
            from jarvis.runtimes.errors import RuntimeEndpointError

            self.endpoint_failures -= 1
            raise RuntimeEndpointError("fake_collision")
        if self.fail_start:
            from jarvis.runtimes.errors import RuntimeStartupError

            raise RuntimeStartupError("fake_failure")
        if self.fail_start_ownership:
            from jarvis.runtimes.errors import RuntimeOwnershipError

            raise RuntimeOwnershipError("fake_identity_mismatch")
        self._specifications[specification.runtime_id] = specification

        async def summary(name: str) -> StreamSummary:
            return StreamSummary(name, 0, 0)

        done = asyncio.create_task(summary("stdout"))
        process = cast(asyncio.subprocess.Process, object())
        return RuntimeHandle(
            specification.runtime_id,
            specification.profile_id,
            specification.model_id,
            process,
            ProcessEvidence(
                1, 1, "00000000-0000-4000-8000-000000000000", 1, ExecutableIdentity(1, 1)
            ),
            specification.host,
            specification.port,
            specification.api_key,
            "2026-08-21T00:00:00.000000Z",
            done,
            asyncio.create_task(summary("stderr")),
        )

    async def health(self, runtime: RuntimeHandle, timeout_seconds: int) -> RuntimeHealth:
        del timeout_seconds
        await self.health_gate.wait()
        if runtime.runtime_id in self._stopped:
            return RuntimeHealth(RuntimeState.STOPPED, RuntimeHealthClass.STOPPED)
        if runtime.runtime_id in self.unhealthy:
            return RuntimeHealth(RuntimeState.ERROR, RuntimeHealthClass.UNHEALTHY, "fake_crash")
        return RuntimeHealth(RuntimeState.READY, RuntimeHealthClass.HEALTHY)

    async def stop(self, runtime: RuntimeHandle, timeout_seconds: int) -> None:
        del timeout_seconds
        if self.fail_stop_ownership:
            from jarvis.runtimes.errors import RuntimeOwnershipError

            raise RuntimeOwnershipError("fake_identity_mismatch")
        self._stopped.add(runtime.runtime_id)
        self.stops.append(self._specifications[runtime.runtime_id])

    async def chat(self, runtime: RuntimeHandle, request: ProviderChatRequest) -> bytes:
        del runtime
        return request.payload


__all__ = ["FakeLLMProvider", "RuntimeHandle"]
