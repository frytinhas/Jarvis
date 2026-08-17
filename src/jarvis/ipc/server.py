"""Async Unix-socket server, session handling, and M002 operation routing."""

from __future__ import annotations

import asyncio
import hmac
import os
import re
import secrets
import socket
import struct
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field, replace
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
    PROFILE_MANAGEMENT,
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
from jarvis.profiles.configuration import (
    AppearanceConfiguration,
    ProfileConfigurationValues,
    UpdateProfileConfiguration,
    section_value,
)
from jarvis.profiles.destructive import (
    ConfirmDestructiveOperation,
    DeletionScope,
    DestructiveOperationKind,
    DestructiveTarget,
    OperationId,
    ResetScope,
)
from jarvis.profiles.models import (
    Capability,
    ConfigurationSection,
    CreateProfile,
    PermissionDecision,
    Profile,
    RenameProfile,
    VisibleLoggingMode,
)
from jarvis.profiles.names import MAX_ALIAS_LENGTH, MAX_DISPLAY_NAME_BYTES
from jarvis.profiles.service import ProfileConfigService, ProfileService

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
        profile_configuration: ProfileConfigService,
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
        self.profile_configuration = profile_configuration
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
        # Do not create a writer task until the physical transport has been
        # admitted.  Otherwise a connection flood can create unbounded short-lived
        # writer tasks before the connection cap has any effect.
        transport: ClientTransport | None = None
        session: LogicalSession | None = None
        admitted = False
        try:
            peer_pid, peer_uid, _peer_gid = self._validate_peer(writer)
            async with self._connection_lock:
                if self._connected_transports >= MAX_CONNECTIONS:
                    raise ipc_error("ipc.connection_limit")
                self._connected_transports += 1
                admitted = True
            transport = ClientTransport(writer)
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
            await self._read_loop(reader, session, transport)
        except IpcError as error:
            self._diagnose("ipc.internal_failure", {"reason_code": error.code})
            with suppress(IpcError):
                response = (
                    {"type": "hello.error", "error": error.to_safe_dict()}
                    if session is None
                    else {"type": "error", "error": error.to_safe_dict()}
                )
                if transport is None:
                    await self._send_direct(writer, response)
                else:
                    await transport.send(response)
        except BaseException:
            if transport is not None:
                with suppress(IpcError):
                    await transport.send(
                        {"type": "error", "error": safe_error_payload(RuntimeError())}
                    )
        finally:
            if session is not None and session.transport is transport:
                session.transport = None
                self._schedule_expiry(session)
            if admitted:
                async with self._connection_lock:
                    self._connected_transports -= 1
            if transport is not None:
                await transport.close()
            else:
                writer.close()
                with suppress(ConnectionError, OSError):
                    await writer.wait_closed()
            self._diagnose("ipc.connection_closed", {})

    @staticmethod
    async def _send_direct(writer: asyncio.StreamWriter, value: Mapping[str, object]) -> None:
        """Send a bounded pre-admission error without allocating a writer task."""

        writer.write(encode_frame(value))
        with suppress(ConnectionError, TimeoutError):
            await asyncio.wait_for(writer.drain(), DRAIN_TIMEOUT_SECONDS)

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

    async def _read_loop(
        self,
        reader: asyncio.StreamReader,
        session: LogicalSession,
        transport: ClientTransport,
    ) -> None:
        while True:
            try:
                message = await read_frame(reader, timeout=IDLE_TIMEOUT_SECONDS)
            except IpcError:
                raise
            # A successful resume atomically replaces the only attached physical
            # transport.  Discard bytes buffered on the displaced transport so it
            # cannot issue operations under the resumed logical session.
            if session.transport is not transport:
                return
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
        operations = {
            "core.health",
            "profiles.list",
            "profiles.get",
            "core.shutdown",
            "profiles.resolve_alias",
            "profiles.create",
            "profiles.rename",
            "profiles.configuration.section.get",
            "profiles.configuration.section.update",
            "profiles.reset.preview",
            "profiles.reset.confirm",
            "profiles.delete.preview",
            "profiles.delete.confirm",
        }
        if request.operation not in operations:
            raise ipc_error("ipc.operation_not_supported", operation=request.operation)
        if (
            request.operation in {"core.health", "profiles.list", "profiles.get", "core.shutdown"}
            and request.payload
        ):
            raise ipc_error("ipc.invalid_message", reason="payload_must_be_empty")
        profile_operations = {
            "profiles.get",
            "profiles.rename",
            "profiles.configuration.section.get",
            "profiles.configuration.section.update",
            "profiles.reset.preview",
            "profiles.reset.confirm",
            "profiles.delete.preview",
            "profiles.delete.confirm",
        }
        if request.operation in profile_operations:
            if request.profile_id is None:
                raise ipc_error("ipc.invalid_message", reason="profile_id_required")
        elif request.profile_id is not None:
            raise ipc_error("ipc.invalid_message", reason="profile_id_forbidden")
        if request.operation == "core.shutdown" and CORE_CONTROL not in session.capabilities:
            raise ipc_error("ipc.capability_mismatch", reason="core_control_not_negotiated")
        if request.operation == "core.health" and CORE_HEALTH not in session.capabilities:
            raise ipc_error("ipc.capability_mismatch", reason="core_health_not_negotiated")
        if (
            request.operation in {"profiles.list", "profiles.get"}
            and PROFILE_CATALOG not in session.capabilities
        ):
            raise ipc_error("ipc.capability_mismatch", reason="profile_catalog_not_negotiated")
        if (
            request.operation.startswith("profiles.")
            and request.operation not in {"profiles.list", "profiles.get"}
            and PROFILE_MANAGEMENT not in session.capabilities
        ):
            raise ipc_error("ipc.capability_mismatch", reason="profile_management_not_negotiated")
        if request.operation.startswith("profiles.") and request.operation not in {
            "profiles.list",
            "profiles.get",
        }:
            _validate_management_payload(request)

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
        if operation == "profiles.resolve_alias":
            _exact_payload(context.request.payload, {"command_alias"})
            alias = _payload_text(
                context.request.payload, "command_alias", max_bytes=MAX_ALIAS_LENGTH
            )
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", alias):
                raise ipc_error("ipc.invalid_message", reason="invalid_command_alias")
            profile = await asyncio.to_thread(self.profiles.resolve_alias, alias)
            return {"profile": _profile_wire(profile.profile)}
        if operation == "profiles.create":
            _exact_payload(context.request.payload, {"display_name"})
            display_name = _payload_text(
                context.request.payload, "display_name", max_bytes=MAX_DISPLAY_NAME_BYTES
            )
            aggregate = await asyncio.to_thread(
                self.profiles.create_profile, CreateProfile(display_name)
            )
            return {"profile": _profile_wire(aggregate.profile)}
        if operation == "profiles.rename":
            assert context.request.profile_id is not None
            _exact_payload(context.request.payload, {"display_name", "expected_identity_revision"})
            display_name = _payload_text(
                context.request.payload, "display_name", max_bytes=MAX_DISPLAY_NAME_BYTES
            )
            revision = _payload_positive_int(context.request.payload, "expected_identity_revision")
            result = await asyncio.to_thread(
                self.profiles.rename_profile,
                RenameProfile(context.request.profile_id, display_name, revision),
            )
            return {"profile": _profile_wire(result.profile)}
        if operation == "profiles.configuration.section.get":
            assert context.request.profile_id is not None
            _exact_payload(context.request.payload, {"section"})
            section = _payload_section(context.request.payload)
            if section is ConfigurationSection.STARTUP:
                raise ipc_error("ipc.operation_not_supported", operation=operation)
            aggregate = await asyncio.to_thread(
                self.profiles.get_profile, context.request.profile_id
            )
            return _section_wire(
                section_value(aggregate.configuration.values, section),
                section,
                aggregate.profile.identity_revision,
                aggregate.configuration.configuration_revision,
                aggregate.configuration.section_revisions[section].revision,
            )
        if operation == "profiles.configuration.section.update":
            assert context.request.profile_id is not None
            _exact_payload(
                context.request.payload,
                {
                    "section",
                    "value",
                    "expected_identity_revision",
                    "expected_configuration_revision",
                },
            )
            section = _payload_section(context.request.payload)
            if section is ConfigurationSection.STARTUP:
                raise ipc_error("ipc.operation_not_supported", operation=operation)
            identity_revision = _payload_positive_int(
                context.request.payload, "expected_identity_revision"
            )
            configuration_revision = _payload_positive_int(
                context.request.payload, "expected_configuration_revision"
            )
            current = await asyncio.to_thread(
                self.profile_configuration.get_configuration, context.request.profile_id
            )
            values = _replace_section(current.values, section, context.request.payload.get("value"))
            updated = await asyncio.to_thread(
                self.profile_configuration.update_configuration,
                UpdateProfileConfiguration(
                    context.request.profile_id, identity_revision, configuration_revision, values
                ),
            )
            return _section_wire(
                section_value(updated.values, section),
                section,
                identity_revision,
                updated.configuration_revision,
                updated.section_revisions[section].revision,
            )
        if operation == "profiles.reset.preview":
            assert context.request.profile_id is not None
            _exact_payload(context.request.payload, {"scope"})
            scope = _payload_reset_scope(context.request.payload)
            preview = await asyncio.to_thread(
                self.profile_configuration.preview_reset, context.request.profile_id, scope
            )
            return {"preview": _preview_wire(preview)}
        if operation == "profiles.reset.confirm":
            assert context.request.profile_id is not None
            _exact_payload(context.request.payload, {"operation_id", "scope", "confirmation_token"})
            scope = _payload_reset_scope(context.request.payload)
            command = _confirm_command(
                context.request.payload,
                context.request.profile_id,
                DestructiveOperationKind.RESET_CONFIGURATION,
                scope,
            )
            reset_result = await asyncio.to_thread(
                self.profile_configuration.confirm_reset, command
            )
            return {
                "profile_id": str(reset_result.profile_id),
                "scope": reset_result.scope.value,
                "configuration_revision": reset_result.configuration.configuration_revision,
                "changed_sections": [section.value for section in reset_result.changed_sections],
            }
        if operation == "profiles.delete.preview":
            assert context.request.profile_id is not None
            _exact_payload(context.request.payload, set())
            preview = await asyncio.to_thread(
                self.profiles.preview_delete, context.request.profile_id
            )
            return {"preview": _preview_wire(preview)}
        if operation == "profiles.delete.confirm":
            assert context.request.profile_id is not None
            _exact_payload(context.request.payload, {"operation_id", "confirmation_token"})
            command = _confirm_command(
                context.request.payload,
                context.request.profile_id,
                DestructiveOperationKind.DELETE_PROFILE,
                DeletionScope.WHOLE_PROFILE,
            )
            delete_result = await asyncio.to_thread(self.profiles.confirm_delete, command)
            return {
                "deleted_profile_id": str(delete_result.profile_id),
                "old_alias": delete_result.alias_change.old_alias,
            }
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


