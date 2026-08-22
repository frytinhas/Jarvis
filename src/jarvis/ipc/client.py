"""Thin internal IPC client shared by future presentation clients."""

from __future__ import annotations

import asyncio
import errno
import time
from collections.abc import AsyncIterator, Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from jarvis.ipc.codec import read_frame, write_frame
from jarvis.ipc.errors import IpcError, ipc_error
from jarvis.ipc.models import (
    IPC_PROTOCOL_VERSION,
    REQUEST_STREAM,
    ConnectionId,
    CoreInstanceId,
    RequestId,
    ResumeProof,
)
from jarvis.profiles.models import ProfileId


@dataclass(frozen=True, slots=True)
class HandshakeResult:
    selected_version: int
    negotiated_capabilities: tuple[str, ...]
    core_instance_id: CoreInstanceId
    connection_id: ConnectionId
    resume_token: str
    state: str

    def resume_proof(self) -> ResumeProof:
        return ResumeProof(self.core_instance_id, self.connection_id, self.resume_token)


@dataclass(frozen=True, slots=True)
class ActivationPolicy:
    timeout_seconds: float = 8.0
    attempt_timeout_seconds: float = 2.0
    initial_delay_seconds: float = 0.025
    maximum_delay_seconds: float = 0.4

    def __post_init__(self) -> None:
        if (
            self.timeout_seconds <= 0
            or self.attempt_timeout_seconds <= 0
            or self.initial_delay_seconds <= 0
            or self.maximum_delay_seconds < self.initial_delay_seconds
        ):
            raise ValueError("invalid activation policy")


