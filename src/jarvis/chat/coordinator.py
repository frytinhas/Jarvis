"""Bounded deterministic per-profile generation admission."""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Protocol

from jarvis.chat.errors import ChatQueueFullError, ChatQuiescingError
from jarvis.profiles.models import ProfileId


class CancellationSignal(Protocol):
    @property
    def requested(self) -> bool: ...

    async def wait(self) -> None: ...

    def request(self) -> bool: ...


@dataclass(slots=True)
class _Ticket:
    signal: CancellationSignal
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    released: bool = False


@dataclass(slots=True)
class _ProfileQueue:
    active: _Ticket | None = None
    queued: deque[_Ticket] = field(default_factory=deque)
    idle: asyncio.Event = field(default_factory=asyncio.Event)
    holds: int = 0

    def __post_init__(self) -> None:
        self.idle.set()


class GenerationLease:
    def __init__(
        self, coordinator: GenerationCoordinator, profile_id: ProfileId, ticket: _Ticket
    ) -> None:
        self._coordinator = coordinator
        self._profile_id = profile_id
        self._ticket = ticket

    async def release(self) -> None:
        await self._coordinator._release(self._profile_id, self._ticket)

    async def __aenter__(self) -> GenerationLease:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.release()


class GenerationQuiescence:
    """Exclusive lifecycle hold which prevents admission after draining."""

    def __init__(
        self, coordinator: GenerationCoordinator, profile_id: ProfileId, outcome: str
    ) -> None:
        self._coordinator = coordinator
        self._profile_id = profile_id
        self.outcome = outcome
        self._released = False

    async def release(self) -> None:
        if not self._released:
            self._released = True
            await self._coordinator._release_hold(self._profile_id)

    async def __aenter__(self) -> str:
        return self.outcome

    async def __aexit__(self, *_exc: object) -> None:
        await self.release()


class GenerationCoordinator:
    def __init__(self, maximum_queued: int = 16) -> None:
        if maximum_queued != 16:
            raise ValueError("M006A requires exactly 16 queued generations")
        self._maximum_queued = maximum_queued
        self._queues: dict[ProfileId, _ProfileQueue] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, profile_id: ProfileId, signal: CancellationSignal) -> GenerationLease:
        ticket = _Ticket(signal)
        async with self._lock:
            queue = self._queues.setdefault(profile_id, _ProfileQueue())
            if queue.holds:
                raise ChatQuiescingError()
            if queue.active is None:
                queue.active = ticket
                queue.idle.clear()
                ticket.ready.set()
            else:
                if len(queue.queued) >= self._maximum_queued:
                    raise ChatQueueFullError()
                queue.queued.append(ticket)
        cancellation = asyncio.create_task(signal.wait())
        readiness = asyncio.create_task(ticket.ready.wait())
        try:
            done, _ = await asyncio.wait(
                (readiness, cancellation), return_when=asyncio.FIRST_COMPLETED
            )
            if cancellation in done and not readiness.done():
                await self._cancel_queued(profile_id, ticket)
                raise asyncio.CancelledError
            if signal.requested:
                await self._release(profile_id, ticket)
                raise asyncio.CancelledError
            return GenerationLease(self, profile_id, ticket)
        finally:
            cancellation.cancel()
            readiness.cancel()
            await asyncio.gather(cancellation, readiness, return_exceptions=True)

    async def _cancel_queued(self, profile_id: ProfileId, ticket: _Ticket) -> None:
        async with self._lock:
            queue = self._queues.get(profile_id)
            if queue is not None:
                with suppress(ValueError):
                    queue.queued.remove(ticket)

    async def _release(self, profile_id: ProfileId, ticket: _Ticket) -> None:
        async with self._lock:
            if ticket.released:
                return
            ticket.released = True
            queue = self._queues.get(profile_id)
            if queue is None or queue.active is not ticket:
                return
            queue.active = None
            while queue.queued:
                candidate = queue.queued.popleft()
                if candidate.signal.requested:
                    candidate.released = True
                    candidate.ready.set()
                    continue
                queue.active = candidate
                candidate.ready.set()
                break
            if queue.active is None and not queue.queued:
                queue.idle.set()

    async def quiesce(self, profile_id: ProfileId, *, cancel: bool) -> str:
        async with self._lock:
            queue = self._queues.get(profile_id)
            if queue is None or (queue.active is None and not queue.queued):
                return "idle"
            if cancel:
                if queue.active is not None:
                    queue.active.signal.request()
                for ticket in queue.queued:
                    ticket.signal.request()
            idle = queue.idle
        await idle.wait()
        return "cancelled" if cancel else "drained"

    async def hold(self, profile_id: ProfileId, *, cancel: bool) -> GenerationQuiescence:
        """Close admission before waiting, eliminating lifecycle/admission races."""

        async with self._lock:
            queue = self._queues.setdefault(profile_id, _ProfileQueue())
            queue.holds += 1
            if cancel:
                if queue.active is not None:
                    queue.active.signal.request()
                for ticket in queue.queued:
                    ticket.signal.request()
            idle = queue.idle
        await idle.wait()
        return GenerationQuiescence(self, profile_id, "cancelled" if cancel else "drained")

    async def _release_hold(self, profile_id: ProfileId) -> None:
        async with self._lock:
            queue = self._queues.get(profile_id)
            if queue is not None:
                queue.holds -= 1
                assert queue.holds >= 0

    async def close(self) -> None:
        async with self._lock:
            profiles = tuple(self._queues)
        await asyncio.gather(*(self.quiesce(profile, cancel=True) for profile in profiles))

    async def queued_count(self, profile_id: ProfileId) -> int:
        async with self._lock:
            queue = self._queues.get(profile_id)
            return 0 if queue is None else len(queue.queued)
