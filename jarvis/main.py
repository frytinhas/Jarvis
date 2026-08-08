from __future__ import annotations

import argparse
import logging

from jarvis.agent.orchestrator import Orchestrator
from jarvis.config import Config
from jarvis.llm.client import LlamaClient
from jarvis.security.audit import AuditLog
from jarvis.security.confirmation import ConfirmationManager
from jarvis.security.policy import PolicyEngine
from jarvis.tools.registry import build_registry
from jarvis.ui.terminal import TerminalUI


def parse_initial_message(arguments: list[str] | None = None) -> str | None:
    parser = argparse.ArgumentParser(prog="jarvis", description="Assistente local Jarvis")
    parser.add_argument("message", nargs="*", help="mensagem inicial para o Jarvis")
    parsed = parser.parse_args(arguments)
    message = " ".join(parsed.message).strip()
    return message or None


def main(arguments: list[str] | None = None) -> None:
    config = Config.load()
    logging.basicConfig(level=config.log_level)
    audit = AuditLog(config.audit_db_path)
    confirmations = ConfirmationManager(config.confirmation_timeout)
    registry = build_registry(PolicyEngine(), confirmations, audit)
    with LlamaClient(config.llm_base_url, config.llm_model, config.llm_api_key) as llm:
        TerminalUI(Orchestrator(llm, registry)).run(parse_initial_message(arguments))


if __name__ == "__main__":
    main()
