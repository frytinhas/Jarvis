from __future__ import annotations

import argparse
from datetime import datetime
import logging
from pathlib import Path

from jarvis.agent.orchestrator import Orchestrator
from jarvis.agent.prompts import build_system_prompt
from jarvis.config import Config
from jarvis.llm.client import LlamaClient
from jarvis.memory import ConversationLogStore, summarize_conversation
from jarvis.security.audit import AuditLog
from jarvis.security.confirmation import ConfirmationManager
from jarvis.security.path_policy import PathPolicy
from jarvis.security.policy import Decision, PolicyEngine, Risk
from jarvis.settings import MessageMode, load_settings, project_root
from jarvis.tools.registry import build_registry
from jarvis.tools import system
from jarvis.ui.terminal import TerminalUI
from jarvis.ui.waiting import WaitingIndicator, load_waiting_messages


def parse_initial_message(arguments: list[str] | None = None, prog: str = "jarvis") -> str | None:
    parser = argparse.ArgumentParser(prog=prog, description="Assistente local")
    parser.add_argument("message", nargs="*", help="mensagem inicial para o Jarvis")
    parsed = parser.parse_args(arguments)
    message = " ".join(parsed.message).strip()
    return message or None


def main(arguments: list[str] | None = None) -> None:
    invocation_directory = Path.cwd().resolve()
    config = Config.load(project_root() / ".env")
    user_settings = load_settings()
    logging.basicConfig(level=config.log_level)
    audit = AuditLog(config.audit_db_path)
    confirmations = ConfirmationManager(config.confirmation_timeout)
    policy_engine = PolicyEngine(user_settings.permissions)
    path_policy = PathPolicy.load(
        project_root() / "Blacklist.txt",
        project_directory=project_root(),
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
        context_path=project_root() / "Context.md",
        home_directory=Path.home().resolve(),
        current_time=datetime.now().astimezone(),
        user_directories=user_directories,
        recent_memories=recent_memories,
    )
    waiting_messages = load_waiting_messages(project_root() / "WaitingMessages.txt")
    waiting_indicator = WaitingIndicator(waiting_messages)
    with LlamaClient(
        config.llm_base_url,
        config.llm_model,
        config.llm_api_key,
        timeout=user_settings.request_timeout_seconds,
    ) as llm:
        orchestrator = Orchestrator(
            llm,
            registry,
            request_timeout_seconds=user_settings.request_timeout_seconds,
            system_prompt=system_prompt,
        )
        initial_message = parse_initial_message(arguments, user_settings.command_name)
        warning = (
            f"Blacklist.txt inválido: {path_policy.error}. Tools de arquivos foram bloqueadas; "
            "corrija o arquivo e abra um novo chat."
            if path_policy.error
            else None
        )
        TerminalUI(
            orchestrator,
            user_settings.assistant_name,
            warning,
            waiting_indicator=waiting_indicator,
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
        if log_path is not None:
            try:
                with waiting_indicator.active():
                    summary = summarize_conversation(llm, orchestrator.transcript)
                memory_store.update_summary(log_path, summary)
            except Exception:
                pass
            memory_store.maintain()


if __name__ == "__main__":
    main()