def _validate_management_payload(request: IpcRequest) -> None:
    payload = request.payload
    operation = request.operation
    if operation == "profiles.resolve_alias":
        _exact_payload(payload, {"command_alias"})
        alias = _payload_text(payload, "command_alias", max_bytes=MAX_ALIAS_LENGTH)
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", alias) is None:
            raise ipc_error("ipc.invalid_message", reason="invalid_command_alias")
    elif operation == "profiles.create":
        _exact_payload(payload, {"display_name"})
        _payload_text(payload, "display_name", max_bytes=MAX_DISPLAY_NAME_BYTES)
    elif operation == "profiles.rename":
        _exact_payload(payload, {"display_name", "expected_identity_revision"})
        _payload_text(payload, "display_name", max_bytes=MAX_DISPLAY_NAME_BYTES)
        _payload_positive_int(payload, "expected_identity_revision")
    elif operation == "profiles.configuration.section.get":
        _exact_payload(payload, {"section"})
        if _payload_section(payload) is ConfigurationSection.STARTUP:
            raise ipc_error("ipc.operation_not_supported", operation=operation)
    elif operation == "profiles.configuration.section.update":
        _exact_payload(
            payload,
            {"section", "value", "expected_identity_revision", "expected_configuration_revision"},
        )
        if _payload_section(payload) is ConfigurationSection.STARTUP:
            raise ipc_error("ipc.operation_not_supported", operation=operation)
        _payload_positive_int(payload, "expected_identity_revision")
        _payload_positive_int(payload, "expected_configuration_revision")
    elif operation == "profiles.reset.preview":
        _exact_payload(payload, {"scope"})
        _payload_reset_scope(payload)
    elif operation == "profiles.reset.confirm":
        _exact_payload(payload, {"operation_id", "scope", "confirmation_token"})
        _payload_reset_scope(payload)
        _payload_confirmation(payload)
    elif operation == "profiles.delete.preview":
        _exact_payload(payload, set())
    elif operation == "profiles.delete.confirm":
        _exact_payload(payload, {"operation_id", "confirmation_token"})
        _payload_confirmation(payload)


