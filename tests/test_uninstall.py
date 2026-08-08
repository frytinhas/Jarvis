from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


def _installation(tmp_path: Path) -> tuple[Path, dict[str, str], dict[str, Path]]:
    source_root = Path(__file__).resolve().parent.parent
    project = tmp_path / "project"
    home = tmp_path / "home"
    mock_bin = tmp_path / "mock-bin"
    (project / "scripts").mkdir(parents=True)
    (project / ".venv").mkdir()
    home.mkdir()
    mock_bin.mkdir()
    script = project / "Uninstall.sh"
    shutil.copy2(source_root / "Uninstall.sh", script)
    (project / "scripts/jarvis").write_text("launcher\n", encoding="utf-8")
    (project / "Config.sh").write_text("config\n", encoding="utf-8")
    for name in (".install", ".runtime", ".env"):
        (project / name).write_text("local\n", encoding="utf-8")
    (project / "jarvis_local.egg-info").mkdir()
    local_bin = home / ".local/bin"
    local_bin.mkdir(parents=True)
    (local_bin / "jarvis").symlink_to(project / "scripts/jarvis")
    (local_bin / "jarvis-config").symlink_to(project / "Config.sh")
    config = home / ".config/jarvis"
    state = home / ".local/state/jarvis"
    data = home / ".local/share/jarvis"
    config.mkdir(parents=True)
    (state / "logs").mkdir(parents=True)
    (state / "sessions").mkdir()
    data.mkdir(parents=True)
    (config / "config.xml").write_text("config\n", encoding="utf-8")
    (state / "logs/conversations.db").write_text("logs\n", encoding="utf-8")
    (state / "audit.db").write_text("audit\n", encoding="utf-8")
    (state / "runtime.env").write_text("runtime\n", encoding="utf-8")
    (state / "sessions/123").write_text("123\n", encoding="utf-8")
    (data / "llama.cpp").mkdir()
    unit = home / ".config/systemd/user/jarvis-llm.service"
    unit.parent.mkdir(parents=True)
    unit.write_text("unit\n", encoding="utf-8")
    desktop = home / ".local/share/applications/jarvis-local.desktop"
    icon = home / ".local/share/icons/jarvis-local.png"
    desktop.parent.mkdir(parents=True)
    icon.parent.mkdir(parents=True)
    desktop.write_text("desktop\n", encoding="utf-8")
    icon.write_text("icon\n", encoding="utf-8")
    (home / ".bashrc").write_text(
        '# Jarvis Local\nexport PATH="$HOME/.local/bin:$PATH"\n', encoding="utf-8"
    )
    systemctl = mock_bin / "systemctl"
    systemctl.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    systemctl.chmod(0o755)
    environment = dict(os.environ)
    environment.update({"HOME": str(home), "PATH": f"{mock_bin}:/usr/bin:/bin"})
    paths = {
        "project": project,
        "config": config,
        "state": state,
        "data": data,
        "unit": unit,
        "desktop": desktop,
        "icon": icon,
        "local_bin": local_bin,
    }
    return script, environment, paths


def _run(script: Path, environment: dict[str, str], mode: str, confirmation: str):
    return subprocess.run(
        ["bash", str(script), mode],
        input=confirmation + "\n",
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_remove_keeps_configuration_logs_and_audit(tmp_path: Path) -> None:
    script, environment, paths = _installation(tmp_path)

    result = _run(script, environment, "--remove", "jarvis remove")

    assert result.returncode == 0, result.stderr
    assert paths["config"].is_dir()
    assert (paths["state"] / "logs/conversations.db").is_file()
    assert (paths["state"] / "audit.db").is_file()
    assert not (paths["state"] / "sessions").exists()
    assert not (paths["state"] / "runtime.env").exists()
    assert not paths["data"].exists()
    assert not (paths["project"] / ".venv").exists()
    assert not (paths["project"] / ".install").exists()
    assert not (paths["project"] / ".runtime").exists()
    assert not (paths["local_bin"] / "jarvis").exists()
    assert not (paths["local_bin"] / "jarvis-config").exists()
    assert not paths["unit"].exists()
    assert not paths["desktop"].exists()
    assert not paths["icon"].exists()
    bashrc = (Path(environment["HOME"]) / ".bashrc").read_text(encoding="utf-8")
    assert "# Jarvis Local" not in bashrc
    assert ".local/bin" in bashrc


def test_purge_removes_configuration_and_logs(tmp_path: Path) -> None:
    script, environment, paths = _installation(tmp_path)

    result = _run(script, environment, "--purge", "jarvis purge")

    assert result.returncode == 0, result.stderr
    assert not paths["config"].exists()
    assert not paths["state"].exists()
    assert not (paths["project"] / ".env").exists()


def test_running_uninstall_script_without_mode_defaults_to_purge(tmp_path: Path) -> None:
    script, environment, paths = _installation(tmp_path)

    result = subprocess.run(
        ["bash", str(script)],
        input="jarvis purge\n",
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not paths["config"].exists()
    assert not paths["state"].exists()


@pytest.mark.parametrize("mode, confirmation", [("--remove", "jarvis purge"), ("--purge", "yes")])
def test_wrong_confirmation_removes_nothing(
    tmp_path: Path, mode: str, confirmation: str
) -> None:
    script, environment, paths = _installation(tmp_path)

    result = _run(script, environment, mode, confirmation)

    assert result.returncode == 1
    assert (paths["project"] / ".venv").is_dir()
    assert paths["config"].is_dir()
    assert paths["state"].is_dir()
