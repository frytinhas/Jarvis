"""Implementation-neutral local LLM provider contract."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from jarvis.models.models import ModelId, ModelRuntimeConfig
from jarvis.profiles.models import ProfileId
from jarvis.runtimes.models import RuntimeHealthClass, RuntimeId, RuntimeState


class ProviderMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class ProviderMessage:
    role: ProviderMessageRole
    content: str
    provenance: str


@dataclass(frozen=True, slots=True)
class ProviderChatRequest:
    messages: tuple[ProviderMessage, ...]
    temperature: float
    top_p: float
    top_k: int
    min_p: float
    repeat_penalty: float
    generation_timeout_seconds: int
    request_id: str
    session_id: str
    turn_id: str
    max_delta_bytes: int
    max_sse_frame_bytes: int
    max_response_bytes: int


class ProviderStreamEventKind(StrEnum):
    TEXT_DELTA = "text_delta"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class ProviderStreamEvent:
    kind: ProviderStreamEventKind
    text: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutableIdentity:
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class ProcessEvidence:
    pid: int
    process_group_id: int
    boot_id: str
    start_ticks: int
    executable: ExecutableIdentity


@dataclass(frozen=True, slots=True)
class RuntimeSpecification:
    runtime_id: RuntimeId
    profile_id: ProfileId
    model_id: ModelId
    model_fd: int
    executable_path: Path
    executable_identity: ExecutableIdentity
    runtime_directory: Path
    host: str
    port: int
    api_key_path: Path
    api_key_fd: int
    api_key: str
    config: ModelRuntimeConfig
    stream_capture_bytes: int


@dataclass(slots=True)
class RuntimeHandle:
    runtime_id: RuntimeId
    profile_id: ProfileId
    model_id: ModelId
    process: asyncio.subprocess.Process
    evidence: ProcessEvidence
    host: str
    port: int
    api_key: str
    started_at_utc: str
    stdout_task: asyncio.Task[StreamSummary]
    stderr_task: asyncio.Task[StreamSummary]


@dataclass(frozen=True, slots=True)
class StreamSummary:
    stream: str
    byte_count: int
    dropped_bytes: int


@dataclass(frozen=True, slots=True)
class RuntimeHealth:
    state: RuntimeState
    health: RuntimeHealthClass
    reason_class: str | None = None


class LLMProvider(Protocol):
    async def start(self, specification: RuntimeSpecification) -> RuntimeHandle: ...

    async def health(self, runtime: RuntimeHandle, timeout_seconds: int) -> RuntimeHealth: ...

    async def stop(self, runtime: RuntimeHandle, timeout_seconds: int) -> None: ...

    def chat(
        self, runtime: RuntimeHandle, request: ProviderChatRequest
    ) -> AsyncIterator[ProviderStreamEvent]: ...


def close_model_descriptor(specification: RuntimeSpecification) -> None:
    with suppress(OSError):
        os.close(specification.model_fd)
