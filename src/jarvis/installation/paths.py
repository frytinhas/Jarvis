"""Side-effect-free M006C installation path resolution."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class InstallationPaths:
    home: Path
    installation_root: Path
    venv: Path
    private_python: Path
    dispatchers: Path
    systemd_user: Path
    manifest_directory: Path
    manifest: Path
    transaction: Path


def resolve_installation_paths(env: Mapping[str, str] | None = None) -> InstallationPaths:
    active = os.environ if env is None else env
    home_text = active.get("HOME", "")
    if not home_text or not Path(home_text).is_absolute():
        raise ValueError("HOME must be an absolute path")
    home = Path(home_text)
    data_home = _base(active, "XDG_DATA_HOME", home / ".local" / "share")
    config_home = _base(active, "XDG_CONFIG_HOME", home / ".config")
    state_home = _base(active, "XDG_STATE_HOME", home / ".local" / "state")
    root = data_home / "jarvis-cli" / "installation"
    venv = root / "venv"
    manifest_directory = state_home / "jarvis-cli" / "installation"
    return InstallationPaths(
        home=home,
        installation_root=root,
        venv=venv,
        private_python=venv / "bin" / "python",
        dispatchers=home / ".local" / "bin",
        systemd_user=config_home / "systemd" / "user",
        manifest_directory=manifest_directory,
        manifest=manifest_directory / "manifest-v1.json",
        transaction=manifest_directory / ".bootstrap-v1.json",
    )


def _base(env: Mapping[str, str], name: str, fallback: Path) -> Path:
    text = env.get(name, "")
    value = Path(text) if text else fallback
    if not value.is_absolute():
        raise ValueError(f"{name} must be an absolute path")
    return value
