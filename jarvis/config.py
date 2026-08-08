from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"").strip("'")
    return values


@dataclass(frozen=True)
class Config:
    llm_base_url: str = "http://127.0.0.1:8080/v1"
    llm_model: str = "local-model"
    llm_api_key: str = ""
    confirmation_timeout: int = 30
    audit_db_path: Path = Path("~/.local/state/jarvis/audit.db")
    log_level: str = "INFO"

    @classmethod
    def load(cls, env_file: Path = Path(".env")) -> "Config":
        file_values = _read_env_file(env_file)

        def value(name: str, default: str) -> str:
            return os.environ.get(name, file_values.get(name, default))

        timeout = int(value("CONFIRMATION_TIMEOUT", "30"))
        if timeout <= 0:
            raise ValueError("CONFIRMATION_TIMEOUT deve ser positivo")
        return cls(
            llm_base_url=value("LLM_BASE_URL", cls.llm_base_url).rstrip("/"),
            llm_model=value("LLM_MODEL", cls.llm_model),
            llm_api_key=value("LLM_API_KEY", ""),
            confirmation_timeout=timeout,
            audit_db_path=Path(value("AUDIT_DB_PATH", str(cls.audit_db_path))).expanduser(),
            log_level=value("LOG_LEVEL", "INFO"),
        )

