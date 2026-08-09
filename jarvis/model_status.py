"""Private, non-authoritative diagnostics for local model integrations."""
from __future__ import annotations

import json
from pathlib import Path

from jarvis.settings import state_directory


def _path() -> Path:
    return state_directory() / "model-tool-status.json"


def _load() -> dict[str, object]:
    try:
        value = json.loads(_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save(value: dict[str, object]) -> None:
    target = _path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(target)


def record_tool_grammar_failure(model: Path | None) -> None:
    if model is None:
        return
    value = _load()
    failed = value.get("failed_models")
    models = set(failed) if isinstance(failed, list) else set()
    models.add(str(model.expanduser().resolve(strict=False)))
    value["failed_models"] = sorted(models)
    _save(value)


def startup_tool_warning(model: Path | None) -> str | None:
    if model is None:
        return None
    key = str(model.expanduser().resolve(strict=False))
    value = _load()
    failed = value.get("failed_models")
    if not isinstance(failed, list) or key not in failed:
        return None
    if value.get("last_warned_model") == key:
        return None
    value["last_warned_model"] = key
    _save(value)
    return "Este modelo já apresentou falha de tool calling. As tools começam ativadas nesta sessão."
