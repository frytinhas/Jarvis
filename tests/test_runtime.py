from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.config import default_config, save_config
from jarvis.runtime import sync_runtime


def _prepare_runtime(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:  # type: ignore[no-untyped-def]
    project = tmp_path / "project"
    project.mkdir()
    config_path = tmp_path / "config.xml"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("JARVIS_CONFIG_PATH", str(config_path))
    monkeypatch.setattr("jarvis.runtime.project_root", lambda: project)
    monkeypatch.setattr("jarvis.configurator.project_root", lambda: project)
    runtime = project / ".runtime"
    runtime.write_text(
        "MODEL_PATH=/tmp/old.gguf\nMODEL_ALIAS=jarvis-model\n"
        "COMMAND_NAME=jarvis\nASSISTANT_NAME=Jarvis\nAUTOSTART=true\n"
        "KEEP_LLM_RUNNING=false\nMESSAGE_MODE=interactive\n",
        encoding="utf-8",
    )
    return config_path, runtime


def test_manual_model_edit_regenerates_runtime_and_marks_restart(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    config_path, runtime = _prepare_runtime(tmp_path, monkeypatch)
    original = default_config()
    settings = original.settings.model_copy(
        update={"model_path": Path("/tmp/new model.gguf")}
    )
    save_config(original.model_copy(update={"settings": settings}), config_path)

    sync_runtime()

    content = runtime.read_text(encoding="utf-8")
    assert "MODEL_PATH='/tmp/new model.gguf'" in content
    assert (tmp_path / ".local/state/jarvis/restart-required").is_file()


def test_manual_command_edit_refuses_existing_unowned_command(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    config_path, _ = _prepare_runtime(tmp_path, monkeypatch)
    local_bin = tmp_path / ".local/bin"
    local_bin.mkdir(parents=True)
    (local_bin / "bob").write_text("third party", encoding="utf-8")
    original = default_config()
    settings = original.settings.model_copy(update={"command_name": "bob"})
    save_config(original.model_copy(update={"settings": settings}), config_path)

    with pytest.raises(ValueError, match="já existe outro comando"):
        sync_runtime()
