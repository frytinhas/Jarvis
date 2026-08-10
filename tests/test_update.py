from __future__ import annotations

import os
from pathlib import Path
import subprocess


def test_update_runs_source_setup_in_repair_mode(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    setup = source / "Setup.sh"
    setup.write_text(
        "#!/usr/bin/env bash\nprintf '%s' \"$1\" > \"$UPDATE_RESULT\"\n",
        encoding="utf-8",
    )
    setup.chmod(0o755)
    project = tmp_path / "home/.local/share/jarvis/app"
    (project / "scripts").mkdir(parents=True)
    update = Path(__file__).resolve().parent.parent / "Update.sh"
    environment_script = Path(__file__).resolve().parent.parent / "scripts/jarvis-env"
    target = project / "Update.sh"
    target.write_text(update.read_text(encoding="utf-8"), encoding="utf-8")
    (project / "scripts/jarvis-env").write_text(
        environment_script.read_text(encoding="utf-8"), encoding="utf-8"
    )
    home = tmp_path / "home"
    result_file = tmp_path / "result"
    (project / ".install").write_text(
        f"INSTALL_UID={os.getuid()}\nINSTALL_HOME={home}\nINSTALL_SOURCE_DIR={source}\n",
        encoding="utf-8",
    )
    environment = {**os.environ, "HOME": str(home), "UPDATE_RESULT": str(result_file)}

    result = subprocess.run(
        ["bash", str(target)], env=environment, text=True, capture_output=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result_file.read_text(encoding="utf-8") == "--repair"
