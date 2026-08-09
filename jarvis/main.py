from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys

from jarvis.agent.orchestrator import Orchestrator
from jarvis.agent.prompts import build_system_prompt
from jarvis.config import config_path, load_config, save_config
from jarvis.legal import consume_license_notice
from jarvis.llm.client import LLMNotice, LlamaClient
from jarvis.memory import ConversationLogStore, ProfileNotesStore
from jarvis.security.audit import AuditLog
from jarvis.security.confirmation import ConfirmationManager
from jarvis.security.path_policy import PathPolicy
from jarvis.security.policy import Decision, PolicyEngine, Risk
from jarvis.settings import DisplayLogLevel, MessageMode, project_root
from jarvis.tools.registry import build_registry
from jarvis.tools import system
from jarvis.ui.terminal import TerminalUI
from jarvis.ui.commands import SessionExit
from jarvis.ui.activity import ActivityPanel, maintain_runtime_logs
from jarvis.ui.theme import Theme
from jarvis.ui.waiting import WaitingIndicator, load_waiting_messages


REASONING_BUDGETS = {0: 0, 1: 512, 2: 1024, 3: 2048, 4: -1}


@dataclass(frozen=True)
class Invocation:
    message: str | None
    reasoning_level: int
    edit_resource: str | None = None


def parse_invocation(
    arguments: list[str] | None = None,
    prog: str = "jarvis",
    default_reasoning_level: int = 2,
) -> Invocation:
    parser = argparse.ArgumentParser(prog=prog, description="Assistente local")
    parser.add_argument(
        "--r", "--reasoning", type=int, choices=range(-1, 5), default=-1,
        metavar="N", help="reasoning: -1 padrão, 0 off, 1 low, 2 medium, 3 high, 4 max",
    )
    edit_group = parser.add_mutually_exclusive_group()
    for option, resource in (
        ("--blacklist", "blacklist"), ("--whitelist", "whitelist"),
        ("--context", "context"), ("--persona", "persona"),
        ("--waiting-messages", "waiting_messages"),
        ("--goodbye-messages", "goodbye_messages"),
    ):
        edit_group.add_argument(option, dest="edit_resource", action="store_const", const=resource)
    parser.add_argument("message", nargs="*", help="mensagem inicial para o Jarvis")
    parsed = parser.parse_args(arguments)
    message = " ".join(parsed.message).strip()
    if parsed.edit_resource and message:
        parser.error("as opções de edição não aceitam mensagem")
    level = default_reasoning_level if parsed.r == -1 else parsed.r
    return Invocation(message or None, level, parsed.edit_resource)


def _edit_resource(config: object, resource: str) -> None:
    settings = config.settings  # type: ignore[attr-defined]
    paths = {
        "blacklist": settings.blacklist_path,
        "whitelist": settings.whitelist_path,
        "context": settings.context_path,
        "persona": settings.persona_path,
        "waiting_messages": settings.waiting_messages_path,
        "goodbye_messages": settings.goodbye_messages_path,
    }
    editor = shutil.which("nano")
    if editor is None:
        raise SystemExit("O editor nano não está instalado.")
    try:
        completed = subprocess.run([editor, str(paths[resource])], check=False)
    except OSError as error:
        raise SystemExit(f"Não foi possível abrir nano: {error}") from error
    if completed.returncode:
        raise SystemExit(f"nano encerrou com código {completed.returncode}.")


def _confirm_root_startup() -> None:
    if os.geteuid() != 0:
        return
    warning = (
        "AVISO: Jarvis está sendo executado como root. Qualquer ação permitida pode afetar "
        "todo o sistema. As políticas e confirmações continuam ativas.\n"
        "Digite 'ciente' para continuar: "
    )
    if not sys.stdin.isatty() or input(warning).strip().casefold() != "ciente":
        raise SystemExit("Inicialização root cancelada.")


def parse_initial_message(arguments: list[str] | None = None, prog: str = "jarvis") -> str | None:
    return parse_invocation(arguments, prog).message


