from __future__ import annotations

import json
import os
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

    version: int = 4
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


def settings_path() -> Path:
    override = os.environ.get("JARVIS_SETTINGS_PATH")
    return Path(override).expanduser() if override else Path.home() / ".config/jarvis/settings.json"


def default_settings() -> UserSettings:
    return UserSettings(persona_path=project_root() / "Persona.md")


def load_settings(path: Path | None = None) -> UserSettings:
    target = path or settings_path()
    if not target.is_file():
        return default_settings()
    settings = UserSettings.model_validate_json(target.read_text(encoding="utf-8"))
    if settings.version < 4:
        settings = settings.model_copy(update={"version": 4})
    return settings


def save_settings(settings: UserSettings, path: Path | None = None) -> None:
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(settings.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(target)
