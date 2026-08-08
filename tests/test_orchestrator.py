from __future__ import annotations

import json
from pathlib import Path

from jarvis.agent.orchestrator import Orchestrator
from jarvis.llm.client import LLMTimeoutError
from jarvis.llm.schemas import AssistantMessage, ToolCall, ToolFunctionCall
from jarvis.tools.registry import ToolRegistry
from jarvis.ui.terminal import confirmation_intent
from jarvis.ui.terminal import TerminalUI


class SequencedLLM:
    def __init__(self, responses: list[AssistantMessage]) -> None:
        self.responses = iter(responses)

    def chat(self, messages, tools, timeout=None):  # type: ignore[no-untyped-def]
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


def test_orchestrator_keeps_visible_transcript(registry: ToolRegistry) -> None:
    llm = SequencedLLM([AssistantMessage(content="Resposta lembrável")])
    agent = Orchestrator(llm, registry)

    agent.handle("Pergunta lembrável")

    assert agent.transcript == [
        {"role": "user", "content": "Pergunta lembrável"},
        {"role": "assistant", "content": "Resposta lembrável"},
    ]


def test_orchestrator_passes_remaining_interaction_time_to_each_model_call(
    registry: ToolRegistry, tmp_path: Path
) -> None:
    call = ToolCall(
        id="one",
        function=ToolFunctionCall(
            name="file_info",
            arguments=json.dumps({"path": str(tmp_path)}),
        ),
    )

    class TimedLLM(SequencedLLM):
        def __init__(self) -> None:
            super().__init__([AssistantMessage(tool_calls=[call]), AssistantMessage(content="ok")])
            self.timeouts: list[float] = []

        def chat(self, messages, tools, timeout=None):  # type: ignore[no-untyped-def]
            self.timeouts.append(timeout)
            return super().chat(messages, tools, timeout)

    times = iter([0.0, 1.0, 1.0, 2.0, 2.0, 2.0])
    llm = TimedLLM()
    agent = Orchestrator(
        llm, registry, interaction_timeout_seconds=10,
        llm_request_timeout_seconds=120, clock=lambda: next(times),
    )

    reply = agent.handle("Consulte")

    assert reply.text == "ok"
    assert llm.timeouts == [10.0, 8.0]


def test_orchestrator_does_not_start_tool_after_deadline(registry: ToolRegistry) -> None:
    call = ToolCall(
        id="one",
        function=ToolFunctionCall(name="get_current_directory", arguments="{}"),
    )
    llm = SequencedLLM([AssistantMessage(tool_calls=[call])])
    times = iter([0.0, 61.0])
    agent = Orchestrator(llm, registry, interaction_timeout_seconds=60, clock=lambda: next(times))

    reply = agent.handle("Onde estou?")

    assert "Timeout total do Jarvis" in reply.text
    assert "60 segundos" in reply.text
    assert not any(message["role"] == "tool" for message in agent.messages)


def test_orchestrator_turns_llm_timeout_into_clear_reply(registry: ToolRegistry) -> None:
    class TimedOutLLM:
        def chat(self, messages, tools, timeout=None):  # type: ignore[no-untyped-def]
            raise LLMTimeoutError

    agent = Orchestrator(TimedOutLLM(), registry, llm_request_timeout_seconds=30)

    reply = agent.handle("Oi")

    assert "Timeout do Jarvis por chamada ao LLM" in reply.text
    assert "30 segundos" in reply.text


def test_orchestrator_allows_128_tools_then_a_final_answer(registry: ToolRegistry) -> None:
    calls = [
        AssistantMessage(tool_calls=[ToolCall(
            id=f"call-{index}",
            function=ToolFunctionCall(name="get_current_directory", arguments="{}"),
        )])
        for index in range(128)
    ]
    llm = SequencedLLM([*calls, AssistantMessage(content="concluído")])
    agent = Orchestrator(llm, registry, max_tool_rounds=128)

    assert agent.handle("faça uma tarefa longa").text == "concluído"


def test_confirmation_wait_does_not_consume_total_timeout(
    registry: ToolRegistry, tmp_path: Path
) -> None:
    call = ToolCall(
        id="write",
        function=ToolFunctionCall(
            name="write_file",
            arguments=json.dumps({"path": str(tmp_path / "file.txt"), "content": "ok"}),
        ),
    )
    (tmp_path / "file.txt").write_text("old", encoding="utf-8")
    llm = SequencedLLM([AssistantMessage(tool_calls=[call]), AssistantMessage(content="feito")])
    now = [0.0]
    agent = Orchestrator(
        llm, registry, interaction_timeout_seconds=10, clock=lambda: now[0]
    )

    pending = agent.handle("altere")
    assert pending.pending is not None
    now[0] = 10_000.0
    reply = agent.confirm(pending.pending.id)

    assert reply.text == "feito"


def test_tool_limit_keeps_history_valid_for_the_next_user_turn(registry: ToolRegistry) -> None:
    tool_messages = [
        AssistantMessage(tool_calls=[ToolCall(
            id=f"call-{index}",
            function=ToolFunctionCall(name="get_current_directory", arguments="{}"),
        )])
        for index in range(3)
    ]
    llm = SequencedLLM([*tool_messages, AssistantMessage(content="nova resposta")])
    agent = Orchestrator(llm, registry, max_tool_rounds=2)

    limited = agent.handle("loop")
    assert "2 ciclos" in limited.text
    assert len([message for message in agent.messages if message["role"] == "assistant"]) == 2
    assert agent.handle("continue").text == "nova resposta"
