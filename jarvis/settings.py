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


class DisplayLogLevel(StrEnum):
    FULL = "Full"
    SERVER_ESSENTIAL = "Server-Essential"
    ESSENTIAL = "Essential"
    MINIMAL_ESSENTIAL = "Minimal-Essential"
    NONE = "None"


class ColorMode(StrEnum):
    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


class UserSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 7
    model_directory: Path | None = None
    model_path: Path | None = None
    permissions: dict[Risk, Decision] = Field(default_factory=lambda: dict(DEFAULT_DECISIONS))
    assistant_name: str = "Jarvis"
    command_name: str = "jarvis"
    autostart: bool = True
    keep_llm_running: bool = False
    message_mode: MessageMode = MessageMode.INTERACTIVE
    max_tool_rounds: int = Field(default=128, gt=0)
    interaction_timeout_seconds: int = Field(default=600, gt=0)
    llm_request_timeout_seconds: int = Field(default=120, gt=0)
    default_reasoning_level: int = Field(default=2, ge=0, le=4)
    display_log_level: DisplayLogLevel = DisplayLogLevel.ESSENTIAL
    color_mode: ColorMode = ColorMode.AUTO
    log_max_size_mb: int = 100
    log_retention_days: int = 30
    persona_path: Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def state_directory() -> Path:
    return Path.home() / ".local/state/jarvis"


def runtime_path() -> Path:
    return state_directory() / "runtime.env"


def default_settings() -> UserSettings:
    return UserSettings(persona_path=project_root() / "Persona.md")
