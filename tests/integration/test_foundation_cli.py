from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path("src").absolute())
    return subprocess.run(
        [sys.executable, "-m", "jarvis.foundation", *arguments],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_initialize_twice_and_inspect_end_to_end() -> None:
    first = _run("initialize", "--json")
    second = _run("initialize", "--json")
    inspected = _run("inspect", "--json")
    assert first.returncode == second.returncode == inspected.returncode == 0
    assert json.loads(first.stdout)["applied_migrations"] == [1, 2, 3, 4, 5]
    assert json.loads(second.stdout)["applied_migrations"] == []
    inspection = json.loads(inspected.stdout)
    assert inspection["database_schema_version"] == 5
    assert inspection["foundation_state_version"] == 1
    assert len(inspection["migrations"]) == 5
    assert "profiles" not in inspection
    assert "models" not in inspection


def test_unsafe_runtime_is_a_safe_typed_error_without_traceback() -> None:
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    runtime.chmod(0o755)
    result = _run("initialize", "--json")
    assert result.returncode == 1
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "xdg.unsafe_runtime_directory"
    assert "traceback" not in result.stderr.casefold()
    assert "/tmp/jarvis-cli-runtime" not in result.stderr
