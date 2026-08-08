from __future__ import annotations

import json
from pathlib import Path

from jarvis.agent.orchestrator import Orchestrator
from jarvis.llm.schemas import AssistantMessage, ToolCall, ToolFunctionCall
from jarvis.tools.registry import ToolRegistry
from jarvis.ui.terminal import confirmation_intent
from jarvis.ui.terminal import TerminalUI


class SequencedLLM:
    def __init__(self, responses: list[AssistantMessage]) -> None:
        self.responses = iter(responses)

    def chat(self, messages, tools):  # type: ignore[no-untyped-def]
        return next(self.responses)


def test_tool_errors_return_to_llm(registry: ToolRegistry, tmp_path: Path) -> None:
    call = ToolCall(
        id="one",
        function=ToolFunctionCall(name="read_file", arguments=json.dumps({"path": str(tmp_path / "missing")})),
    )
    llm = SequencedLLM([AssistantMessage(tool_calls=[call]), AssistantMessage(content="Não encontrei o arquivo.")])
    agent = Orchestrator(llm, registry)
    reply = agent.handle("Leia")
    assert reply.text == "Não encontrei o arquivo."
    tool_message = next(message for message in agent.messages if message["role"] == "tool")
    assert json.loads(tool_message["content"])["status"] == "error"


def test_voice_style_confirmation_only_authorizes_pending_clause() -> None:
    assert confirmation_intent("Sim, e apaga outro arquivo") is True
    assert confirmation_intent("não faça") is False
    assert confirmation_intent("talvez") is None


def test_terminal_sends_initial_message_and_stays_interactive(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    class FakeOrchestrator:
        def __init__(self) -> None:
            self.received: list[str] = []

        def handle(self, message: str):  # type: ignore[no-untyped-def]
            self.received.append(message)
            from jarvis.agent.orchestrator import AgentReply

            return AgentReply("Resposta")

    orchestrator = FakeOrchestrator()
    answers = iter(["segunda mensagem", "/sair"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    TerminalUI(orchestrator, "Bob").run("mensagem inicial")  # type: ignore[arg-type]

    assert orchestrator.received == ["mensagem inicial", "segunda mensagem"]
    assert "Bob local" in capsys.readouterr().out


def test_terminal_one_shot_does_not_request_another_message(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class FakeOrchestrator:
        def __init__(self) -> None:
            self.received: list[str] = []

        def handle(self, message: str):  # type: ignore[no-untyped-def]
            self.received.append(message)
            from jarvis.agent.orchestrator import AgentReply

            return AgentReply("Resposta")

    orchestrator = FakeOrchestrator()

    def unexpected_input(_: str) -> str:
        raise AssertionError("one-shot não deve abrir outro prompt")

    monkeypatch.setattr("builtins.input", unexpected_input)

    TerminalUI(orchestrator, "Bob").run("mensagem inicial", continue_after_initial=False)  # type: ignore[arg-type]

    assert orchestrator.received == ["mensagem inicial"]
