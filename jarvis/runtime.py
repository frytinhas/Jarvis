from __future__ import annotations

import argparse
import os
from pathlib import Path
import shlex
import sys

from jarvis.config import CONFIG_VERSION, ConfigFileError, config_path, load_config, save_config
from jarvis.configurator import (
    _apply_command,
    _apply_desktop_entry,
    _write_runtime,
    normalize_command_name,
    template_thinking_enabled,
)
from jarvis.settings import runtime_path
from jarvis.profiles import active_profile, validate_profile_uniqueness


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
    selected_profile = active_profile()
    if selected_profile is not None and settings.command_name != selected_profile:
        raise ValueError("Renomeie o perfil pelo jarvis-config, não editando somente o XML")
    validate_profile_uniqueness(config, source)
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
        or previous.get("CONTEXT_SIZE") != str(settings.context_size)
        or previous.get("TEMPLATE_THINKING") != (
            "true" if template_thinking_enabled(settings) else "false"
        )
    )
    server_logging_changed = bool(previous) and (
        previous.get("DISPLAY_LOG_LEVEL") != settings.display_log_level.value
    )
    _write_runtime(config)
    if model_changed or server_logging_changed:
        marker = target_runtime.parent / "restart-required"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    options = parser.parse_args(arguments)
    try:
        if options.all:
            from jarvis.profiles import profile_locations
            previous_profile = os.environ.get("JARVIS_PROFILE")
            previous_config = os.environ.get("JARVIS_CONFIG_PATH")
            try:
                for location in profile_locations():
                    if location.slug is None:
                        continue
                    os.environ["JARVIS_PROFILE"] = location.slug
                    os.environ["JARVIS_CONFIG_PATH"] = str(location.config_file)
                    sync_runtime()
            finally:
                if previous_profile is None:
                    os.environ.pop("JARVIS_PROFILE", None)
                else:
                    os.environ["JARVIS_PROFILE"] = previous_profile
                if previous_config is None:
                    os.environ.pop("JARVIS_CONFIG_PATH", None)
                else:
                    os.environ["JARVIS_CONFIG_PATH"] = previous_config
        else:
            sync_runtime()
    except (ConfigFileError, OSError, ValueError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