def _payload_confirmation(payload: Mapping[str, object]) -> None:
    try:
        OperationId.parse(str(payload["operation_id"]))
    except (TypeError, ValueError) as error:
        raise ipc_error("ipc.invalid_message", reason="invalid_confirmation") from error
    token = payload.get("confirmation_token")
    if not isinstance(token, str) or not token or len(token.encode("utf-8")) > 256:
        raise ipc_error("ipc.invalid_message", reason="invalid_confirmation")


def _exact_payload(payload: Mapping[str, object], required: set[str]) -> None:
    if set(payload) != required:
        raise ipc_error("ipc.invalid_message", reason="invalid_payload_fields")


def _payload_text(payload: Mapping[str, object], key: str, *, max_bytes: int) -> str:
    value = payload[key]
    if not isinstance(value, str) or len(value.encode("utf-8")) > max_bytes:
        raise ipc_error("ipc.invalid_message", reason="invalid_payload")
    return value


def _payload_positive_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if type(value) is not int or value <= 0:
        raise ipc_error("ipc.invalid_message", reason="invalid_revision")
    return value


def _payload_section(payload: Mapping[str, object]) -> ConfigurationSection:
    value = payload.get("section")
    if not isinstance(value, str):
        raise ipc_error("ipc.invalid_message", reason="invalid_section")
    try:
        return ConfigurationSection(value)
    except (TypeError, ValueError) as error:
        raise ipc_error("ipc.invalid_message", reason="invalid_section") from error


