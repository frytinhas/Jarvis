from __future__ import annotations

from pathlib import Path
import shlex
import sys

from jarvis.config import CONFIG_VERSION, ConfigFileError, config_path, load_config, save_config
from jarvis.configurator import (
    _apply_command,
    _apply_desktop_entry,
    _write_runtime,
    normalize_command_name,
)
from jarvis.settings import runtime_path


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
    source = config_path()
    if source.is_file() and f'version="{CONFIG_VERSION}"' not in source.read_text(encoding="utf-8", errors="ignore")[:200]:
        save_config(config, source)
    settings = config.settings
    normalize_command_name(settings.command_name)
    target_runtime = runtime_path()
    previous = _read_runtime(target_runtime)
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
    server_logging_changed = bool(previous) and (
        previous.get("DISPLAY_LOG_LEVEL") != settings.display_log_level.value
    )
    _write_runtime(config)
    if model_changed or server_logging_changed:
        marker = target_runtime.parent / "restart-required"
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
