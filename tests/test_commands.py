from __future__ import annotations

from pathlib import Path

from jarvis.config import JarvisConfig, load_config, save_config
from jarvis.security.policy import Decision, Risk
from jarvis.settings import UserSettings
from jarvis.ui.commands import LocalCommands


class FakeOrchestrator:
    def __init__(self) -> None:
        self.budget: int | None = None
        self.permissions: dict[Risk, Decision] = {}

    def set_thinking_budget_tokens(self, value: int) -> None:
        self.budget = value

    def set_permission_decision(self, risk: Risk, decision: Decision) -> None:
        self.permissions[risk] = decision


def _commands(tmp_path: Path, monkeypatch) -> tuple[LocalCommands, FakeOrchestrator, Path]:  # type: ignore[no-untyped-def]
    config_file = tmp_path / "config.xml"
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("JARVIS_CONFIG_PATH", str(config_file))
    model = tmp_path / "models/current.gguf"
    model.parent.mkdir()
    model.write_bytes(b"gguf")
    config = JarvisConfig(settings=UserSettings(
        model_directory=model.parent,
        model_path=model,
        persona_path=tmp_path / "Persona.md",
    ))
    save_config(config, config_file)
    orchestrator = FakeOrchestrator()
    return LocalCommands(orchestrator, config), orchestrator, config_file  # type: ignore[arg-type]


def test_reasoning_command_applies_persists_and_completes(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    commands, orchestrator, config_file = _commands(tmp_path, monkeypatch)

    result = commands.handle("/reasoning high")

    assert result.handled
    assert orchestrator.budget == 2048
    assert load_config(config_file).settings.default_reasoning_level == 3
    assert (tmp_path / ".local/state/jarvis/license-notice.pending").is_file()
    assert "/reasoning medium" in commands.completion_candidates("/reasoning m")


def test_model_command_persists_and_requests_restart(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    commands, _, config_file = _commands(tmp_path, monkeypatch)
    selected = tmp_path / "models/other model.gguf"
    selected.write_bytes(b"gguf")

    result = commands.handle('/model "other model.gguf"')

    assert result.ask_model_restart
    assert load_config(config_file).settings.model_path == selected.resolve()
    assert (tmp_path / ".local/state/jarvis/restart-required").is_file()
    assert "/model other model.gguf" in commands.completion_candidates("/model oth")


def test_unknown_slash_command_is_local(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    commands, _, _ = _commands(tmp_path, monkeypatch)
    result = commands.handle("/reas")
    assert result.handled
    assert "/reasoning" in result.text


def test_permissions_summary_shows_global_policy_and_restriction_notice(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    commands, _, _ = _commands(tmp_path, monkeypatch)

    result = commands.handle("/permissions")

    assert "`READ`: **ALLOW**" in result.text
    assert "`MODIFY`: **CONFIRM**" in result.text
    assert "`PRIVILEGED`: **DENY** (fixo)" in result.text
    assert "Blacklist.txt" in result.text


def test_permissions_change_applies_persists_and_completes(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    commands, orchestrator, config_file = _commands(tmp_path, monkeypatch)

    result = commands.handle("/permissions exec confirmation")

    assert "aplicada nesta sessão" in result.text
    assert orchestrator.permissions[Risk.EXECUTE] is Decision.CONFIRM
    assert load_config(config_file).settings.permissions[Risk.EXECUTE] is Decision.CONFIRM
    assert "/permissions read allow" in commands.completion_candidates("/permissions read a")


def test_permissions_aliases_and_invalid_values_do_not_change_configuration(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    commands, orchestrator, config_file = _commands(tmp_path, monkeypatch)

    commands.handle("/permissions write allow")
    before_invalid = load_config(config_file).settings.permissions
    invalid = commands.handle("/permissions privileged allow")

    assert orchestrator.permissions[Risk.MODIFY] is Decision.ALLOW
    assert before_invalid[Risk.MODIFY] is Decision.ALLOW
    assert "Categoria inválida" in invalid.text
    assert load_config(config_file).settings.permissions == before_invalid