class JarvisIpcClient:
    def __init__(
        self,
        path: Path,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        handshake: HandshakeResult,
        required_capabilities: tuple[str, ...],
        optional_capabilities: tuple[str, ...],
    ) -> None:
        self.path = path
        self._reader = reader
        self._writer = writer
        self.handshake = handshake
        self._required_capabilities = required_capabilities
        self._optional_capabilities = optional_capabilities
        self._requests: dict[RequestId, asyncio.Queue[dict[str, object]]] = {}
        self._control: asyncio.Queue[dict[str, object]] = asyncio.Queue(1)
        self._pending_control_request: RequestId | None = None
        self._send_lock = asyncio.Lock()
        self._control_lock = asyncio.Lock()
        self._reader_task = asyncio.create_task(self._reader_loop())

    @classmethod
    async def connect_ready(
        cls,
        path: Path,
        *,
        required_capabilities: Iterable[str] = (REQUEST_STREAM,),
        optional_capabilities: Iterable[str] = (),
        client_name: str = "jarvis-internal-client",
        resume: ResumeProof | None = None,
        policy: ActivationPolicy | None = None,
    ) -> JarvisIpcClient:
        """Wait boundedly for socket activation; hello.ok is the readiness boundary."""

        active_policy = ActivationPolicy() if policy is None else policy
        deadline = time.monotonic() + active_policy.timeout_seconds
        delay = active_policy.initial_delay_seconds
        while True:
            try:
                return await asyncio.wait_for(
                    cls.connect(
                        path,
                        required_capabilities=required_capabilities,
                        optional_capabilities=optional_capabilities,
                        client_name=client_name,
                        resume=resume,
                    ),
                    timeout=min(
                        active_policy.attempt_timeout_seconds,
                        max(0.001, deadline - time.monotonic()),
                    ),
                )
            except IpcError as error:
                if error.code == "ipc.core_unavailable":
                    raise ipc_error(
                        "ipc.activation_unavailable", reason="hello_rejected"
                    ) from error
                if error.code in {
                    "ipc.invalid_message",
                    "ipc.capability_mismatch",
                    "ipc.version_mismatch",
                }:
                    raise ipc_error("ipc.activation_protocol_failed", cause=error.code) from error
                raise
            except PermissionError as error:
                raise ipc_error("ipc.activation_unavailable", reason="permission_denied") from error
            except OSError as error:
                if error.errno not in {errno.ENOENT, errno.ECONNREFUSED, errno.ECONNRESET}:
                    raise ipc_error("ipc.activation_unavailable", reason="transport") from error
            except TimeoutError:
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ipc_error("ipc.activation_timeout")
            await asyncio.sleep(min(delay, remaining))
            delay = min(active_policy.maximum_delay_seconds, delay * 2)

    @classmethod
    async def connect(
        cls,
        path: Path,
        *,
        required_capabilities: Iterable[str] = (REQUEST_STREAM,),
        optional_capabilities: Iterable[str] = (),
        client_name: str = "jarvis-internal-client",
        resume: ResumeProof | None = None,
    ) -> JarvisIpcClient:
        requirements = tuple(required_capabilities)
        options = tuple(optional_capabilities)
        reader, writer = await asyncio.open_unix_connection(path)
        resume_wire: dict[str, object] | None = None
        if resume is not None:
            resume_wire = {
                "expected_core_instance_id": str(resume.expected_core_instance_id),
                "connection_id": str(resume.connection_id),
                "resume_token": resume.resume_token,
            }
        await write_frame(
            writer,
            {
                "type": "hello",
                "supported_versions": [IPC_PROTOCOL_VERSION],
                "required_capabilities": list(requirements),
                "optional_capabilities": list(options),
                "client_name": client_name,
                "resume": resume_wire,
            },
        )
        response = await read_frame(reader)
        if response.get("type") != "hello.ok":
            writer.close()
            with suppress(ConnectionError, OSError):
                await writer.wait_closed()
            error = response.get("error")
            code = error.get("code") if isinstance(error, dict) else "ipc.core_unavailable"
            raise ipc_error(str(code))
        try:
            expected_fields = {
                "type",
                "selected_version",
                "negotiated_capabilities",
                "core_instance_id",
                "connection_id",
                "resume_token",
                "state",
            }
            if set(response) != expected_fields:
                raise ValueError("invalid hello fields")
            capabilities = response["negotiated_capabilities"]
            if not isinstance(capabilities, list) or not all(
                isinstance(item, str) for item in capabilities
            ):
                raise ValueError("invalid capabilities")
            selected_version = response["selected_version"]
            resume_token = response["resume_token"]
            state = response["state"]
            if (
                type(selected_version) is not int
                or selected_version != IPC_PROTOCOL_VERSION
                or not isinstance(resume_token, str)
                or not resume_token
                or not isinstance(state, str)
            ):
                raise ValueError("invalid selected version")
            handshake = HandshakeResult(
                selected_version=selected_version,
                negotiated_capabilities=tuple(capabilities),
                core_instance_id=CoreInstanceId.parse(str(response["core_instance_id"])),
                connection_id=ConnectionId.parse(str(response["connection_id"])),
                resume_token=resume_token,
                state=state,
            )
        except (KeyError, TypeError, ValueError) as error:
            writer.close()
            with suppress(ConnectionError, OSError):
                await writer.wait_closed()
            raise ipc_error("ipc.invalid_message", reason="invalid_hello_response") from error
        return cls(path, reader, writer, handshake, requirements, options)

    async def resume(self) -> JarvisIpcClient:
        return await self.connect_ready(
            self.path,
            required_capabilities=self._required_capabilities,
            optional_capabilities=self._optional_capabilities,
            resume=self.handshake.resume_proof(),
        )

    async def request(
        self,
        operation: str,
        *,
        payload: Mapping[str, object] | None = None,
        profile_id: ProfileId | None = None,
        request_id: RequestId | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        active_id = RequestId(uuid4()) if request_id is None else request_id
        if active_id in self._requests:
            raise ipc_error("ipc.request_id_conflict")
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(64)
        self._requests[active_id] = queue
        message: dict[str, object] = {
            "type": "request",
            "protocol_version": IPC_PROTOCOL_VERSION,
            "request_id": str(active_id),
            "operation": operation,
            "payload": dict(payload or {}),
        }
        if profile_id is not None:
            message["profile_id"] = str(profile_id)
        try:
            await self._send(message)
            while True:
                event = await queue.get()
                yield event
                if event.get("terminal") is True or event.get("type") == "error":
                    return
        finally:
            self._requests.pop(active_id, None)

    async def cancel(self, request_id: RequestId) -> dict[str, object]:
        return await self._control_call(
            {
                "type": "cancel",
                "protocol_version": IPC_PROTOCOL_VERSION,
                "request_id": str(request_id),
            },
            expected="cancel.result",
        )

    async def status(self, request_id: RequestId) -> dict[str, object]:
        return await self._control_call(
            {
                "type": "request.status",
                "protocol_version": IPC_PROTOCOL_VERSION,
                "request_id": str(request_id),
            },
            expected="request.status.result",
        )

    async def replay(self, request_id: RequestId, *, after_sequence: int) -> dict[str, object]:
        return await self._control_call(
            {
                "type": "replay",
                "protocol_version": IPC_PROTOCOL_VERSION,
                "request_id": str(request_id),
                "after_sequence": after_sequence,
            },
            expected="replay.result",
        )

    async def attach(
        self, request_id: RequestId, *, after_sequence: int
    ) -> AsyncIterator[dict[str, object]]:
        """Replay retained events, then follow the same Core-owned request.

        The queue is registered before replay so an event emitted during the
        replay round trip cannot be lost. Sequence de-duplication reconciles
        the retained snapshot with events concurrently delivered to the queue.
        """

        if after_sequence < 0:
            raise ipc_error("ipc.invalid_message", reason="invalid_after_sequence")
        if request_id in self._requests:
            raise ipc_error("ipc.request_id_conflict")
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(64)
        self._requests[request_id] = queue
        latest = after_sequence
        try:
            replay = await self.replay(request_id, after_sequence=after_sequence)
            events = replay.get("events")
            status = replay.get("request")
            if not isinstance(events, list) or not isinstance(status, dict):
                raise ipc_error("ipc.invalid_message", reason="invalid_replay_response")
            for event in events:
                if not isinstance(event, dict):
                    raise ipc_error("ipc.invalid_message", reason="invalid_replay_event")
                sequence = event.get("sequence")
                if type(sequence) is not int or sequence <= latest:
                    if type(sequence) is int and sequence <= latest:
                        continue
                    raise ipc_error("ipc.invalid_message", reason="invalid_replay_sequence")
                latest = sequence
                yield event
                if event.get("terminal") is True:
                    return
            if status.get("terminal") is True:
                return
            while True:
                event = await queue.get()
                sequence = event.get("sequence")
                if type(sequence) is int:
                    if sequence <= latest:
                        continue
                    latest = sequence
                yield event
                if event.get("terminal") is True or event.get("type") == "error":
                    return
        finally:
            self._requests.pop(request_id, None)

    async def _control_call(
        self, message: dict[str, object], *, expected: str
    ) -> dict[str, object]:
        async with self._control_lock:
            request_id = RequestId.parse(str(message["request_id"]))
            self._pending_control_request = request_id
            try:
                await self._send(message)
                response = await self._control.get()
                if response.get("type") == "error":
                    error = response.get("error")
                    code = error.get("code") if isinstance(error, dict) else "ipc.internal_error"
                    raise ipc_error(str(code))
                if response.get("type") != expected:
                    raise ipc_error("ipc.invalid_message", reason="unexpected_control_response")
                return response
            finally:
                self._pending_control_request = None

    async def _send(self, message: dict[str, object]) -> None:
        async with self._send_lock:
            await write_frame(self._writer, message)

    async def _reader_loop(self) -> None:
        try:
            while True:
                message = await read_frame(self._reader, timeout=300.0)
                request_raw = message.get("request_id")
                try:
                    request_id = RequestId.parse(str(request_raw))
                except (ValueError, TypeError):
                    request_id = None
                if message.get("type") == "error" and request_id == self._pending_control_request:
                    await self._control.put(message)
                    continue
                if request_id is not None and message.get("type") in {"event", "error"}:
                    queue = self._requests.get(request_id)
                    if queue is not None:
                        await queue.put(message)
                        continue
                await self._control.put(message)
        except (IpcError, ConnectionError, asyncio.CancelledError):
            unavailable: dict[str, object] = {
                "type": "error",
                "error": IpcError(
                    code="ipc.core_unavailable",
                    message_key="error.ipc.core_unavailable",
                ).to_safe_dict(),
            }
            for queue in tuple(self._requests.values()):
                await queue.put(unavailable)
            if self._control.empty():
                self._control.put_nowait(unavailable)

    async def close(self) -> None:
        self._reader_task.cancel()
        await asyncio.gather(self._reader_task, return_exceptions=True)
        self._writer.close()
        with suppress(ConnectionError, OSError):
            await self._writer.wait_closed()
