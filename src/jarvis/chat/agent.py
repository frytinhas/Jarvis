"""Core-owned text-only Agent Engine for M006A."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from jarvis.chat.context import ContextBuilder
from jarvis.chat.coordinator import CancellationSignal, GenerationCoordinator
from jarvis.chat.diagnostics import ChatDiagnosticService
from jarvis.chat.errors import ChatError, ProviderStreamError
from jarvis.chat.models import (
    ContextContribution,
    MessageRole,
    SessionId,
    TurnSnapshot,
    TurnState,
)
from jarvis.chat.repository import ConversationRepository
from jarvis.config.defaults import DefaultsRegistry
from jarvis.foundation.clock import Clock
from jarvis.llm.provider import (
    ProviderChatRequest,
    ProviderMessage,
    ProviderMessageRole,
    ProviderStreamEventKind,
)
from jarvis.models.models import ModelRuntimeConfig
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.models import ProfileId
from jarvis.profiles.service import ProfileConfigService
from jarvis.runtimes.manager import RuntimeManager


@dataclass(frozen=True, slots=True)
class AgentStreamEvent:
    event_type: str
    payload: dict[str, object]


AgentEventCallback = Callable[[AgentStreamEvent], Awaitable[None]]


class AgentEngine:
    def __init__(
        self,
        *,
        conversations: ConversationRepository,
        diagnostics: ChatDiagnosticService,
        coordinator: GenerationCoordinator,
        runtime_manager: RuntimeManager,
        profiles: ProfileConfigService,
        models: ModelRegistryService,
        defaults: DefaultsRegistry,
        clock: Clock,
    ) -> None:
        self._conversations = conversations
        self._diagnostics = diagnostics
        self._coordinator = coordinator
        self._runtime_manager = runtime_manager
        self._profiles = profiles
        self._models = models
        self._defaults = defaults
        self._clock = clock
        self._context = ContextBuilder(
            max_contribution_bytes=defaults.current().chat.max_context_contribution_bytes
        )

    async def chat(
        self,
        *,
        profile_id: ProfileId,
        request_id: str,
        content: str,
        cancellation: CancellationSignal,
        emit: AgentEventCallback,
        session_id: SessionId | None = None,
        new_session: bool = False,
    ) -> TurnSnapshot:
        chat_defaults = self._defaults.current().chat
        reservation = None
        turn: TurnSnapshot | None = None
        partial = ""
        try:
            record, config, _revision = await asyncio.to_thread(
                self._models.runtime_association, profile_id, None
            )
            reservation = await asyncio.to_thread(
                self._diagnostics.reserve, profile_id, record.model_id
            )
            admitted = await asyncio.to_thread(
                self._conversations.admit,
                profile_id=profile_id,
                model_id=record.model_id,
                request_id=request_id,
                content=content,
                now=self._clock.now(),
                max_message_bytes=chat_defaults.max_message_bytes,
                max_session_bytes=chat_defaults.max_session_bytes,
                requested_session_id=session_id,
                new_session=new_session,
            )
            turn = admitted.turn
            await asyncio.to_thread(
                self._diagnostics.emit, turn, "queued", "Generation admitted to durable queue"
            )
            async with await self._coordinator.acquire(profile_id, cancellation):
                if cancellation.requested:
                    raise asyncio.CancelledError
                turn = await asyncio.to_thread(
                    self._conversations.mark_generating, turn, self._clock.now()
                )
                # Build only after this turn owns the profile generation lease.  A queued
                # request must not see later durable user messages, nor run without the
                # preceding assistant completion that FIFO has just made durable.
                history, profile_configuration = await asyncio.gather(
                    asyncio.to_thread(self._conversations.history, turn),
                    asyncio.to_thread(self._profiles.get_configuration, profile_id),
                )
                effective_context_window = await self._runtime_manager.context_window(
                    profile_id, config.context_window
                )
                context = self._context.build(
                    persona=profile_configuration.values.persona_text,
                    profile_context=profile_configuration.values.profile_context_text,
                    user_configured=f"reasoning={config.reasoning}",
                    conversation=history,
                    user_request=content,
                    context_window=effective_context_window,
                )
                provider_request = self._provider_request(turn, context.contributions, config)
                await asyncio.to_thread(
                    self._diagnostics.emit,
                    turn,
                    "generation_started",
                    "Local generation started",
                )
                await emit(
                    AgentStreamEvent(
                        "response_started",
                        {
                            "session_id": str(turn.session_id),
                            "turn_id": str(turn.turn_id),
                            "model_id": str(turn.model_id),
                            "learning_status": admitted.learning.status.value,
                        },
                    )
                )

                async def consume() -> None:
                    nonlocal partial
                    assert turn is not None
                    completed = False
                    async for event in self._runtime_manager.stream_chat(
                        profile_id, provider_request
                    ):
                        if event.kind is ProviderStreamEventKind.TEXT_DELTA:
                            candidate = partial + event.text
                            if len(candidate.encode("utf-8")) > chat_defaults.max_partial_bytes:
                                raise ProviderStreamError("partial_output_too_large")
                            partial = candidate
                            await asyncio.to_thread(
                                self._conversations.store_partial,
                                turn,
                                partial,
                                chat_defaults.max_partial_bytes,
                            )
                            await emit(AgentStreamEvent("text_delta", {"text": event.text}))
                        elif event.kind is ProviderStreamEventKind.COMPLETED:
                            if completed:
                                raise ProviderStreamError("duplicate_completion")
                            completed = True
                    if not completed:
                        raise ProviderStreamError("missing_completion")

                generation = asyncio.create_task(consume())
                cancellation_wait = asyncio.create_task(cancellation.wait())
                try:
                    done, _ = await asyncio.wait(
                        (generation, cancellation_wait), return_when=asyncio.FIRST_COMPLETED
                    )
                    if cancellation_wait in done and not generation.done():
                        generation.cancel()
                        await asyncio.gather(generation, return_exceptions=True)
                        raise asyncio.CancelledError
                    await generation
                finally:
                    cancellation_wait.cancel()
                    await asyncio.gather(cancellation_wait, return_exceptions=True)
                # The next FIFO turn may construct context as soon as the lease is released.
                # Commit the successful assistant message before that point so it observes a
                # complete preceding turn rather than an unpaired user message.
                turn = await asyncio.to_thread(
                    self._conversations.finalize,
                    turn,
                    state=TurnState.COMPLETED,
                    partial_text=partial,
                    failure_code=None,
                    now=self._clock.now(),
                    max_message_bytes=chat_defaults.max_message_bytes,
                    max_session_bytes=chat_defaults.max_session_bytes,
                )
                await asyncio.to_thread(
                    self._diagnostics.emit,
                    turn,
                    "completed",
                    "Generation completed",
                    closed=True,
                )
                await emit(AgentStreamEvent("response_completed", turn.to_safe_mapping()))
                return turn
        except asyncio.CancelledError:
            if turn is not None and turn.state not in {
                TurnState.COMPLETED,
                TurnState.FAILED,
                TurnState.CANCELLED,
            }:
                turn = await asyncio.to_thread(
                    self._conversations.finalize,
                    turn,
                    state=TurnState.CANCELLED,
                    partial_text=partial,
                    failure_code="chat.cancelled",
                    now=self._clock.now(),
                    max_message_bytes=chat_defaults.max_message_bytes,
                    max_session_bytes=chat_defaults.max_session_bytes,
                )
                await asyncio.to_thread(
                    self._diagnostics.emit,
                    turn,
                    "cancelled",
                    "Generation cancelled",
                    severity="warning",
                    closed=True,
                )
            raise
        except BaseException as error:
            if turn is not None and turn.state not in {
                TurnState.COMPLETED,
                TurnState.FAILED,
                TurnState.CANCELLED,
            }:
                code = error.code if isinstance(error, ChatError) else "chat.generation_failed"
                turn = await asyncio.to_thread(
                    self._conversations.finalize,
                    turn,
                    state=TurnState.FAILED,
                    partial_text=partial,
                    failure_code=code,
                    now=self._clock.now(),
                    max_message_bytes=chat_defaults.max_message_bytes,
                    max_session_bytes=chat_defaults.max_session_bytes,
                )
                await asyncio.to_thread(
                    self._diagnostics.emit,
                    turn,
                    "failed",
                    f"Generation failed: {code}",
                    severity="error",
                    closed=True,
                )
            raise
        finally:
            if reservation is not None:
                reservation.release()

    def _provider_request(
        self,
        turn: TurnSnapshot,
        contributions: tuple[ContextContribution, ...],
        config: ModelRuntimeConfig,
    ) -> ProviderChatRequest:
        role_map = {
            MessageRole.SYSTEM: ProviderMessageRole.SYSTEM,
            MessageRole.USER: ProviderMessageRole.USER,
            MessageRole.ASSISTANT: ProviderMessageRole.ASSISTANT,
        }
        chat = self._defaults.current().chat
        return ProviderChatRequest(
            messages=tuple(
                ProviderMessage(role_map[item.role], item.content, item.provenance.value)
                for item in contributions
            ),
            temperature=config.temperature,
            top_p=config.top_p,
            top_k=config.top_k,
            min_p=config.min_p,
            repeat_penalty=config.repeat_penalty,
            generation_timeout_seconds=config.generation_timeout_seconds,
            request_id=turn.request_id,
            session_id=str(turn.session_id),
            turn_id=str(turn.turn_id),
            max_delta_bytes=chat.max_provider_delta_bytes,
            max_sse_frame_bytes=chat.max_sse_frame_bytes,
            max_response_bytes=chat.max_sse_response_bytes,
        )
