"""Async Unix-socket server, session handling, and M002 operation routing."""

from __future__ import annotations

import asyncio
import hmac
import os
import secrets
import socket
import struct
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from jarvis.config.defaults import DefaultsSnapshot
from jarvis.core.lifecycle import CoreLifecycle, CoreLifecycleState
from jarvis.core.requests import IpcEvent, RequestContext, RequestRegistry
from jarvis.diagnostics.events import InfrastructureEvent, Severity
from jarvis.diagnostics.sink import InfrastructureDiagnosticSink
from jarvis.foundation.clock import Clock
from jarvis.foundation.identifiers import IdGenerator
from jarvis.ipc.codec import encode_frame, read_frame
from jarvis.ipc.errors import IpcError, ipc_error
from jarvis.ipc.models import (
    CORE_CONTROL,
    CORE_HEALTH,
    EVENT_REPLAY,
    IPC_PROTOCOL_VERSION,
    PROFILE_CATALOG,
    REQUEST_CANCEL,
    SERVER_CAPABILITIES,
    SESSION_RESUME,
    ConnectionId,
    CoreInstanceId,
    IpcRequest,
    ProtocolIdGenerator,
    RandomProtocolIdGenerator,
    negotiate,
    parse_control_request,
    parse_hello,
    parse_replay_request,
    parse_request,
    safe_error_payload,
)
from jarvis.profiles.models import Profile
from jarvis.profiles.service import ProfileService

MAX_CONNECTIONS = 32
MAX_LOGICAL_SESSIONS = 128
MAX_OUTBOUND_FRAMES = 64
MAX_OUTBOUND_BYTES = 2 * 1024 * 1024
IDLE_TIMEOUT_SECONDS = 300.0
DRAIN_TIMEOUT_SECONDS = 5.0
DISCONNECTED_SESSION_RETENTION_SECONDS = 60.0

Handler = Callable[[RequestContext], Awaitable[Mapping[str, object]]]
ShutdownCallback = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class _Outbound:
    data: bytes
    fence: asyncio.Future[None]


class ClientTransport:
    def __init__(self, writer: asyncio.StreamWriter) -> None:
        self.writer = writer
        self.queue: asyncio.Queue[_Outbound | None] = asyncio.Queue(MAX_OUTBOUND_FRAMES)
        self._queued_bytes = 0
        self._queue_lock = asyncio.Lock()
        self._closed = False
        self._writer_task = asyncio.create_task(self._writer_loop())

    async def send(self, value: Mapping[str, object]) -> None:
        data = encode_frame(value)
        loop = asyncio.get_running_loop()
        fence: asyncio.Future[None] = loop.create_future()
        async with self._queue_lock:
            if self._closed:
                raise ipc_error("ipc.core_unavailable", reason="transport_closed")
            if self.queue.full() or self._queued_bytes + len(data) > MAX_OUTBOUND_BYTES:
                await self._mark_closed()
                raise ipc_error("ipc.connection_limit", reason="outbound_backpressure")
            self._queued_bytes += len(data)
            self.queue.put_nowait(_Outbound(data, fence))
        await fence

    async def _writer_loop(self) -> None:
        try:
            while True:
                item = await self.queue.get()
                if item is None:
                    return
                try:
                    self.writer.write(item.data)
                    await asyncio.wait_for(self.writer.drain(), DRAIN_TIMEOUT_SECONDS)
                    if not item.fence.done():
                        item.fence.set_result(None)
                except BaseException as error:
                    if not item.fence.done():
                        item.fence.set_exception(
                            ipc_error("ipc.core_unavailable", reason="transport_write_failed")
                        )
                    raise error
                finally:
                    async with self._queue_lock:
                        self._queued_bytes -= len(item.data)
        except BaseException:
            await self._mark_closed()

    async def _mark_closed(self) -> None:
        if self._closed:
            return
        self._closed = True
        while not self.queue.empty():
            item = self.queue.get_nowait()
            if item is not None and not item.fence.done():
                item.fence.set_exception(
                    ipc_error("ipc.core_unavailable", reason="transport_closed")
                )
        self.writer.close()

    async def close(self) -> None:
        await self._mark_closed()
        if asyncio.current_task() is not self._writer_task:
            self._writer_task.cancel()
            await asyncio.gather(self._writer_task, return_exceptions=True)
        with suppress(ConnectionError, OSError):
            await self.writer.wait_closed()


