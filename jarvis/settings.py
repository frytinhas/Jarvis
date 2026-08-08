from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from jarvis.security.policy import Decision, Risk


DEFAULT_DECISIONS: dict[Risk, Decision] = {
    Risk.READ: Decision.ALLOW,
    Risk.CREATE: Decision.ALLOW,
    Risk.MODIFY: Decision.CONFIRM,
    Risk.DELETE: Decision.CONFIRM,
    Risk.EXECUTE: Decision.CONFIRM,
    Risk.PRIVILEGED: Decision.DENY,
}


class MessageMode(StrEnum):
    INTERACTIVE = "interactive"
    ONE_SHOT = "one_shot"


class UserSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 5
    model_directory: Path | None = None
    model_path: Path | None = None
    permissions: dict[Risk, Decision] = Field(default_factory=lambda: dict(DEFAULT_DECISIONS))
    assistant_name: str = "Jarvis"
    command_name: str = "jarvis"
    autostart: bool = True
    keep_llm_running: bool = False
    message_mode: MessageMode = MessageMode.INTERACTIVE
    request_timeout_seconds: int = Field(default=60, gt=0)
    log_max_size_mb: int = 100
    log_retention_days: int = 30
    persona_path: Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_settings() -> UserSettings:
    return UserSettings(persona_path=project_root() / "Persona.md")