def _payload_reset_scope(payload: Mapping[str, object]) -> ResetScope:
    value = payload.get("scope")
    if not isinstance(value, str):
        raise ipc_error("ipc.invalid_message", reason="invalid_scope")
    try:
        return ResetScope(value)
    except ValueError as error:
        raise ipc_error("ipc.invalid_message", reason="invalid_scope") from error


def _replace_section(
    values: ProfileConfigurationValues, section: ConfigurationSection, raw_value: object
) -> ProfileConfigurationValues:
    try:
        match section:
            case ConfigurationSection.PERSONA:
                if not isinstance(raw_value, str):
                    raise ValueError
                return replace(values, persona_text=raw_value)
            case ConfigurationSection.PROFILE_CONTEXT:
                if not isinstance(raw_value, str):
                    raise ValueError
                return replace(values, profile_context_text=raw_value)
            case ConfigurationSection.APPEARANCE:
                if not isinstance(raw_value, dict) or set(raw_value) != {
                    "accent_color",
                    "foreground_color",
                    "background_color",
                }:
                    raise ValueError
                return replace(values, appearance=AppearanceConfiguration(**raw_value))
            case ConfigurationSection.WAITING_MESSAGES:
                if not isinstance(raw_value, list):
                    raise ValueError
                return replace(values, waiting_messages=tuple(raw_value))
            case ConfigurationSection.GOODBYE_MESSAGES:
                if not isinstance(raw_value, list):
                    raise ValueError
                return replace(values, goodbye_messages=tuple(raw_value))
            case ConfigurationSection.VISIBLE_LOGGING:
                if not isinstance(raw_value, str):
                    raise ValueError
                return replace(values, visible_logging_mode=VisibleLoggingMode(raw_value))
            case ConfigurationSection.PERMISSIONS:
                if not isinstance(raw_value, dict):
                    raise ValueError
                return replace(
                    values,
                    permissions={
                        Capability(key): PermissionDecision(value)
                        for key, value in raw_value.items()
                    },
                )
            case ConfigurationSection.STARTUP:
                # The stored section remains resettable but is deliberately not writable in M003.
                raise ipc_error(
                    "ipc.operation_not_supported", operation="profiles.configuration.section.update"
                )
    except (TypeError, ValueError) as error:
        raise ipc_error("ipc.invalid_message", reason="invalid_section_value") from error


