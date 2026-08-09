from __future__ import annotations

from contextlib import contextmanager
import random
import re
import sys
from typing import Iterator

from jarvis.agent.orchestrator import AgentReply, Orchestrator
from jarvis.config import ConfigFileError, JarvisConfig
from jarvis.legal import COPYRIGHT_NOTICE, STARTUP_LICENSE_NOTICE, license_text
from jarvis.ui.commands import LocalCommands, SessionExit
from jarvis.ui.markdown import render_markdown
from jarvis.ui.theme import PLAIN_THEME, Theme
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
        goodbye_messages: list[str] | None = None,
        waiting_indicator: WaitingIndicator | None = None,
        config: JarvisConfig | None = None,
        theme: Theme = PLAIN_THEME,
        show_license_notice: bool = False,
    ) -> None:
        self.orchestrator = orchestrator
        self.assistant_name = assistant_name
        self.startup_warning = startup_warning
        self.waiting = waiting_indicator or WaitingIndicator(waiting_messages or [])
        self.goodbye_messages = goodbye_messages or []
        self.theme = theme
        self.show_license_notice = show_license_notice
        self.commands = LocalCommands(orchestrator, config) if config is not None else None

    def run(
        self, initial_message: str | None = None, continue_after_initial: bool = True
    ) -> SessionExit:
        mark = self.theme.paint("◉", "primary", strong=True)
        print(f"{mark} {self.assistant_name} local. Digite /help para ver os comandos.")
        print(COPYRIGHT_NOTICE)
        if self.show_license_notice:
            print(self.theme.paint(STARTUP_LICENSE_NOTICE, "warning"))
        if self.startup_warning:
            print(self.theme.paint(f"AVISO: {self.startup_warning}", "warning"))
        if initial_message:
            action = self._handle_local_command(initial_message)
            if action is None:
                self._handle(initial_message)
            elif action is not SessionExit.CONTINUE:
                return action
            if not continue_after_initial:
                return SessionExit.EXIT
        with self._completion():
            while True:
                try:
                    prompt = self.theme.paint("Você > ", "user", strong=True)
                    user_text = input(f"\n{prompt}").strip()
                except (EOFError, KeyboardInterrupt):
                    return self._exit()
                if not user_text:
                    continue
                if user_text.lower() in {"/sair", "/exit"}:
                    return self._exit()
                action = self._handle_local_command(user_text)
                if action is not None:
                    if action is not SessionExit.CONTINUE:
                        return action
                    continue
                self._handle(user_text)

    def _exit(self, action: SessionExit = SessionExit.EXIT) -> SessionExit:
        message = random.choice(self.goodbye_messages) if self.goodbye_messages else "Até logo."
        label = self.theme.paint(f"{self.assistant_name}:", "assistant", strong=True)
        print(f"\n{label}\n{render_markdown(message, self.theme)}")
        return action

    def _handle_local_command(self, user_text: str) -> SessionExit | None:
        if self.commands is None:
            if user_text.strip().lower() not in LICENSE_COMMANDS:
                return None
            print(f"\n{license_text()}")
            return SessionExit.CONTINUE
        try:
            result = self.commands.handle(user_text)
        except (ConfigFileError, OSError, ValueError) as error:
            print(self.theme.paint(f"Não foi possível aplicar o comando: {error}", "error"))
            return SessionExit.CONTINUE
        if not result.handled:
            return None
        if result.clear_screen:
            print("\033[2J\033[H" if sys.stdout.isatty() else "\n" * 3, end="")
        if result.text:
            print(f"\n{render_markdown(result.text, self.theme)}")
        if result.ask_model_restart:
            while True:
                answer = input("Reiniciar o servidor e abrir uma nova sessão agora? [y/N] ")
                intent = confirmation_intent(answer)
                if intent is None and answer.strip():
                    print("Responda sim ou não.")
                    continue
                return SessionExit.RESTART_MODEL if intent is True else SessionExit.CONTINUE
        if result.action is SessionExit.FULL_STOP:
            print(self.theme.paint("Finalizando memória em segundo plano e desligando o servidor.", "warning"))
            return self._exit(SessionExit.FULL_STOP)
        return result.action

    @contextmanager
    def _completion(self) -> Iterator[None]:
        if self.commands is None or not sys.stdin.isatty():
            yield
            return
        try:
            import readline
        except ImportError:
            yield
            return
        previous = readline.get_completer()
        previous_delimiters = readline.get_completer_delims()
        matches: list[str] = []

        def complete(text: str, state: int) -> str | None:
            nonlocal matches
            if state == 0:
                matches = self.commands.completion_candidates(readline.get_line_buffer())
            return matches[state] if state < len(matches) else None

        readline.set_completer_delims("")
        readline.set_completer(complete)
        readline.parse_and_bind("tab: complete")
        try:
            yield
        finally:
            readline.set_completer(previous)
            readline.set_completer_delims(previous_delimiters)

    def _handle(self, user_text: str) -> None:
        try:
            with self.waiting.active():
                reply = self.orchestrator.handle(user_text)
            self._show(reply)
        except Exception as error:
            message = f"{self.assistant_name}: erro de comunicação: {error}"
            print(self.theme.paint(message, "error"))

    def _show(self, reply: AgentReply) -> None:
        label = self.theme.paint(f"{self.assistant_name}:", "assistant", strong=True)
        print(f"\n{label}\n{render_markdown(reply.text, self.theme)}")
        if reply.tool_grammar_failed:
            answer = input("Desativar tools nesta sessão para este modelo? [Y/n] ").strip()
            if answer.lower() not in {"n", "no", "não", "nao"}:
                self.orchestrator.disable_tools_for_session()
            return
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
