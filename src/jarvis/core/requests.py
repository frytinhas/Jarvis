"""Request ownership, state transitions, sequencing, and terminal arbitration."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from jarvis.ipc.errors import ipc_error
from jarvis.ipc.models import (
    ConnectionId,
    CoreInstanceId,
    IpcRequest,
    RequestId,
    RequestState,
    safe_error_payload,
)

MAX_IN_FLIGHT_PER_SESSION = 16
MAX_IN_FLIGHT_GLOBAL = 128
MAX_EVENTS_PER_REQUEST = 64
MAX_REPLAY_BYTES_PER_REQUEST = 256 * 1024
MAX_EVENTS_PER_SESSION = 256
MAX_REPLAY_BYTES_PER_SESSION = 2 * 1024 * 1024
MAX_REPLAY_BYTES_GLOBAL = 16 * 1024 * 1024


class CancelOutcome(StrEnum):
    REQUESTED = "requested"
    ALREADY_REQUESTED = "already_requested"
    ALREADY_TERMINAL = "already_terminal"


class CancellationController:
    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()

    def request(self) -> bool:
        if self._event.is_set():
            return False
        self._event.set()
        return True


@dataclass(frozen=True, slots=True)
class IpcEvent:
    core_instance_id: CoreInstanceId
    request_id: RequestId
    sequence: int
    event_type: str
    terminal: bool
    payload: Mapping[str, object] | None = None
    error: Mapping[str, object] | None = None

    def to_wire(self) -> dict[str, object]:
        result: dict[str, object] = {
            "type": "event",
            "protocol_version": 1,
            "core_instance_id": str(self.core_instance_id),
            "request_id": str(self.request_id),
            "sequence": self.sequence,
            "event_type": self.event_type,
            "terminal": self.terminal,
        }
        if self.error is not None:
            result["error"] = dict(self.error)
        else:
            result["payload"] = dict(self.payload or {})
        return result


@dataclass(slots=True)
class RequestContext:
    request: IpcRequest
    owner: ConnectionId
    core_instance_id: CoreInstanceId
    state: RequestState = RequestState.ACCEPTED
    cancellation: CancellationController = field(default_factory=CancellationController)
    events: list[IpcEvent] = field(default_factory=list)
    state_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    terminal_event: asyncio.Event = field(default_factory=asyncio.Event)
    replay_bytes: int = 0
    earliest_sequence: int = 1
    completed_order: int | None = None
    next_sequence: int = 1

    @property
    def request_id(self) -> RequestId:
        return self.request.request_id

    @property
    def terminal(self) -> bool:
        return self.state.terminal

    def _append(
        self,
        event_type: str,
        *,
        terminal: bool,
        payload: Mapping[str, object] | None = None,
        error: Mapping[str, object] | None = None,
    ) -> IpcEvent:
        if self.events and self.events[-1].terminal:
            raise ipc_error("ipc.already_terminal")
        event = IpcEvent(
            core_instance_id=self.core_instance_id,
            request_id=self.request_id,
            sequence=self.next_sequence,
            event_type=event_type,
            terminal=terminal,
            payload=payload,
            error=error,
        )
        event_size = _event_size(event)
        if event_size > MAX_REPLAY_BYTES_PER_REQUEST:
            raise ipc_error(
                "ipc.message_too_large",
                maximum_bytes=MAX_REPLAY_BYTES_PER_REQUEST,
            )
        self.next_sequence += 1
        self.events.append(event)
        self.replay_bytes += event_size
        while (
            len(self.events) > MAX_EVENTS_PER_REQUEST
            or self.replay_bytes > MAX_REPLAY_BYTES_PER_REQUEST
        ) and len(self.events) > 1:
            removed = self.events.pop(0)
            self.replay_bytes -= _event_size(removed)
            self.earliest_sequence = removed.sequence + 1
        if terminal:
            self.terminal_event.set()
        return event


class RequestRegistry:
    def __init__(
        self,
        core_instance_id: CoreInstanceId,
        *,
        max_in_flight_per_session: int = MAX_IN_FLIGHT_PER_SESSION,
        max_in_flight_global: int = MAX_IN_FLIGHT_GLOBAL,
    ) -> None:
        self._core_instance_id = core_instance_id
        self._max_per_session = max_in_flight_per_session
        self._max_global = max_in_flight_global
        self._requests: dict[RequestId, RequestContext] = {}
        self._in_flight_by_owner: Counter[ConnectionId] = Counter()
        self._in_flight = 0
        self._completion_counter = 0
        self._lock = asyncio.Lock()

    @property
    def in_flight_count(self) -> int:
        # Terminal state is authoritative; the admission counter is released immediately after
        # terminal arbitration and can lag by one event-loop turn.
        return sum(not context.terminal for context in self._requests.values())

    async def accept(self, request: IpcRequest, owner: ConnectionId) -> RequestContext:
        async with self._lock:
            if request.request_id in self._requests:
                raise ipc_error("ipc.request_id_conflict")
            if self._in_flight >= self._max_global:
                raise ipc_error("ipc.request_limit", scope="global")
            if self._in_flight_by_owner[owner] >= self._max_per_session:
                raise ipc_error("ipc.request_limit", scope="session")
            context = RequestContext(request, owner, self._core_instance_id)
            context._append("request.accepted", terminal=False, payload={})
            self._requests[request.request_id] = context
            self._in_flight += 1
            self._in_flight_by_owner[owner] += 1
            return context

    async def start(self, context: RequestContext) -> IpcEvent | None:
        async with context.state_lock:
            if context.state is not RequestState.ACCEPTED:
                return None
            context.state = RequestState.RUNNING
            event = context._append("request.started", terminal=False, payload={})
        await self._enforce_replay_bounds(context.owner)
        return event

    async def emit(
        self,
        context: RequestContext,
        event_type: str,
        payload: Mapping[str, object],
    ) -> IpcEvent | None:
        async with context.state_lock:
            if context.state is not RequestState.RUNNING:
                return None
            event = context._append(event_type, terminal=False, payload=payload)
        await self._enforce_replay_bounds(context.owner)
        return event

    async def complete(
        self,
        context: RequestContext,
        payload: Mapping[str, object],
        *,
        event_type: str = "request.completed",
    ) -> IpcEvent | None:
        return await self._terminal(
            context,
            state=RequestState.COMPLETED,
            event_type=event_type,
            payload=payload,
        )

    async def fail(self, context: RequestContext, error: BaseException) -> IpcEvent | None:
        return await self._terminal(
            context,
            state=RequestState.FAILED,
            event_type="error",
            error=safe_error_payload(error),
        )

    async def _terminal(
        self,
        context: RequestContext,
        *,
        state: RequestState,
        event_type: str,
        payload: Mapping[str, object] | None = None,
        error: Mapping[str, object] | None = None,
    ) -> IpcEvent | None:
        async with context.state_lock:
            if context.state.terminal:
                return None
            event = context._append(
                event_type,
                terminal=True,
                payload=payload,
                error=error,
            )
            context.state = state
        await self._release_admission(context)
        await self._enforce_replay_bounds(context.owner)
        return event

    async def cancel(self, request_id: RequestId, owner: ConnectionId) -> CancelOutcome:
        context = await self._owned(request_id, owner)
        async with context.state_lock:
            if context.state.terminal:
                return CancelOutcome.ALREADY_TERMINAL
            first = context.cancellation.request()
            context.state = RequestState.CANCELLED
            if context.request.operation.startswith("chat."):
                context._append(
                    "error",
                    terminal=True,
                    error={
                        "code": "chat.cancelled",
                        "message_key": "error.chat.cancelled",
                        "safe_details": {"reason": "explicit_cancellation"},
                    },
                )
            else:
                context._append("request.cancelled", terminal=True, payload={})
        await self._release_admission(context)
        await self._enforce_replay_bounds(context.owner)
        return CancelOutcome.REQUESTED if first else CancelOutcome.ALREADY_REQUESTED

    async def get_owned(self, request_id: RequestId, owner: ConnectionId) -> RequestContext:
        return await self._owned(request_id, owner)

    async def _owned(self, request_id: RequestId, owner: ConnectionId) -> RequestContext:
        async with self._lock:
            context = self._requests.get(request_id)
            if context is None:
                raise ipc_error("ipc.request_not_found")
            if context.owner != owner:
                raise ipc_error("ipc.request_not_owned")
            return context

    async def _release_admission(self, context: RequestContext) -> None:
        async with self._lock:
            if self._in_flight_by_owner[context.owner] <= 0:
                return
            self._in_flight -= 1
            self._in_flight_by_owner[context.owner] -= 1
            if self._in_flight_by_owner[context.owner] == 0:
                del self._in_flight_by_owner[context.owner]
            if context.completed_order is None:
                self._completion_counter += 1
                context.completed_order = self._completion_counter

    async def _enforce_replay_bounds(self, owner: ConnectionId) -> None:
        async with self._lock:
            owned = [context for context in self._requests.values() if context.owner == owner]
            evicted = _trim_contexts(
                owned,
                max_events=MAX_EVENTS_PER_SESSION,
                max_bytes=MAX_REPLAY_BYTES_PER_SESSION,
            )
            for request_id in evicted:
                self._requests.pop(request_id, None)
            globally_retained = list(self._requests.values())
            evicted = _trim_contexts(
                globally_retained,
                max_events=None,
                max_bytes=MAX_REPLAY_BYTES_GLOBAL,
            )
            for request_id in evicted:
                self._requests.pop(request_id, None)

    async def discard_owner(self, owner: ConnectionId) -> None:
        """Discard terminal replay state after a disconnected session expires."""

        async with self._lock:
            owned = [
                request_id
                for request_id, context in self._requests.items()
                if context.owner == owner
            ]
            if any(not self._requests[request_id].terminal for request_id in owned):
                return
            for request_id in owned:
                del self._requests[request_id]

    async def retained(self, request_id: RequestId) -> RequestContext | None:
        async with self._lock:
            return self._requests.get(request_id)

    async def status(self, request_id: RequestId, owner: ConnectionId) -> dict[str, object]:
        context = await self._owned(request_id, owner)
        latest = context.next_sequence - 1
        return {
            "request_id": str(request_id),
            "state": context.state.value,
            "terminal": context.terminal,
            "earliest_retained_sequence": context.earliest_sequence,
            "latest_sequence": latest,
        }

    async def replay(
        self, request_id: RequestId, owner: ConnectionId, after_sequence: int
    ) -> tuple[IpcEvent, ...]:
        if after_sequence < 0:
            raise ipc_error("ipc.invalid_message", reason="invalid_after_sequence")
        context = await self._owned(request_id, owner)
        latest = context.next_sequence - 1
        if after_sequence < context.earliest_sequence - 1 and latest > after_sequence:
            raise ipc_error(
                "ipc.replay_unavailable",
                state=context.state.value,
                terminal=context.terminal,
                earliest_retained_sequence=context.earliest_sequence,
                latest_sequence=latest,
            )
        return tuple(event for event in context.events if event.sequence > after_sequence)

    async def owner_has_active(self, owner: ConnectionId) -> bool:
        async with self._lock:
            return any(
                context.owner == owner and not context.terminal
                for context in self._requests.values()
            )

    async def cancel_all_unfinished(self) -> None:
        """Request terminal cancellation for every unfinished M002 request during Core stop."""

        async with self._lock:
            targets = [context for context in self._requests.values() if not context.terminal]
        for context in targets:
            await self.cancel(context.request_id, context.owner)


def _event_size(event: IpcEvent) -> int:
    return len(
        json.dumps(
            event.to_wire(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _trim_contexts(
    contexts: list[RequestContext], *, max_events: int | None, max_bytes: int
) -> tuple[RequestId, ...]:
    def totals() -> tuple[int, int]:
        return sum(len(context.events) for context in contexts), sum(
            context.replay_bytes for context in contexts
        )

    event_count, byte_count = totals()
    ordered = sorted(
        contexts,
        key=lambda context: (
            context.completed_order is None,
            context.completed_order or 0,
            str(context.request_id),
        ),
    )
    evicted: list[RequestId] = []
    while (max_events is not None and event_count > max_events) or byte_count > max_bytes:
        candidate = next(
            (
                context
                for context in ordered
                if len(context.events) > 1 or (context.events and not context.terminal)
            ),
            None,
        )
        if candidate is not None:
            removed = candidate.events.pop(0)
            size = _event_size(removed)
            candidate.replay_bytes -= size
            candidate.earliest_sequence = removed.sequence + 1
            event_count -= 1
            byte_count -= size
            continue
        completed = next((context for context in ordered if context.terminal), None)
        if completed is None:
            # Active request terminal summaries cannot be discarded. Admission and per-event
            # bounds keep this exceptional remainder finite until those requests terminate.
            break
        ordered.remove(completed)
        contexts.remove(completed)
        event_count -= len(completed.events)
        byte_count -= completed.replay_bytes
        evicted.append(completed.request_id)
    return tuple(evicted)
