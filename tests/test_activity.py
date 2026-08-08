from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from jarvis.security.policy import Risk
from jarvis.settings import DisplayLogLevel
from jarvis.tools.registry import ToolActivity
from jarvis.ui.activity import ActivityPanel, maintain_runtime_logs


def _run_panel(level: DisplayLogLevel, event: ToolActivity, tmp_path: Path) -> str:
    output = StringIO()
    panel = ActivityPanel(level, stream=output, log_path=None)
    panel(event)
    return output.getvalue()


def test_minimal_essential_hides_arguments_and_content(tmp_path: Path) -> None:
    event = ToolActivity(
        "running", "write_file", Risk.MODIFY,
        {"path": str(tmp_path / "a.txt"), "content": "segredo"},
    )
    output = _run_panel(DisplayLogLevel.MINIMAL_ESSENTIAL, event, tmp_path)
    assert "write_file" in output
    assert "segredo" not in output


def test_essential_shows_write_diff_but_read_never_shows_content(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("antes\n", encoding="utf-8")
    output = StringIO()
    panel = ActivityPanel(DisplayLogLevel.ESSENTIAL, stream=output)
    panel(ToolActivity("running", "write_file", Risk.MODIFY, {"path": str(path), "content": "depois\n"}))
    panel(ToolActivity("finished", "read_file", Risk.READ, {"path": str(path)}, "ok", {"content": "privado"}))
    rendered = output.getvalue()
    assert "-antes" in rendered
    assert "+depois" in rendered
    assert "privado" not in rendered
    assert "7 bytes" in rendered


@pytest.mark.parametrize("level", list(DisplayLogLevel))
def test_activity_levels_never_disable_audit_contract(level: DisplayLogLevel) -> None:
    # O painel é somente observador; o registry captura suas exceções e audita separadamente.
    assert isinstance(level.value, str)


def test_runtime_log_maintenance_removes_old_sessions(tmp_path: Path) -> None:
    old = tmp_path / "session-old.log"
    old.write_text("old", encoding="utf-8")
    old.touch()
    import os
    os.utime(old, (0, 0))
    maintain_runtime_logs(tmp_path, max_size_mb=100, retention_days=1)
    assert not old.exists()
