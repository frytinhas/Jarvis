from __future__ import annotations

import re
import sys

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
    def __init__(self, orchestrator: Orchestrator, assistant_name: str = "Jarvis") -> None:
        self.orchestrator = orchestrator
        self.assistant_name = assistant_name

    def run(self, initial_message: str | None = None, continue_after_initial: bool = True) -> None:
        mark = "\033[38;5;208m◉\033[0m" if sys.stdout.isatty() else "◉"
        print(f"{mark} {self.assistant_name} local. Digite /sair para encerrar.")
        if initial_message:
            self._handle(initial_message)
            if not continue_after_initial:
                return
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
            print(f"{self.assistant_name}: erro de comunicação: {error}")

    def _show(self, reply: AgentReply) -> None:
        print(f"\n{self.assistant_name}:\n{reply.text}")
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