def _section_wire(
    value: object,
    section: ConfigurationSection,
    identity_revision: int,
    configuration_revision: int,
    section_revision: int,
) -> dict[str, object]:
    if isinstance(value, AppearanceConfiguration):
        wire_value: object = {
            "accent_color": value.accent_color,
            "foreground_color": value.foreground_color,
            "background_color": value.background_color,
        }
    elif isinstance(value, tuple):
        wire_value = list(value)
    elif isinstance(value, Mapping):
        wire_value = {str(key): str(item) for key, item in value.items()}
    elif isinstance(value, (VisibleLoggingMode,)):
        wire_value = value.value
    else:
        wire_value = value
    return {
        "section": section.value,
        "value": wire_value,
        "identity_revision": identity_revision,
        "configuration_revision": configuration_revision,
        "section_revision": section_revision,
    }


def _preview_wire(preview: object) -> dict[str, object]:
    from jarvis.profiles.destructive import DestructivePreview

    assert isinstance(preview, DestructivePreview)
    return {
        "operation_id": str(preview.operation_id),
        "operation_kind": preview.target.operation_kind.value,
        "scope": preview.target.scope.value,
        "profile_id": str(preview.profile_id),
        "expected_identity_revision": preview.expected_identity_revision,
        "expected_configuration_revision": preview.expected_configuration_revision,
        "expires_at_utc": preview.expires_at_utc.isoformat(),
        "target_defaults_version": preview.target_defaults_version,
        "has_changes": preview.has_changes,
        "confirmation_token": preview.confirmation_token,
        "items": [
            {
                "key": item.key,
                "action": item.action,
                "current_count": item.current_count,
                "target_count": item.target_count,
                "will_change": item.will_change,
            }
            for item in preview.items
        ],
    }


def _confirm_command(
    payload: Mapping[str, object], profile_id: object, kind: DestructiveOperationKind, scope: object
) -> ConfirmDestructiveOperation:
    _exact_payload(
        payload,
        {"operation_id", "scope", "confirmation_token"}
        if kind is DestructiveOperationKind.RESET_CONFIGURATION
        else {"operation_id", "confirmation_token"},
    )
    try:
        operation_id = OperationId.parse(str(payload["operation_id"]))
        token = payload["confirmation_token"]
        if not isinstance(token, str):
            raise ValueError
        from jarvis.profiles.models import ProfileId

        assert isinstance(profile_id, ProfileId)
        assert isinstance(scope, (ResetScope, DeletionScope))
        return ConfirmDestructiveOperation(
            operation_id, DestructiveTarget(kind, scope), profile_id, token
        )
    except (TypeError, ValueError) as error:
        raise ipc_error("ipc.invalid_message", reason="invalid_confirmation") from error
