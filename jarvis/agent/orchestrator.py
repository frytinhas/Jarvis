from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from typing import Any

from jarvis.agent.prompts import SYSTEM_PROMPT
from jarvis.llm.client import LLM, LLMTimeoutError
from jarvis.llm.schemas import AssistantMessage, Message
from jarvis.security.confirmation import ConfirmationError, PendingAction
from jarvis.tools.registry import ToolRegistry, ToolResult


@dataclass(frozen=True)
class AgentReply:
    text: str
    pending: PendingAction | None = None


class Orchestrator:
    def __init__(
        self,
        llm: LLM,
        registry: ToolRegistry,
        max_tool_rounds: int = 8,
        request_timeout_seconds: float = 60.0,
        system_prompt: str = SYSTEM_PROMPT,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds deve ser positivo")
        self.llm = llm
        self.registry = registry
        self.max_tool_rounds = max_tool_rounds
        self.request_timeout_seconds = request_timeout_seconds
        self.clock = clock or time.monotonic
        self.messages: list[Message] = [{"role": "system", "content": system_prompt}]
        self.transcript: list[dict[str, str]] = []
        self.started_at = datetime.now(timezone.utc)
        self._pending_calls: dict[str, tuple[str, PendingAction]] = {}

    def handle(self, user_text: str) -> AgentReply:
        if self._pending_calls:
            return self._reply("Há uma ação aguardando confirmação.", self._current_pending())
        self.transcript.append({"role": "user", "content": user_text})
        self.messages.append({"role": "user", "content": user_text})
        return self._run(self._deadline())

    def confirm(self, action_id: str) -> AgentReply:
        deadline = self._deadline()
        pending_call = self._pending_calls.pop(action_id, None)
        if pending_call is None:
            return self._reply("Ação pendente inexistente ou diferente.")
        self.transcript.append({"role": "user", "content": "[Ação confirmada pelo usuário]"})
        call_id, _ = pending_call
        try:
            result = self.registry.confirm(action_id)
        except (ConfirmationError, ValueError) as error:
            result = ToolResult("error", {"error": str(error)})
        self._append_tool_result(call_id, result)
        if self.clock() >= deadline:
            return self._tool_completed_after_timeout()
        return self._run(deadline)

    def cancel(self, action_id: str) -> AgentReply:
        deadline = self._deadline()
        pending_call = self._pending_calls.pop(action_id, None)
        if pending_call is None:
            return self._reply("Ação pendente inexistente ou diferente.")
        self.transcript.append({"role": "user", "content": "[Ação cancelada pelo usuário]"})
        call_id, _ = pending_call
        result = self.registry.cancel(action_id)
        self._append_tool_result(call_id, result)
        if self.clock() >= deadline:
            return self._tool_completed_after_timeout()
        return self._run(deadline)

    def _run(self, deadline: float) -> AgentReply:
        for _ in range(self.max_tool_rounds):
            remaining = deadline - self.clock()
            if remaining <= 0:
                return self._timeout_reply()
            try:
                assistant = self.llm.chat(
                    self.messages,
                    self.registry.schemas(),
                    timeout=remaining,
                )
            except LLMTimeoutError:
                return self._timeout_reply()
            if self.clock() >= deadline:
                return self._timeout_reply()
            self.messages.append(self._assistant_dict(assistant))
            if not assistant.tool_calls:
                return self._reply(assistant.content or "")
            if len(assistant.tool_calls) != 1:
                for call in assistant.tool_calls:
                    self._append_tool_result(
                        call.id,
                        ToolResult("error", {"error": "Solicite somente uma tool por resposta"}),
                    )
                continue
            call = assistant.tool_calls[0]
            if self.clock() >= deadline:
                return self._timeout_reply()
            result = self.registry.request(call.function.name, call.function.arguments)
            if result.pending:
                self._pending_calls[result.pending.id] = (call.id, result.pending)
                return self._reply(self._confirmation_message(result.pending), result.pending)
            self._append_tool_result(call.id, result)
            if self.clock() >= deadline:
                return self._tool_completed_after_timeout()
        return self._reply("Limite de chamadas de tools atingido; operação interrompida com segurança.")

    def _deadline(self) -> float:
        return self.clock() + self.request_timeout_seconds

    def _timeout_reply(self) -> AgentReply:
        seconds = f"{self.request_timeout_seconds:g}"
        return self._reply(
            f"Tempo limite de {seconds} segundos atingido enquanto aguardava o llama-server."
        )

    def _tool_completed_after_timeout(self) -> AgentReply:
        return self._reply(
            "A tool foi concluída, mas o limite de tempo da interação foi atingido "
            "antes da resposta final."
        )

    def _reply(self, text: str, pending: PendingAction | None = None) -> AgentReply:
        if text:
            self.transcript.append({"role": "assistant", "content": text})
        return AgentReply(text, pending)

    def _append_tool_result(self, call_id: str, result: ToolResult) -> None:
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(result.as_dict(), ensure_ascii=False, default=str),
            }
        )

    @staticmethod
    def _assistant_dict(message: AssistantMessage) -> Message:
        payload: Message = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            payload["tool_calls"] = [call.model_dump() for call in message.tool_calls]
        return payload

    @staticmethod
    def _confirmation_message(action: PendingAction) -> str:
        arguments = json.dumps(action.arguments, ensure_ascii=False, indent=2)
        return (
            "A ação abaixo precisa de confirmação:\n\n"
            f"{action.tool_name}\n{arguments}\n\n"
            f"action_id: {action.id}\nExpira em: {action.expires_at.isoformat()}"
        )

    def _current_pending(self) -> PendingAction | None:
        return next((pending for _, pending in self._pending_calls.values()), None)
