from __future__ import annotations

import re
import sys

from jarvis.agent.orchestrator import AgentReply, Orchestrator
from jarvis.legal import COPYRIGHT_NOTICE, STARTUP_LICENSE_NOTICE, license_text
from jarvis.ui.waiting import WaitingIndicator


POSITIVE = {"s", "sim", "y", "yes", "pode", "confirmo", "execute", "faça", "faca"}
NEGATIVE = {"n", "não", "nao", "no", "cancela", "cancelar", "deixa"}
LICENSE_COMMANDS = {"/licenca", "/licença", "/license"}


def confirmation_intent(text: str) -> bool | None:
    normalized = text.strip().lower()
    first_word = re.split(r"[\s,.;:!?]+", normalized, maxsplit=1)[0]
    if first_word in POSITIVE:
        return True
    if first_word in NEGATIVE:
        return False
    return None


class TerminalUI:
    def __init__(
        self,
        orchestrator: Orchestrator,
        assistant_name: str = "Jarvis",
        startup_warning: str | None = None,
        waiting_messages: list[str] | None = None,
        waiting_indicator: WaitingIndicator | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.assistant_name = assistant_name
        self.startup_warning = startup_warning
        self.waiting = waiting_indicator or WaitingIndicator(waiting_messages or [])

    def run(self, initial_message: str | None = None, continue_after_initial: bool = True) -> None:
        mark = "\033[38;5;208m◉\033[0m" if sys.stdout.isatty() else "◉"
        print(f"{mark} {self.assistant_name} local. Digite /sair para encerrar.")
        print(COPYRIGHT_NOTICE)
        print(STARTUP_LICENSE_NOTICE)
        if self.startup_warning:
            print(f"AVISO: {self.startup_warning}")
        if initial_message:
            if not self._handle_local_command(initial_message):
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
            if self._handle_local_command(user_text):
                continue
            self._handle(user_text)

    @staticmethod
    def _handle_local_command(user_text: str) -> bool:
        if user_text.strip().lower() not in LICENSE_COMMANDS:
            return False
        print(f"\n{license_text()}")
        return True

    def _handle(self, user_text: str) -> None:
        try:
            with self.waiting.active():
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
            with self.waiting.active():
                follow_up = (
                    self.orchestrator.confirm(reply.pending.id)
                    if intent
                    else self.orchestrator.cancel(reply.pending.id)
                )
            self._show(follow_up)
            return
