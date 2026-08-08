from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from jarvis.agent.prompts import SYSTEM_PROMPT
from jarvis.llm.client import LLM
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
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.max_tool_rounds = max_tool_rounds
        self.messages: list[Message] = [{"role": "system", "content": system_prompt}]
        self._pending_calls: dict[str, tuple[str, PendingAction]] = {}

    def handle(self, user_text: str) -> AgentReply:
        if self._pending_calls:
            return AgentReply("Há uma ação aguardando confirmação.", self._current_pending())
        self.messages.append({"role": "user", "content": user_text})
        return self._run()

    def confirm(self, action_id: str) -> AgentReply:
        pending_call = self._pending_calls.pop(action_id, None)
        if pending_call is None:
            return AgentReply("Ação pendente inexistente ou diferente.")
        call_id, _ = pending_call
        try:
            result = self.registry.confirm(action_id)
        except (ConfirmationError, ValueError) as error:
            result = ToolResult("error", {"error": str(error)})
        self._append_tool_result(call_id, result)
        return self._run()

    def cancel(self, action_id: str) -> AgentReply:
        pending_call = self._pending_calls.pop(action_id, None)
        if pending_call is None:
            return AgentReply("Ação pendente inexistente ou diferente.")
        call_id, _ = pending_call
        result = self.registry.cancel(action_id)
        self._append_tool_result(call_id, result)
        return self._run()

    def _run(self) -> AgentReply:
        for _ in range(self.max_tool_rounds):
            assistant = self.llm.chat(self.messages, self.registry.schemas())
            self.messages.append(self._assistant_dict(assistant))
            if not assistant.tool_calls:
                return AgentReply(assistant.content or "")
            if len(assistant.tool_calls) != 1:
                for call in assistant.tool_calls:
                    self._append_tool_result(
                        call.id,
                        ToolResult("error", {"error": "Solicite somente uma tool por resposta"}),
                    )
                continue
            call = assistant.tool_calls[0]
            result = self.registry.request(call.function.name, call.function.arguments)
            if result.pending:
                self._pending_calls[result.pending.id] = (call.id, result.pending)
                return AgentReply(self._confirmation_message(result.pending), result.pending)
            self._append_tool_result(call.id, result)
        return AgentReply("Limite de chamadas de tools atingido; operação interrompida com segurança.")

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
