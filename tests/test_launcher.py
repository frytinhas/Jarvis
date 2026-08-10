from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


def _launcher_fixture(tmp_path: Path, keep_running: bool) -> tuple[Path, dict[str, str]]:
    source_root = Path(__file__).resolve().parent.parent
    project = tmp_path / "install"
    scripts = project / "scripts"
    binary = project / ".venv/bin"
    mock_bin = tmp_path / "mock-bin"
    scripts.mkdir(parents=True)
    binary.mkdir(parents=True)
    mock_bin.mkdir()
    launcher = scripts / "jarvis"
    shutil.copy2(source_root / "scripts/jarvis", launcher)
    shutil.copy2(source_root / "scripts/jarvis-env", scripts / "jarvis-env")
    uninstaller = project / "Uninstall.sh"
    uninstaller.write_text(
        '#!/usr/bin/env bash\nprintf "%s" "$1" > "$HOME/uninstall-mode"\n',
        encoding="utf-8",
    )

    (project / ".install").write_text(
        f"INSTALL_UID={os.getuid()}\nINSTALL_HOME={tmp_path}\n"
        "LLAMA_BIN=/bin/true\nLLAMA_STYLE=server\nSERVER_HOST=127.0.0.1\nSERVER_PORT=8080\n",
        encoding="utf-8",
    )
    config = tmp_path / ".config/jarvis/profiles/jarvis/config.xml"
    config.parent.mkdir(parents=True)
    config.write_text("config\n", encoding="utf-8")
    state = tmp_path / ".local/state/jarvis/profiles/jarvis"
    state.mkdir(parents=True)
    (state / "runtime.env").write_text(
        "MODEL_PATH=/tmp/model.gguf\nMODEL_ALIAS=jarvis-model\nSERVER_PORT=8080\nCOMMAND_NAME=jarvis\n"
        "ASSISTANT_NAME=Jarvis\nAUTOSTART=true\n"
        f"KEEP_LLM_RUNNING={'true' if keep_running else 'false'}\n",
        encoding="utf-8",
    )
    python = binary / "python"
    python.write_text(
        '#!/usr/bin/env bash\n[[ "$*" == *"profile_cli port-in-use"* ]] && exit 1\nexit 0\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    client = binary / "jarvis"
    client.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$PWD" > "$HOME/client-cwd"\n'
        'printf "%s\\n" "$@" > "$HOME/client-args"\n',
        encoding="utf-8",
    )
    client.chmod(0o755)
    curl = mock_bin / "curl"
    curl.write_text('#!/usr/bin/env bash\nprintf \'%s\\n\' \'{"id":"jarvis-model"}\'\n', encoding="utf-8")
    curl.chmod(0o755)
    systemctl = mock_bin / "systemctl"
    systemctl.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$HOME/systemctl-log"\nexit 0\n',
        encoding="utf-8",
    )
    systemctl.chmod(0o755)
    environment = dict(os.environ)
    environment.update({"HOME": str(tmp_path), "PATH": f"{mock_bin}:/usr/bin:/bin"})
    return launcher, environment


@pytest.mark.parametrize("keep_running, should_stop", [(False, True), (True, False)])
def test_launcher_preserves_cwd_and_applies_server_lifecycle(
    tmp_path: Path,
    keep_running: bool,
    should_stop: bool,
) -> None:
    launcher, environment = _launcher_fixture(tmp_path, keep_running)
    invocation_directory = tmp_path / "current-project"
    invocation_directory.mkdir()

    result = subprocess.run(
        [str(launcher), "resuma esta pasta"],
        cwd=invocation_directory,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "client-cwd").read_text(encoding="utf-8").strip() == str(invocation_directory)
    assert (tmp_path / "client-args").read_text(encoding="utf-8").strip() == "resuma esta pasta"
    log_path = tmp_path / "systemctl-log"
    systemctl_log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert ("--user stop jarvis-llm@jarvis.service" in systemctl_log) is should_stop


def test_full_stop_stops_managed_server_without_opening_client(tmp_path: Path) -> None:
    launcher, environment = _launcher_fixture(tmp_path, keep_running=True)

    result = subprocess.run(
        [str(launcher), "--full-stop"],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "início automático foi mantida" in result.stdout
    assert not (tmp_path / "client-cwd").exists()
    assert "--user stop jarvis-llm@jarvis.service" in (tmp_path / "systemctl-log").read_text(encoding="utf-8")


@pytest.mark.parametrize("mode", ["--remove", "--purge"])
def test_launcher_routes_uninstall_modes_before_startup(tmp_path: Path, mode: str) -> None:
    launcher, environment = _launcher_fixture(tmp_path, keep_running=True)

    result = subprocess.run(
        [str(launcher), mode],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "uninstall-mode").read_text(encoding="utf-8") == mode
    assert not (tmp_path / "client-cwd").exists()


def test_launcher_rejects_installation_owned_by_another_uid(tmp_path: Path) -> None:
    launcher, environment = _launcher_fixture(tmp_path, keep_running=True)
    install_file = tmp_path / "install/.install"
    install_file.write_text(
        f"INSTALL_UID={os.getuid() + 1}\nINSTALL_HOME={tmp_path}\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(launcher)], env=environment, text=True, capture_output=True, check=False
    )

    assert result.returncode == 1
    assert "pertence a outro usuário" in result.stderr
    assert not (tmp_path / "client-cwd").exists()


def test_launcher_restarts_model_and_reopens_client_on_internal_exit_code(tmp_path: Path) -> None:
    launcher, environment = _launcher_fixture(tmp_path, keep_running=True)
    client = tmp_path / "install/.venv/bin/jarvis"
    client.write_text(
        '#!/usr/bin/env bash\n'
        'count_file="$HOME/client-count"\n'
        'count=0\n'
        '[[ -f "$count_file" ]] && count="$(<"$count_file")"\n'
        'count=$((count + 1))\n'
        'printf "%s\\n" "$count" >"$count_file"\n'
        '((count == 1)) && exit 75\n'
        'exit 0\n',
        encoding="utf-8",
    )
    client.chmod(0o755)

    result = subprocess.run(
        [str(launcher)], env=environment, text=True, capture_output=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "client-count").read_text(encoding="utf-8").strip() == "2"
    assert "--user restart jarvis-llm@jarvis.service" in (
        tmp_path / "systemctl-log"
    ).read_text(encoding="utf-8")
