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
from jarvis.config import load_config
from jarvis.legal import consume_license_notice
from jarvis.llm.client import LlamaClient
from jarvis.memory import ConversationLogStore, summarize_conversation
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
    system_prompt = build_system_prompt(
        user_settings.assistant_name,
        user_settings.persona_path,
        invocation_directory,
        context_path=user_settings.context_path,
        home_directory=Path.home().resolve(),
        current_time=datetime.now().astimezone(),
        user_directories=user_directories,
        recent_memories=recent_memories,
        interaction_timeout_seconds=user_settings.interaction_timeout_seconds,
        llm_request_timeout_seconds=user_settings.llm_request_timeout_seconds,
        max_tool_rounds=user_settings.max_tool_rounds,
    )
    waiting_messages = load_waiting_messages(user_settings.waiting_messages_path)
    waiting_indicator = WaitingIndicator(waiting_messages)
    with LlamaClient(
        advanced.llm_base_url,
        advanced.llm_model,
        advanced.llm_api_key,
        timeout=user_settings.llm_request_timeout_seconds,
        thinking_budget_tokens=REASONING_BUDGETS[invocation.reasoning_level],
    ) as llm:
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
        outcome = TerminalUI(
            orchestrator,
            user_settings.assistant_name,
            warning,
            waiting_indicator=waiting_indicator,
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
            try:
                with waiting_indicator.active():
                    summary = summarize_conversation(llm, orchestrator.transcript)
                memory_store.update_summary(log_path, summary)
            except Exception:
                pass
            memory_store.maintain()
        if outcome is SessionExit.RESTART_MODEL:
            raise SystemExit(75)


if __name__ == "__main__":
    main()
