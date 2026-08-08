from __future__ import annotations

import argparse
import logging

from jarvis.agent.orchestrator import Orchestrator
from jarvis.agent.prompts import build_system_prompt
from jarvis.config import Config
from jarvis.llm.client import LlamaClient
from jarvis.security.audit import AuditLog
from jarvis.security.confirmation import ConfirmationManager
from jarvis.security.policy import PolicyEngine
from jarvis.settings import load_settings
from jarvis.tools.registry import build_registry
from jarvis.ui.terminal import TerminalUI


def parse_initial_message(arguments: list[str] | None = None, prog: str = "jarvis") -> str | None:
    parser = argparse.ArgumentParser(prog=prog, description="Assistente local")
    parser.add_argument("message", nargs="*", help="mensagem inicial para o Jarvis")
    parsed = parser.parse_args(arguments)
    message = " ".join(parsed.message).strip()
    return message or None


def main(arguments: list[str] | None = None) -> None:
    config = Config.load()
    user_settings = load_settings()
    logging.basicConfig(level=config.log_level)
    audit = AuditLog(config.audit_db_path)
    confirmations = ConfirmationManager(config.confirmation_timeout)
    registry = build_registry(PolicyEngine(user_settings.permissions), confirmations, audit)
    system_prompt = build_system_prompt(user_settings.assistant_name, user_settings.persona_path)
    with LlamaClient(config.llm_base_url, config.llm_model, config.llm_api_key) as llm:
        orchestrator = Orchestrator(llm, registry, system_prompt=system_prompt)
        TerminalUI(orchestrator, user_settings.assistant_name).run(
            parse_initial_message(arguments, user_settings.command_name)
        )


if __name__ == "__main__":
    main()
