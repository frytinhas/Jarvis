from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


def test_advanced_flag_opens_config_xml_in_nano(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parent.parent
    project = tmp_path / "project"
    binary = project / ".venv/bin"
    scripts = project / "scripts"
    mock_bin = tmp_path / "mock-bin"
    binary.mkdir(parents=True)
    scripts.mkdir()
    mock_bin.mkdir()
    shutil.copy2(source_root / "Config.sh", project / "Config.sh")
    shutil.copy2(source_root / "scripts/jarvis-env", scripts / "jarvis-env")
    (project / ".install").write_text("installed\n", encoding="utf-8")
    python = binary / "python"
    python.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    python.chmod(0o755)
    config = tmp_path / "config.xml"
    config.write_text("<jarvis />\n", encoding="utf-8")
    nano = mock_bin / "nano"
    nano.write_text('#!/usr/bin/env bash\nprintf "%s" "$1" > "$HOME/nano-target"\n', encoding="utf-8")
    nano.chmod(0o755)
    environment = dict(os.environ)
    environment.update(
        {
            "HOME": str(tmp_path),
            "JARVIS_CONFIG_PATH": str(config),
            "PATH": f"{mock_bin}:/usr/bin:/bin",
        }
    )

    result = subprocess.run(
        [str(project / "Config.sh"), "--a"],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "nano-target").read_text(encoding="utf-8") == str(config)


def test_setup_flag_is_forwarded_to_configurator(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parent.parent
    project = tmp_path / "project"
    binary = project / ".venv/bin"
    scripts = project / "scripts"
    binary.mkdir(parents=True)
    scripts.mkdir()
    shutil.copy2(source_root / "Config.sh", project / "Config.sh")
    shutil.copy2(source_root / "scripts/jarvis-env", scripts / "jarvis-env")
    (project / ".install").write_text("installed\n", encoding="utf-8")
    python = binary / "python"
    python.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$HOME/python-arguments"\n',
        encoding="utf-8",
    )
    python.chmod(0o755)

    result = subprocess.run(
        [str(project / "Config.sh"), "--setup"],
        env={**os.environ, "HOME": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "python-arguments").read_text(encoding="utf-8").splitlines() == [
        "-m",
        "jarvis.configurator",
        "--setup",
    ]
