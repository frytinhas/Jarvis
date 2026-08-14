from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from jarvis.core.requests import CancelOutcome, RequestRegistry
from jarvis.ipc.errors import IpcError
from jarvis.ipc.models import ConnectionId, CoreInstanceId, IpcRequest, RequestId

pytestmark = pytest.mark.unit


def _request(request_id: RequestId | None = None) -> IpcRequest:
    return IpcRequest(request_id or RequestId(uuid4()), "test.harmless", None, {})


def test_accept_start_complete_is_monotonic_and_exactly_terminal() -> None:
    async def run() -> None:
        registry = RequestRegistry(CoreInstanceId(uuid4()))
        context = await registry.accept(_request(), ConnectionId(uuid4()))
        await registry.start(context)
        terminal = await registry.complete(context, {"ok": True})
        assert terminal is not None
        assert [event.sequence for event in context.events] == [1, 2, 3]
        assert [event.event_type for event in context.events] == [
            "request.accepted",
            "request.started",
            "request.completed",
        ]
        assert sum(event.terminal for event in context.events) == 1
        assert await registry.complete(context, {}) is None
        assert await registry.emit(context, "test.progress", {}) is None

    asyncio.run(run())


def test_cancel_before_start_has_no_started_event() -> None:
    async def run() -> None:
        registry = RequestRegistry(CoreInstanceId(uuid4()))
        owner = ConnectionId(uuid4())
        context = await registry.accept(_request(), owner)
        assert await registry.cancel(context.request_id, owner) is CancelOutcome.REQUESTED
        assert [event.event_type for event in context.events] == [
            "request.accepted",
            "request.cancelled",
        ]
        assert await registry.start(context) is None

    asyncio.run(run())


def test_completion_cancellation_race_selects_one_terminal() -> None:
    async def run() -> None:
        registry = RequestRegistry(CoreInstanceId(uuid4()))
        owner = ConnectionId(uuid4())
        for _ in range(20):
            context = await registry.accept(_request(), owner)
            await registry.start(context)
            results = await asyncio.gather(
                registry.complete(context, {"ok": True}),
                registry.cancel(context.request_id, owner),
            )
            assert len([event for event in context.events if event.terminal]) == 1
            assert context.events[-1].event_type in {"request.completed", "request.cancelled"}
            assert results[0] is None or results[1] is CancelOutcome.ALREADY_TERMINAL

    asyncio.run(run())


def test_request_id_collision_never_mutates_or_exposes_retained_state() -> None:
    async def run() -> None:
        registry = RequestRegistry(CoreInstanceId(uuid4()))
        request = _request()
        first = await registry.accept(request, ConnectionId(uuid4()))
        with pytest.raises(IpcError) as caught:
            await registry.accept(request, ConnectionId(uuid4()))
        assert caught.value.code == "ipc.request_id_conflict"
        assert len(first.events) == 1

    asyncio.run(run())


def test_wrong_owner_cannot_cancel_or_inspect() -> None:
    async def run() -> None:
        registry = RequestRegistry(CoreInstanceId(uuid4()))
        context = await registry.accept(_request(), ConnectionId(uuid4()))
        stranger = ConnectionId(uuid4())
        with pytest.raises(IpcError) as caught:
            await registry.cancel(context.request_id, stranger)
        assert caught.value.code == "ipc.request_not_owned"
        with pytest.raises(IpcError):
            await registry.get_owned(RequestId(uuid4()), stranger)

    asyncio.run(run())


def test_admission_limits_are_atomic_and_terminal_releases_capacity() -> None:
    async def run() -> None:
        registry = RequestRegistry(
            CoreInstanceId(uuid4()), max_in_flight_per_session=1, max_in_flight_global=2
        )
        owner = ConnectionId(uuid4())
        first = await registry.accept(_request(), owner)
        with pytest.raises(IpcError) as caught:
            await registry.accept(_request(), owner)
        assert caught.value.code == "ipc.request_limit"
        await registry.complete(first, {})
        second = await registry.accept(_request(), owner)
        assert registry.in_flight_count == 1
        await registry.complete(second, {})

    asyncio.run(run())


def test_disconnect_has_no_registry_cancellation_effect() -> None:
    async def run() -> None:
        registry = RequestRegistry(CoreInstanceId(uuid4()))
        context = await registry.accept(_request(), ConnectionId(uuid4()))
        # There is deliberately no disconnect API on the request registry.
        await asyncio.sleep(0)
        assert not context.cancellation.requested
        assert not context.terminal

    asyncio.run(run())


def test_replay_gap_is_authoritative_after_per_request_eviction() -> None:
    async def run() -> None:
        registry = RequestRegistry(CoreInstanceId(uuid4()))
        owner = ConnectionId(uuid4())
        context = await registry.accept(_request(), owner)
        await registry.start(context)
        for index in range(80):
            await registry.emit(context, "test.progress", {"index": index})
        await registry.complete(context, {})
        assert len(context.events) <= 64
        with pytest.raises(IpcError) as caught:
            await registry.replay(context.request_id, owner, 0)
        assert caught.value.code == "ipc.replay_unavailable"
        details = caught.value.safe_details
        earliest = details["earliest_retained_sequence"]
        assert isinstance(earliest, int)
        assert earliest > 1
        latest = context.events[-1].sequence
        replay = await registry.replay(context.request_id, owner, latest - 1)
        assert len(replay) == 1
        assert replay[0].terminal

    asyncio.run(run())


def test_session_replay_retention_is_bounded_and_deterministic() -> None:
    async def run() -> None:
        registry = RequestRegistry(CoreInstanceId(uuid4()))
        owner = ConnectionId(uuid4())
        contexts = []
        for _ in range(100):
            context = await registry.accept(_request(), owner)
            await registry.start(context)
            await registry.complete(context, {})
            contexts.append(context)
        assert sum(len(context.events) for context in contexts) <= 256
        assert contexts[0].earliest_sequence > 1
        first_status = await registry.status(contexts[0].request_id, owner)
        assert first_status["state"] == "COMPLETED"
        with pytest.raises(IpcError) as caught:
            await registry.replay(contexts[0].request_id, owner, 0)
        assert caught.value.code == "ipc.replay_unavailable"

    asyncio.run(run())


def test_completed_requests_are_evicted_when_terminal_summaries_exceed_session_bytes() -> None:
    async def run() -> None:
        registry = RequestRegistry(CoreInstanceId(uuid4()))
        owner = ConnectionId(uuid4())
        contexts = []
        for _ in range(40):
            context = await registry.accept(_request(), owner)
            await registry.start(context)
            await registry.complete(context, {"value": "x" * 60_000})
            contexts.append(context)

        assert await registry.retained(contexts[0].request_id) is None
        assert await registry.retained(contexts[-1].request_id) is not None
        with pytest.raises(IpcError) as caught:
            await registry.status(contexts[0].request_id, owner)
        assert caught.value.code == "ipc.request_not_found"

        reused = await registry.accept(_request(contexts[0].request_id), owner)
        assert reused.request_id == contexts[0].request_id

    asyncio.run(run())


def test_expired_session_discards_terminal_request_ids() -> None:
    async def run() -> None:
        registry = RequestRegistry(CoreInstanceId(uuid4()))
        owner = ConnectionId(uuid4())
        context = await registry.accept(_request(), owner)
        await registry.complete(context, {})
        await registry.discard_owner(owner)
        assert await registry.retained(context.request_id) is None

    asyncio.run(run())
