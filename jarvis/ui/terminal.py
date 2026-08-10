from __future__ import annotations

import json
import os
from pathlib import Path
import random
import re
import sys
from typing import Callable

from jarvis.agent.orchestrator import AgentReply, Orchestrator
from jarvis.config import ConfigFileError, JarvisConfig
from jarvis.config import save_config
from jarvis.legal import COPYRIGHT_NOTICE, STARTUP_LICENSE_NOTICE, license_text
from jarvis.ui.commands import LocalCommands, SessionExit
from jarvis.ui.markdown import render_markdown
from jarvis.ui.theme import PLAIN_THEME, Theme
from jarvis.ui.waiting import WaitingIndicator
from jarvis.memory import LearningContextStore, summarize_conversation, summarize_learning
from jarvis.memory.learning import LearningSummaryError
from jarvis.security.input_guard import unsafe_chat_input_reason
from jarvis.ui.line_editor import read_line


POSITIVE = {"s", "sim", "y", "yes", "pode", "confirmo", "execute", "faça", "faca"}
NEGATIVE = {"n", "não", "nao", "no", "cancela", "cancelar", "deixa"}
LICENSE_COMMANDS = {"/licenca", "/licença", "/license"}
LEARNING_ALLOWED = {"/help", "/clear", "/license", "/licenca", "/licença", "/finish", "/exit", "/sair", "/quit"}

FIRST_LEARNING_NOTICE = (
    "FIRST-RUN LEARNING SESSION: nothing said here is saved unless you run /finish and explicitly "
    "approve the proposed summary. /exit, closing the terminal, or Ctrl+C discards this entire "
    "learning conversation. Describe only durable preferences, projects, and constraints. Never "
    "provide passwords, tokens, credentials, or other secrets. Mentioned paths are context only; "
    "they never grant access or authorize tools."
)

