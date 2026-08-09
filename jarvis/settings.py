from __future__ import annotations

from enum import StrEnum
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from jarvis.security.policy import Decision, Risk


DEFAULT_DECISIONS: dict[Risk, Decision] = {
    Risk.READ: Decision.ALLOW,
    Risk.CREATE: Decision.ALLOW,
    Risk.MODIFY: Decision.CONFIRM,
    Risk.DELETE: Decision.CONFIRM,
    Risk.EXECUTE: Decision.ALLOW,
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

    version: int = 11
    model_directory: Path | None = None
    model_path: Path | None = None
    context_size: int = Field(default=4096, gt=0, multiple_of=1024)
    permissions: dict[Risk, Decision] = Field(default_factory=lambda: dict(DEFAULT_DECISIONS))
    assistant_name: str = "Jarvis"
    command_name: str = "jarvis"
    autostart: bool = True
    keep_llm_running: bool = True
    message_mode: MessageMode = MessageMode.INTERACTIVE
    max_tool_rounds: int = Field(default=128, gt=0)
    interaction_timeout_seconds: int = Field(default=600, gt=0)
    llm_request_timeout_seconds: int = Field(default=120, gt=0)
    default_reasoning_level: int = Field(default=2, ge=0, le=4)
    display_log_level: DisplayLogLevel = DisplayLogLevel.MINIMAL_ESSENTIAL
    color_mode: ColorMode = ColorMode.ALWAYS
    log_max_size_mb: int = 100
    log_retention_days: int = 30
    notes_max_size_mb: int = Field(default=1, gt=0)
    # These files are user-owned configuration, never repository resources at runtime.
    persona_path: Path = Field(default_factory=lambda: editable_paths()["persona"])
    context_path: Path = Field(default_factory=lambda: editable_paths()["context"])
    waiting_messages_path: Path = Field(default_factory=lambda: editable_paths()["waiting_messages"])
    goodbye_messages_path: Path = Field(default_factory=lambda: editable_paths()["goodbye_messages"])
    blacklist_path: Path = Field(default_factory=lambda: editable_paths()["blacklist"])
    whitelist_path: Path = Field(default_factory=lambda: editable_paths()["whitelist"])


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def state_directory() -> Path:
    return Path.home() / ".local/state/jarvis"


def configuration_directory() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser() / "jarvis"


def editable_paths(directory: Path | None = None) -> dict[str, Path]:
    root = (directory or configuration_directory()).expanduser()
    return {
        "persona": root / "Persona.md",
        "context": root / "Context.md",
        "waiting_messages": root / "WaitingMessages.txt",
        "goodbye_messages": root / "GoodbyeMessages.txt",
        "blacklist": root / "Blacklist.txt",
        "whitelist": root / "Whitelist.txt",
        "notes": root / "jarvis-notes",
    }


def runtime_path() -> Path:
    return state_directory() / "runtime.env"


def default_settings() -> UserSettings:
    return UserSettings()
