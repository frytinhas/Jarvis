from __future__ import annotations

import re

from jarvis.agent.orchestrator import AgentReply, Orchestrator


POSITIVE = {"s", "sim", "y", "yes", "pode", "confirmo", "execute", "faça", "faca"}
NEGATIVE = {"n", "não", "nao", "no", "cancela", "cancelar", "deixa"}


def confirmation_intent(text: str) -> bool | None:
    normalized = text.strip().lower()
    first_word = re.split(r"[\s,.;:!?]+", normalized, maxsplit=1)[0]
    if first_word in POSITIVE:
        return True
    if first_word in NEGATIVE:
        return False
    return None


class TerminalUI:
    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator

    def run(self, initial_message: str | None = None) -> None:
        print("Jarvis local. Digite /sair para encerrar.")
        if initial_message:
            self._handle(initial_message)
        while True:
            try:
                user_text = input("\nVocê > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAté logo.")
                return
            if user_text.lower() in {"/sair", "/exit", "/quit"}:
                return
            if not user_text:
                continue
            self._handle(user_text)

    def _handle(self, user_text: str) -> None:
        try:
            reply = self.orchestrator.handle(user_text)
            self._show(reply)
        except Exception as error:
            print(f"Jarvis: erro de comunicação: {error}")

    def _show(self, reply: AgentReply) -> None:
        print(f"\nJarvis:\n{reply.text}")
        if reply.pending is None:
            return
        while True:
            answer = input("Confirmar? [y/N] ")
            intent = confirmation_intent(answer)
            if intent is None:
                print("Responda sim ou não.")
                continue
            follow_up = (
                self.orchestrator.confirm(reply.pending.id)
                if intent
                else self.orchestrator.cancel(reply.pending.id)
            )
            self._show(follow_up)
            return
