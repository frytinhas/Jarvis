from pathlib import Path

from jarvis.model_status import record_tool_grammar_failure, startup_tool_warning


def test_failed_model_warning_is_shown_when_entering_that_model(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    failed = tmp_path / "failed.gguf"
    healthy = tmp_path / "healthy.gguf"

    assert startup_tool_warning(failed) is None
    record_tool_grammar_failure(failed)
    assert startup_tool_warning(failed) is None
    assert startup_tool_warning(healthy) is None
    assert startup_tool_warning(failed) is not None
    assert startup_tool_warning(failed) is None
