from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from typing import Any

from jarvis.agent.prompts import SYSTEM_PROMPT
from jarvis.agent.tool_routing import ToolRoute, route_user_request
from jarvis.llm.client import LLM, LLMTimeoutError
from jarvis.llm.schemas import AssistantMessage, Message
from jarvis.security.confirmation import ConfirmationError, PendingAction
from jarvis.security.policy import Risk
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
        max_tool_rounds: int = 128,
        interaction_timeout_seconds: float = 600.0,
        llm_request_timeout_seconds: float = 120.0,
        system_prompt: str = SYSTEM_PROMPT,
        thinking_budget_tokens: int | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if interaction_timeout_seconds <= 0 or llm_request_timeout_seconds <= 0:
            raise ValueError("timeouts devem ser positivos")
        if max_tool_rounds <= 0:
            raise ValueError("max_tool_rounds deve ser positivo")
        self.llm = llm
        self.registry = registry
        self.max_tool_rounds = max_tool_rounds
        self.interaction_timeout_seconds = interaction_timeout_seconds
        self.llm_request_timeout_seconds = llm_request_timeout_seconds
        self.clock = clock or time.monotonic
        self.thinking_budget_tokens = thinking_budget_tokens
        self.messages: list[Message] = [{"role": "system", "content": system_prompt}]
        self.transcript: list[dict[str, str]] = []
        self.started_at = datetime.now(timezone.utc)
        self._pending_calls: dict[str, tuple[str, PendingAction]] = {}
        self._active_seconds = 0.0
        self._tool_rounds = 0
        self._route = ToolRoute()
        self._route_requirement_satisfied = True
        self._route_retry_used = False

    def handle(self, user_text: str) -> AgentReply:
        if self._pending_calls:
            return self._reply("Há uma ação aguardando confirmação.", self._current_pending())
        self.transcript.append({"role": "user", "content": user_text})
        self.messages.append({"role": "user", "content": user_text})
        self._active_seconds = 0.0
        self._tool_rounds = 0
        self._route = route_user_request(user_text)
        self._route_requirement_satisfied = not self._route.require_tool
        self._route_retry_used = False
        unavailable = self._route_unavailable_reply()
        if unavailable is not None:
            return unavailable
        try:
            return self._run()
        except KeyboardInterrupt:
            return self._cancelled_reply()

    def confirm(self, action_id: str) -> AgentReply:
        pending_call = self._pending_calls.pop(action_id, None)
        if pending_call is None:
            return self._reply("Ação pendente inexistente ou diferente.")
        self.transcript.append({"role": "user", "content": "[Ação confirmada pelo usuário]"})
        call_id, _ = pending_call
        started = self.clock()
        try:
            result = self.registry.confirm(action_id)
        except KeyboardInterrupt:
            self._append_tool_result(
                call_id,
                ToolResult("cancelled", {"cancelled": True, "error": "Execução cancelada pelo usuário."}),
            )
            return self._cancelled_reply()
        except (ConfirmationError, ValueError) as error:
            result = ToolResult("error", {"error": str(error)})
        self._active_seconds += max(0.0, self.clock() - started)
        self._append_tool_result(call_id, result)
        if self._active_seconds >= self.interaction_timeout_seconds:
            return self._tool_completed_after_timeout()
        try:
            return self._run()
        except KeyboardInterrupt:
            return self._cancelled_reply()

    def cancel(self, action_id: str) -> AgentReply:
        pending_call = self._pending_calls.pop(action_id, None)
        if pending_call is None:
            return self._reply("Ação pendente inexistente ou diferente.")
        self.transcript.append({"role": "user", "content": "[Ação cancelada pelo usuário]"})
        call_id, _ = pending_call
        started = self.clock()
        result = self.registry.cancel(action_id)
        self._active_seconds += max(0.0, self.clock() - started)
        self._append_tool_result(call_id, result)
        if self._active_seconds >= self.interaction_timeout_seconds:
            return self._total_timeout_reply()
        try:
            return self._run()
        except KeyboardInterrupt:
            return self._cancelled_reply()

    def _run(self) -> AgentReply:
        while True:
            remaining = self.interaction_timeout_seconds - self._active_seconds
            if remaining <= 0:
                return self._total_timeout_reply()
            request_timeout = min(remaining, self.llm_request_timeout_seconds)
            restricted = not self._route_requirement_satisfied and self._route.tool_names is not None
            schemas = self.registry.schemas(
                set(self._route.tool_names) if restricted and self._route.tool_names is not None else None
            )
            request_messages = self.messages
            if restricted and self._route_retry_used:
                request_messages = [
                    *self.messages,
                    {
                        "role": "system",
                        "content": (
                            "A solicitação atual exige uma tool. Não responda com fatos, perguntas "
                            "de permissão ou suposições: chame exatamente uma das tools fornecidas."
                        ),
                    },
                ]
            started = self.clock()
            reasoning_arguments = (
                {"thinking_budget_tokens": self.thinking_budget_tokens}
                if self.thinking_budget_tokens is not None
                else {}
            )
            try:
                if restricted:
                    assistant = self.llm.chat(
                        request_messages,
                        schemas,
                        timeout=request_timeout,
                        tool_choice="required",
                        **reasoning_arguments,
                    )
                else:
                    assistant = self.llm.chat(
                        self.messages,
                        schemas,
                        timeout=request_timeout,
                        **reasoning_arguments,
                    )
            except LLMTimeoutError:
                self._active_seconds += max(0.0, self.clock() - started)
                if remaining <= self.llm_request_timeout_seconds:
                    return self._total_timeout_reply()
                return self._llm_timeout_reply()
            self._active_seconds += max(0.0, self.clock() - started)
            if self._active_seconds >= self.interaction_timeout_seconds:
                return self._total_timeout_reply()
            if not assistant.tool_calls:
                if not self._route_requirement_satisfied:
                    if not self._route_retry_used:
                        self._route_retry_used = True
                        continue
                    return self._strict_tool_failure_reply()
                self.messages.append(self._assistant_dict(assistant))
                return self._complete_reply(assistant.content or "")
            if self._tool_rounds >= self.max_tool_rounds:
                return self._complete_reply(
                    f"Limite do Jarvis de {self.max_tool_rounds} ciclos de tools atingido. "
                    "Altere em jarvis-config → Comportamento."
                )
            self._tool_rounds += 1
            self.messages.append(self._assistant_dict(assistant))
            if len(assistant.tool_calls) != 1:
                for call in assistant.tool_calls:
                    self._append_tool_result(
                        call.id,
                        ToolResult("error", {"error": "Solicite somente uma tool por resposta"}),
                    )
                continue
            call = assistant.tool_calls[0]
            self._route_requirement_satisfied = True
            if (
                self.registry.risk_for(call.function.name) is Risk.EXECUTE
                and not self._route.execution_authorized
            ):
                result = self.registry.reject(
                    call.function.name,
                    call.function.arguments,
                    "Execução rejeitada: o pedido original do usuário não autorizou execução.",
                )
                self._append_tool_result(call.id, result)
                continue
            started = self.clock()
            try:
                result = self.registry.request(call.function.name, call.function.arguments)
            except KeyboardInterrupt:
                self._append_tool_result(
                    call.id,
                    ToolResult("cancelled", {"cancelled": True, "error": "Execução cancelada pelo usuário."}),
                )
                raise
            self._active_seconds += max(0.0, self.clock() - started)
            if result.pending:
                self._pending_calls[result.pending.id] = (call.id, result.pending)
                return self._reply(self._confirmation_message(result.pending), result.pending)
            self._append_tool_result(call.id, result)
            if self._active_seconds >= self.interaction_timeout_seconds:
                return self._tool_completed_after_timeout()

    def _llm_timeout_reply(self) -> AgentReply:
        seconds = f"{self.llm_request_timeout_seconds:g}"
        return self._complete_reply(
            f"Timeout do Jarvis por chamada ao LLM atingido ({seconds} segundos). "
            "Altere em jarvis-config → Timeouts."
        )

    @property
    def active_seconds(self) -> float:
        return self._active_seconds

    def set_thinking_budget_tokens(self, value: int) -> None:
        self.thinking_budget_tokens = value

    def _total_timeout_reply(self) -> AgentReply:
        seconds = f"{self.interaction_timeout_seconds:g}"
        return self._complete_reply(
            f"Timeout total do Jarvis atingido ({seconds} segundos de processamento ativo). "
            "Altere em jarvis-config → Timeouts."
        )

    def _tool_completed_after_timeout(self) -> AgentReply:
        return self._complete_reply(
            "A tool foi concluída, mas o limite de tempo da interação foi atingido "
            f"({self.interaction_timeout_seconds:g} segundos). "
            "Altere em jarvis-config → Timeouts."
        )

    def _route_unavailable_reply(self) -> AgentReply | None:
        if not self._route.require_tool or self._route.tool_names is None:
            return None
        available = {
            schema["function"]["name"]
            for schema in self.registry.schemas(set(self._route.tool_names))
        }
        required = {"execute_file"} if self._route.label == "execute" else set(self._route.tool_names)
        if available & required:
            return None
        text = (
            "Não posso atender essa solicitação porque a tool necessária está indisponível "
            "pela política ou pela configuração de paths atual."
        )
        self.messages.append({"role": "assistant", "content": text})
        return self._complete_reply(text)

    def _strict_tool_failure_reply(self) -> AgentReply:
        text = (
            "Não consegui consultar a tool obrigatória para responder com dados reais. "
            "Nenhuma informação foi presumida."
        )
        self.messages.append({"role": "assistant", "content": text})
        return self._complete_reply(text)

    def _cancelled_reply(self) -> AgentReply:
        text = "Operação cancelada com Ctrl+C. O chat continua disponível."
        self.messages.append({"role": "assistant", "content": text})
        self._active_seconds = 0.0
        self._tool_rounds = 0
        return self._reply(text)

    def _complete_reply(self, text: str) -> AgentReply:
        reply = self._reply(text)
        self._active_seconds = 0.0
        self._tool_rounds = 0
        return reply

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
