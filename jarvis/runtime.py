from __future__ import annotations

from pathlib import Path
import shlex
import sys

from jarvis.config import ConfigFileError, load_config
from jarvis.configurator import (
    _apply_command,
    _apply_desktop_entry,
    _write_runtime,
    normalize_command_name,
)
from jarvis.settings import project_root


def _read_runtime(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in raw_line:
            continue
        key, raw_value = raw_line.split("=", 1)
        try:
            parsed = shlex.split(raw_value)
        except ValueError:
            continue
        if len(parsed) == 1:
            values[key] = parsed[0]
    return values


def sync_runtime() -> None:
    config = load_config()
    settings = config.settings
    normalize_command_name(settings.command_name)
    runtime_path = project_root() / ".runtime"
    previous = _read_runtime(runtime_path)
    previous_command = previous.get("COMMAND_NAME", settings.command_name)
    _apply_command(previous_command, settings.command_name)
    identity_changed = (
        previous.get("COMMAND_NAME") != settings.command_name
        or previous.get("ASSISTANT_NAME") != settings.assistant_name
    )
    if identity_changed:
        _apply_desktop_entry(settings)
    model_changed = bool(previous) and (
        previous.get("MODEL_PATH") != str(settings.model_path)
        or previous.get("MODEL_ALIAS") != config.advanced.llm_model
    )
    _write_runtime(config)
    if model_changed:
        marker = Path.home() / ".local/state/jarvis/restart-required"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()


def main() -> None:
    try:
        sync_runtime()
    except (ConfigFileError, OSError, ValueError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
