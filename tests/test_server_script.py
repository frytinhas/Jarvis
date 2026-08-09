from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize(
    "level,expected,unexpected",
    [
        ("Essential", "--log-disable", "--log-file"),
        ("Server-Essential", "--log-verbosity\n3", "--log-disable"),
        ("Full", "--verbose", "--log-disable"),
    ],
)
def test_server_logging_flags_follow_display_level(
    tmp_path: Path, level: str, expected: str, unexpected: str
) -> None:
    source_root = Path(__file__).resolve().parent.parent
    project = tmp_path / "project"
    scripts = project / "scripts"
    binary = project / ".venv/bin"
    scripts.mkdir(parents=True)
    binary.mkdir(parents=True)
    shutil.copy2(source_root / "scripts/jarvis-server", scripts / "jarvis-server")
    shutil.copy2(source_root / "scripts/jarvis-env", scripts / "jarvis-env")
    python = binary / "python"
    python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)
    model = tmp_path / "model.gguf"
    model.write_text("model", encoding="utf-8")
    llama = tmp_path / "llama-server"
    llama.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$HOME/server-args"\n',
        encoding="utf-8",
    )
    llama.chmod(0o755)
    (project / ".install").write_text(
        f"INSTALL_UID={os.getuid()}\nINSTALL_HOME={tmp_path}\n"
        f"LLAMA_BIN={llama}\nLLAMA_STYLE=server\nSERVER_HOST=127.0.0.1\nSERVER_PORT=8080\n",
        encoding="utf-8",
    )
    state = tmp_path / ".local/state/jarvis"
    state.mkdir(parents=True)
    (state / "runtime.env").write_text(
        f"MODEL_PATH={model}\nMODEL_ALIAS=jarvis-model\nCONTEXT_SIZE=8192\nDISPLAY_LOG_LEVEL={level}\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(scripts / "jarvis-server")],
        env={**os.environ, "HOME": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    arguments = (tmp_path / "server-args").read_text(encoding="utf-8")
    assert expected in arguments
    assert unexpected not in arguments
    assert "--ctx-size\n8192" in arguments
    if level != "Essential":
        assert "--log-file" in arguments
        assert (tmp_path / ".local/state/jarvis/logs/runtime/llama-server.log").is_file()
