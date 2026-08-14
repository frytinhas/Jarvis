from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def start_core_process(repository: Path) -> subprocess.Popen[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repository / "src")
    return subprocess.Popen(
        [sys.executable, "-m", "jarvis.core", "--foreground"],
        cwd=repository,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
