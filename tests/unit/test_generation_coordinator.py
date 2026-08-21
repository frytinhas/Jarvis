from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from jarvis.chat.coordinator import GenerationCoordinator
from jarvis.chat.errors import ChatQueueFullError, ChatQuiescingError
from jarvis.profiles.models import ProfileId

pytestmark = pytest.mark.unit


class Signal:
    def __init__(self) -> None:
        self.event = asyncio.Event()

    @property
    def requested(self) -> bool:
        return self.event.is_set()

    async def wait(self) -> None:
        await self.event.wait()

    def request(self) -> bool:
        first = not self.event.is_set()
        self.event.set()
        return first


def test_same_profile_fifo_queue_bound_and_queued_cancellation() -> None:
    async def run() -> None:
        coordinator = GenerationCoordinator()
        profile = ProfileId(uuid4())
        active = await coordinator.acquire(profile, Signal())
        signals = [Signal() for _ in range(16)]
        tasks = [asyncio.create_task(coordinator.acquire(profile, signal)) for signal in signals]
        await asyncio.gather(*(coordinator.queued_count(profile) for _ in range(2)))
        while await coordinator.queued_count(profile) != 16:
            await asyncio.sleep(0)
        with pytest.raises(ChatQueueFullError):
            await coordinator.acquire(profile, Signal())
        signals[0].request()
        with pytest.raises(asyncio.CancelledError):
            await tasks[0]
        await active.release()
        first = await tasks[1]
        assert await coordinator.queued_count(profile) == 14
        await first.release()
        for task in tasks[2:]:
            lease = await task
            await lease.release()

    asyncio.run(run())


def test_different_profiles_admit_concurrently_and_quiesce_cancels_active() -> None:
    async def run() -> None:
        coordinator = GenerationCoordinator()
        first_signal = Signal()
        second_signal = Signal()
        first = await coordinator.acquire(ProfileId(uuid4()), first_signal)
        second = await coordinator.acquire(ProfileId(uuid4()), second_signal)
        assert first is not None and second is not None
        profile = ProfileId(uuid4())
        signal = Signal()
        active = await coordinator.acquire(profile, signal)
        quiesce = asyncio.create_task(coordinator.quiesce(profile, cancel=True))
        await signal.wait()
        await active.release()
        assert await quiesce == "cancelled"
        await first.release()
        await second.release()

    asyncio.run(run())


def test_lifecycle_hold_closes_admission_after_drain() -> None:
    """A reset/switch cannot race a newly admitted generation after quiescence."""

    async def run() -> None:
        coordinator = GenerationCoordinator()
        profile = ProfileId(uuid4())
        async with await coordinator.hold(profile, cancel=False):
            with pytest.raises(ChatQuiescingError) as caught:
                await coordinator.acquire(profile, Signal())
            assert getattr(caught.value, "code", None) == "chat.profile_quiescing"

    asyncio.run(run())