def main(arguments: list[str] | None = None) -> None:
    invocation_directory = Path.cwd().resolve()
    config = load_config()
    user_settings = config.settings
    advanced = config.advanced
    invocation = parse_invocation(
        arguments, user_settings.command_name, user_settings.default_reasoning_level
    )
    if invocation.edit_resource:
        _edit_resource(config, invocation.edit_resource)
        return
    _confirm_root_startup()
    maintain_runtime_logs(
        Path.home() / ".local/state/jarvis/logs/runtime",
        user_settings.log_max_size_mb,
        user_settings.log_retention_days,
    )
    theme = Theme.load(user_settings.color_mode)
    activity = ActivityPanel(
        user_settings.display_log_level,
        theme=theme,
        interaction_timeout_seconds=user_settings.interaction_timeout_seconds,
    )
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if activity.log_path is not None:
        handlers.append(logging.FileHandler(activity.log_path, encoding="utf-8"))
    logging.basicConfig(
        level=(
            logging.DEBUG
            if user_settings.display_log_level is DisplayLogLevel.FULL
            else logging.CRITICAL
        ),
        handlers=handlers,
        force=True,
    )
    # Mantém diagnóstico HTTP útil sem expor headers sensíveis do transporte.
    logging.getLogger("httpcore").setLevel(logging.INFO)
    audit = AuditLog(advanced.audit_db_path)
    confirmations = ConfirmationManager(advanced.confirmation_timeout)
    policy_engine = PolicyEngine(user_settings.permissions)
    path_policy = PathPolicy.load(
        user_settings.blacklist_path,
        project_directory=project_root(),
        whitelist_path=user_settings.whitelist_path,
    )
    memory_store = ConversationLogStore(
        Path.home() / ".local/state/jarvis/logs",
        max_size_mb=user_settings.log_max_size_mb,
        retention_days=user_settings.log_retention_days,
    )
    memory_store.maintain()
    registry = build_registry(
        policy_engine,
        confirmations,
        audit,
        path_policy,
        memory_store,
        activity,
    )
    user_directories: dict[str, object] = {}
    directory_context_read = path_policy.decide(
        policy_engine.decide(Risk.READ),
        Risk.READ,
        [system.user_directories_config_path()],
    )
    if directory_context_read is Decision.ALLOW:
        directory_result = registry.request("get_user_directories", {})
        if directory_result.status == "ok":
            user_directories = directory_result.result
    recent_memories: list[dict[str, object]] = []
    memory_read = path_policy.decide(
        policy_engine.decide(Risk.READ),
        Risk.READ,
        [memory_store.database_path],
    )
    if memory_read is Decision.ALLOW:
        recent_memories = memory_store.recent_summaries(
            can_read=lambda path: path_policy.decide(
                policy_engine.decide(Risk.READ),
                Risk.READ,
                [path],
            )
            is Decision.ALLOW
        )
    notes_store: ProfileNotesStore | None = None
    notes_store_error: str | None = None
    try:
        notes_store = ProfileNotesStore(config_path().parent / "jarvis-notes")
    except OSError as error:
        notes_store_error = str(error)
    waiting_messages = load_waiting_messages(user_settings.waiting_messages_path)
    goodbye_messages = load_waiting_messages(user_settings.goodbye_messages_path)
    waiting_indicator = WaitingIndicator(waiting_messages)
    def show_llm_notice(notice: LLMNotice) -> None:
        level = "ERRO" if notice.critical else "AVISO"
        role = "error" if notice.critical else "warning"
        print(theme.paint(f"{level}: {notice.message}", role), file=sys.stderr)

    with LlamaClient(
        advanced.llm_base_url,
        advanced.llm_model,
        advanced.llm_api_key,
        timeout=user_settings.llm_request_timeout_seconds,
        thinking_budget_tokens=REASONING_BUDGETS[invocation.reasoning_level],
        notice=show_llm_notice,
    ) as llm:
        notes = ""
        notes_warning: str | None = notes_store_error
        if notes_store is not None:
            try:
                notes, doubled = notes_store.prepare(
                    llm,
                    max_size_mb=user_settings.notes_max_size_mb,
                    context_size=user_settings.context_size,
                    lock_timeout_seconds=user_settings.llm_request_timeout_seconds,
                )
                if doubled:
                    updated_settings = user_settings.model_copy(
                        update={"notes_max_size_mb": user_settings.notes_max_size_mb * 2}
                    )
                    config = config.model_copy(update={"settings": updated_settings})
                    save_config(config)
                    user_settings = updated_settings
                    notes_warning = (
                        "As notas de perfil continuaram acima do limite após a compactação; "
                        f"o limite foi dobrado para {user_settings.notes_max_size_mb} MB."
                    )
            except (OSError, RuntimeError, TimeoutError) as error:
                notes_warning = f"Não foi possível preparar as notas de perfil: {error}"
        system_prompt = build_system_prompt(
            user_settings.assistant_name,
            user_settings.persona_path,
            invocation_directory,
            context_path=user_settings.context_path,
            home_directory=Path.home().resolve(),
            current_time=datetime.now().astimezone(),
            user_directories=user_directories,
            recent_memories=recent_memories,
            jarvis_notes=notes,
            interaction_timeout_seconds=user_settings.interaction_timeout_seconds,
            llm_request_timeout_seconds=user_settings.llm_request_timeout_seconds,
            max_tool_rounds=user_settings.max_tool_rounds,
        )
        orchestrator = Orchestrator(
            llm,
            registry,
            max_tool_rounds=user_settings.max_tool_rounds,
            interaction_timeout_seconds=user_settings.interaction_timeout_seconds,
            llm_request_timeout_seconds=user_settings.llm_request_timeout_seconds,
            system_prompt=system_prompt,
            thinking_budget_tokens=REASONING_BUDGETS[invocation.reasoning_level],
        )
        activity.total_seconds = lambda: orchestrator.active_seconds
        initial_message = invocation.message
        warning = (
            f"Política de paths inválida: {path_policy.error}. Tools de arquivos foram bloqueadas; "
            "corrija o arquivo e abra um novo chat."
            if path_policy.error
            else None
        )
        if notes_warning:
            warning = f"{warning}\n{notes_warning}" if warning else notes_warning
        outcome = TerminalUI(
            orchestrator,
            user_settings.assistant_name,
            warning,
            waiting_indicator=waiting_indicator,
            goodbye_messages=goodbye_messages,
            config=config,
            theme=theme,
            show_license_notice=consume_license_notice(),
        ).run(
            initial_message,
            continue_after_initial=(
                initial_message is None or user_settings.message_mode is MessageMode.INTERACTIVE
            ),
        )
        log_path = memory_store.create(
            orchestrator.transcript,
            started_at=orchestrator.started_at,
            invocation_directory=invocation_directory,
        )
        if log_path is not None and outcome is not SessionExit.RESTART_MODEL:
            memory_store.schedule_summary(log_path)
        if log_path is not None and notes_store is not None:
            memory_store.schedule_profile_notes(log_path, notes_store.path)
        if outcome is SessionExit.RESTART_MODEL:
            raise SystemExit(75)


if __name__ == "__main__":
    main()