@dataclass(slots=True)
class LogicalSession:
    connection_id: ConnectionId
    capabilities: frozenset[str]
    resume_token: str
    transport: ClientTransport | None
    tasks: set[asyncio.Task[None]] = field(default_factory=set)
    expiry_task: asyncio.Task[None] | None = None


class IpcServer:
    def __init__(
        self,
        *,
        listener: socket.socket,
        core_instance_id: CoreInstanceId,
        lifecycle: CoreLifecycle,
        profiles: ProfileService,
        defaults: DefaultsSnapshot,
        started_at_utc: str,
        shutdown_callback: ShutdownCallback,
        protocol_ids: ProtocolIdGenerator | None = None,
        handlers: Mapping[str, Handler] | None = None,
        diagnostics: InfrastructureDiagnosticSink | None = None,
        clock: Clock | None = None,
        event_ids: IdGenerator | None = None,
    ) -> None:
        self._listener = listener
        self.core_instance_id = core_instance_id
        self.lifecycle = lifecycle
        self.profiles = profiles
        self.defaults = defaults
        self.started_at_utc = started_at_utc
        self.shutdown_callback = shutdown_callback
        self.protocol_ids = RandomProtocolIdGenerator() if protocol_ids is None else protocol_ids
        self.handlers = dict(handlers or {})
        self.diagnostics = diagnostics
        self.clock = clock
        self.event_ids = event_ids
        self.registry = RequestRegistry(core_instance_id)
        self._server: asyncio.AbstractServer | None = None
        self._sessions: dict[ConnectionId, LogicalSession] = {}
        self._connection_lock = asyncio.Lock()
        self._connected_transports = 0
        self._all_tasks: set[asyncio.Task[None]] = set()

    @property
    def active_connections(self) -> int:
        return self._connected_transports

    async def start(self) -> None:
        self._server = await asyncio.start_unix_server(self._accept, sock=self._listener)

    async def stop_accepting(self) -> None:
        if self._server is not None:
            self._server.close()

    async def close(self) -> None:
        await self.stop_accepting()
        tasks = tuple(self._all_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        transports = [s.transport for s in self._sessions.values() if s.transport is not None]
        for transport in transports:
            assert transport is not None
            await transport.close()
        if self._server is not None:
            await self._server.wait_closed()
        expiry_tasks = [
            session.expiry_task
            for session in self._sessions.values()
            if session.expiry_task is not None
        ]
        for expiry_task in expiry_tasks:
            assert expiry_task is not None
            expiry_task.cancel()
        if expiry_tasks:
            await asyncio.gather(*expiry_tasks, return_exceptions=True)
        self._sessions.clear()

    async def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        transport = ClientTransport(writer)
        session: LogicalSession | None = None
        admitted = False
        try:
            async with self._connection_lock:
                if self._connected_transports >= MAX_CONNECTIONS:
                    raise ipc_error("ipc.connection_limit")
                self._connected_transports += 1
                admitted = True
            peer_pid, peer_uid, _peer_gid = self._validate_peer(writer)
            self._diagnose("ipc.connection_accepted", {"peer_pid": peer_pid, "peer_uid": peer_uid})
            hello = parse_hello(await read_frame(reader))
            version, capabilities = negotiate(hello)
            if hello.resume is None:
                connection_id = self.protocol_ids.new_connection_id()
                new_session = LogicalSession(
                    connection_id=connection_id,
                    capabilities=frozenset(capabilities),
                    resume_token=secrets.token_urlsafe(32),
                    transport=transport,
                )
                async with self._connection_lock:
                    if len(self._sessions) >= MAX_LOGICAL_SESSIONS:
                        raise ipc_error("ipc.connection_limit", reason="logical_session_limit")
                    if connection_id in self._sessions:
                        raise ipc_error("ipc.core_unavailable", reason="connection_id_collision")
                    self._sessions[connection_id] = new_session
                    session = new_session
            else:
                if SESSION_RESUME not in capabilities:
                    raise ipc_error("ipc.resume_unavailable", reason="resume_not_negotiated")
                session = await self._resume_session(hello.resume, transport)
                connection_id = session.connection_id
                capabilities = tuple(sorted(session.capabilities))
            await transport.send(
                {
                    "type": "hello.ok",
                    "selected_version": version,
                    "negotiated_capabilities": list(capabilities),
                    "core_instance_id": str(self.core_instance_id),
                    "connection_id": str(connection_id),
                    "resume_token": session.resume_token,
                    "state": self.lifecycle.state.value,
                }
            )
            await self._read_loop(reader, session)
        except IpcError as error:
            self._diagnose("ipc.internal_failure", {"reason_code": error.code})
            with suppress(IpcError):
                await transport.send(
                    {"type": "hello.error", "error": error.to_safe_dict()}
                    if session is None
                    else {"type": "error", "error": error.to_safe_dict()}
                )
        except BaseException:
            with suppress(IpcError):
                await transport.send({"type": "error", "error": safe_error_payload(RuntimeError())})
        finally:
            if session is not None and session.transport is transport:
                session.transport = None
                self._schedule_expiry(session)
            if admitted:
                async with self._connection_lock:
                    self._connected_transports -= 1
            await transport.close()
            self._diagnose("ipc.connection_closed", {})

    async def _resume_session(self, proof: object, transport: ClientTransport) -> LogicalSession:
        from jarvis.ipc.models import ResumeProof

        assert isinstance(proof, ResumeProof)
        if proof.expected_core_instance_id != self.core_instance_id:
            raise ipc_error("ipc.resume_unavailable", reason="core_instance_changed")
        async with self._connection_lock:
            session = self._sessions.get(proof.connection_id)
            if session is None or not hmac.compare_digest(
                proof.resume_token.encode("utf-8"), session.resume_token.encode("utf-8")
            ):
                raise ipc_error("ipc.resume_unavailable", reason="invalid_resume")
            previous = session.transport
            session.resume_token = secrets.token_urlsafe(32)
            session.transport = transport
            if session.expiry_task is not None:
                session.expiry_task.cancel()
                session.expiry_task = None
        if previous is not None and previous is not transport:
            await previous.close()
        return session

    def _validate_peer(self, writer: asyncio.StreamWriter) -> tuple[int, int, int]:
        raw_socket: Any = writer.get_extra_info("socket")
        if raw_socket is None or not hasattr(socket, "SO_PEERCRED"):
            raise ipc_error("ipc.core_unavailable", reason="peer_credentials_unavailable")
        try:
            credentials = raw_socket.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            pid, uid, gid = struct.unpack("3i", credentials)
        except (OSError, struct.error, TypeError) as error:
            raise ipc_error("ipc.core_unavailable", reason="peer_credentials_invalid") from error
        if uid != os.getuid():
            raise ipc_error("ipc.core_unavailable", reason="peer_uid_mismatch")
        return pid, uid, gid

    async def _read_loop(self, reader: asyncio.StreamReader, session: LogicalSession) -> None:
        while True:
            try:
                message = await read_frame(reader, timeout=IDLE_TIMEOUT_SECONDS)
            except IpcError:
                raise
            message_type = message.get("type")
            if message_type == "request":
                await self._receive_request(session, message)
            elif message_type == "cancel":
                await self._receive_cancel(session, message)
            elif message_type == "replay":
                await self._receive_replay(session, message)
            elif message_type == "request.status":
                await self._receive_status(session, message)
            else:
                raise ipc_error("ipc.invalid_message", reason="unknown_message_type")

    async def _receive_request(
        self, session: LogicalSession, message: Mapping[str, object]
    ) -> None:
        try:
            request = parse_request(message)
            self._validate_operation(request, session)
        except IpcError as error:
            await self._send_unsequenced(session, message.get("request_id", "invalid"), error)
            return
        if self.lifecycle.state is not CoreLifecycleState.READY:
            raise ipc_error("ipc.core_shutting_down")
        try:
            context = await self.registry.accept(request, session.connection_id)
        except IpcError as error:
            await self._send_unsequenced(session, request.request_id, error)
            return
        await self._send_event(session, context.events[0])
        self._diagnose(
            "ipc.request_accepted",
            {"request_id": str(context.request_id), "operation": context.request.operation},
        )
        task = asyncio.create_task(self._run_request(session, context))
        session.tasks.add(task)
        self._all_tasks.add(task)
        task.add_done_callback(session.tasks.discard)
        task.add_done_callback(self._all_tasks.discard)

    def _validate_operation(self, request: IpcRequest, session: LogicalSession) -> None:
        if request.operation in self.handlers:
            return
        operations = {"core.health", "profiles.list", "profiles.get", "core.shutdown"}
        if request.operation not in operations:
            raise ipc_error("ipc.operation_not_supported", operation=request.operation)
        if request.payload:
            raise ipc_error("ipc.invalid_message", reason="payload_must_be_empty")
        if request.operation == "profiles.get":
            if request.profile_id is None:
                raise ipc_error("ipc.invalid_message", reason="profile_id_required")
        elif request.profile_id is not None:
            raise ipc_error("ipc.invalid_message", reason="profile_id_forbidden")
        if request.operation == "core.shutdown" and CORE_CONTROL not in session.capabilities:
            raise ipc_error("ipc.capability_mismatch", reason="core_control_not_negotiated")
        if request.operation == "core.health" and CORE_HEALTH not in session.capabilities:
            raise ipc_error("ipc.capability_mismatch", reason="core_health_not_negotiated")
        if (
            request.operation.startswith("profiles.")
            and PROFILE_CATALOG not in session.capabilities
        ):
            raise ipc_error("ipc.capability_mismatch", reason="profile_catalog_not_negotiated")

    async def _run_request(self, session: LogicalSession, context: RequestContext) -> None:
        try:
            started = await self.registry.start(context)
            if started is None:
                return
            await self._send_event_if_attached(session, started)
            self._diagnose("ipc.request_started", {"request_id": str(context.request_id)})
            result = await self._dispatch(context)
            terminal = await self.registry.complete(context, result)
            if terminal is not None:
                if context.request.operation == "core.shutdown":
                    try:
                        await self._send_event_if_attached(session, terminal)
                    finally:
                        # A disconnected or stalled requester cannot strand an already accepted,
                        # terminal shutdown request. Healthy transports still drain first.
                        await self.shutdown_callback()
                else:
                    await self._send_event_if_attached(session, terminal)
                self._diagnose(
                    "ipc.request_terminal",
                    {
                        "request_id": str(context.request_id),
                        "event_type": terminal.event_type,
                        "sequence": terminal.sequence,
                    },
                )
        except asyncio.CancelledError:
            terminal = await self.registry.fail(context, ipc_error("ipc.core_shutting_down"))
            if terminal is not None:
                await self._send_event_if_attached(session, terminal)
            raise
        except BaseException as error:
            terminal = await self.registry.fail(context, error)
            if terminal is not None:
                await self._send_event_if_attached(session, terminal)
        finally:
            if session.transport is None:
                self._schedule_expiry(session)

    async def _dispatch(self, context: RequestContext) -> Mapping[str, object]:
        operation = context.request.operation
        if operation in self.handlers:
            return await self.handlers[operation](context)
        if operation == "core.health":
            return self._health()
        if operation == "profiles.list":
            profiles = await asyncio.to_thread(self.profiles.list_profiles)
            return {"profiles": [_profile_wire(item.profile) for item in profiles]}
        if operation == "profiles.get":
            assert context.request.profile_id is not None
            profile = await asyncio.to_thread(self.profiles.get_profile, context.request.profile_id)
            return {"profile": _profile_wire(profile.profile)}
        if operation == "core.shutdown":
            return {"shutdown_scheduled": True}
        raise ipc_error("ipc.operation_not_supported", operation=operation)

    def _health(self) -> dict[str, object]:
        return {
            "state": self.lifecycle.state.value,
            "core_instance_id": str(self.core_instance_id),
            "pid": os.getpid(),
            "started_at_utc": self.started_at_utc,
            "protocol_version": IPC_PROTOCOL_VERSION,
            "capabilities": sorted(SERVER_CAPABILITIES),
            "active_connections": self.active_connections,
            "in_flight_requests": self.registry.in_flight_count,
            "database_schema_version": 2,
            "defaults_schema_version": self.defaults.defaults_schema_version,
            "product_defaults_version": self.defaults.product_defaults_version,
        }

    async def _receive_cancel(self, session: LogicalSession, message: Mapping[str, object]) -> None:
        try:
            request_id = parse_control_request(message, "cancel")
            if REQUEST_CANCEL not in session.capabilities:
                raise ipc_error("ipc.capability_mismatch", reason="cancel_not_negotiated")
        except IpcError as error:
            await self._send_unsequenced(session, message.get("request_id", "invalid"), error)
            return
        try:
            context = await self.registry.get_owned(request_id, session.connection_id)
            previous_events = len(context.events)
            outcome = await self.registry.cancel(request_id, session.connection_id)
            await self._transport(session).send(
                {
                    "type": "cancel.result",
                    "protocol_version": IPC_PROTOCOL_VERSION,
                    "request_id": str(request_id),
                    "outcome": outcome.value,
                }
            )
            if len(context.events) > previous_events:
                await self._send_event_if_attached(session, context.events[-1])
                self._diagnose("ipc.request_cancelled", {"request_id": str(request_id)})
        except IpcError as error:
            await self._send_unsequenced(session, request_id, error)

    async def _receive_status(self, session: LogicalSession, message: Mapping[str, object]) -> None:
        try:
            request_id = parse_control_request(message, "request.status")
            status = await self.registry.status(request_id, session.connection_id)
            await self._transport(session).send(
                {
                    "type": "request.status.result",
                    "protocol_version": IPC_PROTOCOL_VERSION,
                    "request": status,
                }
            )
        except IpcError as error:
            await self._send_unsequenced(session, message.get("request_id", "invalid"), error)

    async def _receive_replay(self, session: LogicalSession, message: Mapping[str, object]) -> None:
        try:
            if EVENT_REPLAY not in session.capabilities:
                raise ipc_error("ipc.capability_mismatch", reason="replay_not_negotiated")
            request_id, after = parse_replay_request(message)
            events = await self.registry.replay(request_id, session.connection_id, after)
            status = await self.registry.status(request_id, session.connection_id)
            await self._transport(session).send(
                {
                    "type": "replay.result",
                    "protocol_version": IPC_PROTOCOL_VERSION,
                    "request_id": str(request_id),
                    "after_sequence": after,
                    "events": [event.to_wire() for event in events],
                    "request": status,
                }
            )
        except IpcError as error:
            await self._send_unsequenced(session, message.get("request_id", "invalid"), error)

    def _schedule_expiry(self, session: LogicalSession) -> None:
        if session.expiry_task is not None and not session.expiry_task.done():
            return
        session.expiry_task = asyncio.create_task(self._expire_session(session))

    async def _expire_session(self, session: LogicalSession) -> None:
        await asyncio.sleep(DISCONNECTED_SESSION_RETENTION_SECONDS)
        if session.transport is not None:
            return
        if await self.registry.owner_has_active(session.connection_id):
            session.expiry_task = None
            return
        async with self._connection_lock:
            if session.transport is None:
                self._sessions.pop(session.connection_id, None)
                await self.registry.discard_owner(session.connection_id)

    def _diagnose(self, event_type: str, fields: dict[str, object]) -> None:
        if self.diagnostics is None or self.clock is None or self.event_ids is None:
            return
        self.diagnostics.emit(
            InfrastructureEvent(
                event_id=self.event_ids.new_event_id(),
                timestamp_utc=self.clock.now(),
                event_type=event_type,
                subsystem="ipc.server",
                severity=Severity.INFO,
                fields=fields,
            )
        )

    async def _send_unsequenced(
        self, session: LogicalSession, request_id: object, error: IpcError
    ) -> None:
        await self._transport(session).send(
            {
                "type": "error",
                "protocol_version": IPC_PROTOCOL_VERSION,
                "request_id": str(request_id),
                "error": error.to_safe_dict(),
            }
        )

    async def _send_event(self, session: LogicalSession, event: IpcEvent) -> None:
        await self._transport(session).send(event.to_wire())

    async def _send_event_if_attached(self, session: LogicalSession, event: IpcEvent) -> None:
        if session.transport is not None:
            await session.transport.send(event.to_wire())

    @staticmethod
    def _transport(session: LogicalSession) -> ClientTransport:
        if session.transport is None:
            raise ipc_error("ipc.core_unavailable", reason="transport_detached")
        return session.transport


def _profile_wire(profile: Profile) -> dict[str, object]:
    return {
        "profile_id": str(profile.profile_id),
        "kind": profile.kind.value,
        "display_name": profile.display_name,
        "command_alias": profile.command_alias,
        "identity_revision": profile.identity_revision,
    }