LEARNING_NOTICE = (
    "Learning session: only a summary explicitly approved with /finish can replace the existing "
    "learning context. Exiting discards this session. Never provide secrets; paths are context only "
    "and never authorize tools."
)


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
        learning_store: LearningContextStore | None = None,
        learning_mode: bool = False,
        learning_prompt: str | None = None,
        normal_prompt: Callable[[str], str] | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.assistant_name = assistant_name
        self.startup_warning = startup_warning
        self.waiting = waiting_indicator or WaitingIndicator(waiting_messages or [])
        self.goodbye_messages = goodbye_messages or []
        self.theme = theme
        self.show_license_notice = show_license_notice
        self.commands = LocalCommands(orchestrator, config) if config is not None else None
        self.config = config
        self.learning_store = learning_store
        self.learning_mode = learning_mode
        self.learning_prompt = learning_prompt
        self.normal_prompt = normal_prompt
        self.completed_transcripts: list[tuple[list[dict[str, str]], object, object]] = []
        self._first_learning_session = learning_mode

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
        if self.learning_mode:
            self._show_learning_notice(first_run=self._first_learning_session)
        if initial_message:
            action = self._handle_local_command(initial_message)
            if action is None:
                if self._unsafe_message(initial_message):
                    print(self.theme.paint("Mensagem inicial bloqueada; remova os marcadores internos e tente novamente.", "warning"))
                else:
                    self._handle(initial_message)
            elif action is not SessionExit.CONTINUE:
                return action
            if not continue_after_initial:
                return SessionExit.EXIT
        while True:
            try:
                prompt = self.theme.paint("Você > ", "user", strong=True)
                print()
                user_text = read_line(
                    prompt, validator=unsafe_chat_input_reason,
                    completer=self.commands.completion_candidates if self.commands else None,
                    blocked_message="Mensagem bloqueada",
                ).strip()
            except (EOFError, KeyboardInterrupt):
                return self._exit()
            if not user_text:
                continue
            if self._unsafe_message(user_text):
                print(self.theme.paint("Mensagem bloqueada; remova os marcadores internos e tente novamente.", "warning"))
                continue
            lowered = user_text.lower()
            if self.learning_mode:
                command = lowered.partition(" ")[0]
                if command == "/finish":
                    if not self._finish_learning():
                        continue
                    continue
                if command in {"/exit", "/sair"}:
                    return self._exit()
                if command == "/quit":
                    return self._exit(SessionExit.FULL_STOP)
                if command == "/help":
                    print("\nDurante o aprendizado: converse normalmente e use /finish, /exit ou /quit para propor o resumo. /clear e /license também estão disponíveis.")
                    continue
                if command.startswith("/") and command not in LEARNING_ALLOWED:
                    print(self.theme.paint(
                        "Este comando fica bloqueado durante o aprendizado. Use /finish, /exit ou /quit.",
                        "warning",
                    ))
                    continue
            elif lowered == "/learning":
                if self._enter_learning():
                    continue
            if lowered in {"/sair", "/exit"}:
                return self._exit()
            action = self._handle_local_command(user_text)
            if action is not None:
                if action is not SessionExit.CONTINUE:
                    return action
                continue
            self._handle(user_text)

    def _exit(self, action: SessionExit = SessionExit.EXIT) -> SessionExit:
        self._discard_learning()
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
        if result.ask_profile_switch:
            while True:
                answer = input("Confirmar a troca de perfil? [y/N] ")
                intent = confirmation_intent(answer)
                if intent is None and answer.strip():
                    print("Responda sim ou não.")
                    continue
                if intent is not True:
                    return SessionExit.CONTINUE
                try:
                    handoff = summarize_conversation(self.orchestrator.llm, self.orchestrator.transcript)
                    self._write_switch_request(result.target_profile, handoff)
                except Exception as error:
                    print(self.theme.paint(f"Não foi possível preparar a troca: {error}", "error"))
                    return SessionExit.CONTINUE
                return SessionExit.SWITCH_PROFILE
        if result.action is SessionExit.FULL_STOP:
            print(self.theme.paint("Finalizando memória em segundo plano e desligando o servidor.", "warning"))
            return self._exit(SessionExit.FULL_STOP)
        return result.action

    def _enter_learning(self) -> bool:
        if self.learning_store is None or self.learning_prompt is None or self.config is None:
            print(self.theme.paint("O aprendizado não está disponível nesta sessão.", "error"))
            return True
        print(self.theme.paint(
            "O contexto de aprendizado anterior será substituído somente depois que você aprovar "
            "um novo resumo. A sessão atual será encerrada e salva normalmente.",
            "warning",
        ))
        answer = input("Iniciar um novo aprendizado? [y/N] ")
        if confirmation_intent(answer) is not True:
            return True
        if self.orchestrator.transcript:
            self.completed_transcripts.append((
                list(self.orchestrator.transcript), self.orchestrator.started_at, Path.cwd().resolve()
            ))
        settings = self.config.settings.model_copy(update={"learning_state": "pending"})
        pending_config = self.config.model_copy(update={"settings": settings})
        try:
            save_config(pending_config)
        except (ConfigFileError, OSError, ValueError) as error:
            print(self.theme.paint(f"Não foi possível iniciar o aprendizado: {error}", "error"))
            return True
        self.config = pending_config
        if self.commands is not None:
            self.commands.config = self.config
        self.orchestrator.reset_session(self.learning_prompt)
        self.learning_mode = True
        self._first_learning_session = False
        self._show_learning_notice(first_run=False)
        return True

    def _finish_learning(self) -> bool:
        if self.learning_store is None or self.config is None or self.normal_prompt is None:
            print(self.theme.paint("O aprendizado não está disponível nesta sessão.", "error"))
            return False
        try:
            with self.waiting.active():
                summary = summarize_learning(
                    self.orchestrator.llm,
                    self.orchestrator.transcript,
                    self.config.settings.context_size,
                )
        except LearningSummaryError as error:
            print(self.theme.paint(
                f"O resumo proposto foi recusado ({error}). Continue o aprendizado e tente /finish novamente.",
                "warning",
            ))
            return False
        except Exception as error:
            print(self.theme.paint(f"Não foi possível resumir o aprendizado: {error}", "error"))
            return False
        if not summary:
            print(self.theme.paint(
                "Ainda não há informações úteis suficientes. Continue explicando e tente /finish novamente.",
                "warning",
            ))
            return False
        print("\nResumo privado proposto:\n")
        print(render_markdown(summary, self.theme))
        answer = input("Aprovar e substituir o contexto de aprendizado? [y/N] ")
        if confirmation_intent(answer) is not True:
            print("Resumo rejeitado. O contexto anterior foi preservado; continue o aprendizado.")
            return False
        previous_learning = self.learning_store.read()
        settings = self.config.settings.model_copy(update={"learning_state": "complete"})
        completed_config = self.config.model_copy(update={"settings": settings})
        try:
            self.learning_store.replace(summary, self.config.settings.context_size)
            save_config(completed_config)
        except (ConfigFileError, OSError, ValueError) as error:
            try:
                self.learning_store.restore(previous_learning)
            except OSError:
                pass
            print(self.theme.paint(f"Não foi possível salvar o aprendizado: {error}", "error"))
            return False
        self.config = completed_config
        if self.commands is not None:
            self.commands.config = self.config
        self.orchestrator.reset_session(self.normal_prompt(summary))
        self.learning_mode = False
        print("Aprendizado aprovado. Uma nova conversa normal foi iniciada neste terminal.")
        return True

    def _unsafe_message(self, user_text: str) -> bool:
        return unsafe_chat_input_reason(user_text) is not None

    def _show_learning_notice(self, *, first_run: bool) -> None:
        notice = FIRST_LEARNING_NOTICE if first_run else LEARNING_NOTICE
        role = "error" if first_run else "warning"
        print(self.theme.paint(notice, role, strong=first_run))

    def _discard_learning(self) -> None:
        """Forget the in-memory onboarding conversation before ending the terminal."""
        if not self.learning_mode:
            return
        self.orchestrator.discard_session(self.learning_prompt or "")
        if not self._first_learning_session and self.config is not None:
            settings = self.config.settings.model_copy(update={"learning_state": "complete"})
            restored_config = self.config.model_copy(update={"settings": settings})
            try:
                save_config(restored_config)
            except (ConfigFileError, OSError, ValueError) as error:
                print(self.theme.paint(f"Could not restore the prior learning state: {error}", "error"))
            else:
                self.config = restored_config
                if self.commands is not None:
                    self.commands.config = self.config

    def _write_switch_request(self, target: str | None, handoff: str) -> None:
        request_path = os.environ.get("JARVIS_SWITCH_REQUEST_PATH")
        if not request_path or not target:
            raise OSError("O launcher não preparou uma troca de perfil segura")
        path = Path(request_path).expanduser().absolute()
        if path.is_symlink():
            raise OSError("O pedido de troca não pode ser um symlink")
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"target": target, "handoff": handoff}, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        temporary.replace(path)

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
