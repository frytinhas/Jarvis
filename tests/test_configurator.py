from pathlib import Path

import pytest

from jarvis.config import AdvancedConfig, JarvisConfig, load_config, save_config
from jarvis.configurator import (
    MENU_OPTIONS,
    CommandReplacement,
    ConfigurationResult,
    _changes_summary,
    _full_summary,
    _apply_command,
    _apply_desktop_entry,
    _choose_identity,
    _inspect_command,
    ask_integer,
    ask_choice,
    ask_positive_integer,
    commit,
    discover_models,
    main as configurator_main,
    normalize_command_name,
    run_wizard,
)
from jarvis.settings import UserSettings, editable_paths


def test_discovers_gguf_recursively_and_ignores_mmproj(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    model = nested / "model.Q4_K_M.GGUF"
    model.write_bytes(b"model")
    (nested / "mmproj-model.gguf").write_bytes(b"projector")
    (nested / "notes.txt").write_text("not a model", encoding="utf-8")

    assert discover_models(tmp_path) == [model.resolve()]


def test_model_location_must_be_directory(tmp_path: Path) -> None:
    file = tmp_path / "model.gguf"
    file.write_bytes(b"model")
    with pytest.raises(ValueError, match="pasta"):
        discover_models(file)


@pytest.mark.parametrize("name, expected", [("Bob", "bob"), ("my-assistant", "my-assistant")])
def test_normalizes_valid_command_names(name: str, expected: str) -> None:
    assert normalize_command_name(name) == expected


@pytest.mark.parametrize("name", ["123bob", "Bob Smith", "bób", "jarvis-config"])
def test_rejects_unsafe_or_reserved_command_names(name: str) -> None:
    with pytest.raises(ValueError):
        normalize_command_name(name)


def test_custom_command_replaces_owned_default_alias(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    local_bin = tmp_path / ".local/bin"
    local_bin.mkdir(parents=True)
    launcher = (Path(__file__).resolve().parent.parent / "scripts/jarvis").resolve()
    (local_bin / "jarvis").symlink_to(launcher)

    _apply_command("jarvis", "bob")

    assert not (local_bin / "jarvis").exists()
    assert (local_bin / "bob").resolve() == launcher


def test_root_configurator_manages_its_local_launcher(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("jarvis.configurator.os.geteuid", lambda: 0)
    command = tmp_path / ".local/bin/jarvis"
    command.parent.mkdir(parents=True)
    command.symlink_to(tmp_path / "old/scripts/jarvis")

    replacement = _inspect_command("jarvis")
    assert replacement is not None
    _apply_command("jarvis", "jarvis", replacement)
    assert command.resolve() == (Path(__file__).resolve().parent.parent / "scripts/jarvis").resolve()


def test_migrates_confirmed_broken_legacy_launcher(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    local_bin = tmp_path / ".local/bin"
    local_bin.mkdir(parents=True)
    old_launcher = tmp_path / "old-project/scripts/jarvis"
    command = local_bin / "jarvis"
    command.symlink_to(old_launcher)
    replacement = _inspect_command("jarvis")

    assert replacement == CommandReplacement(command, str(old_launcher))

    _apply_command("jarvis", "jarvis", replacement)

    launcher = (Path(__file__).resolve().parent.parent / "scripts/jarvis").resolve()
    assert command.resolve() == launcher


def test_default_identity_offers_confirmed_legacy_migration(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    local_bin = tmp_path / ".local/bin"
    local_bin.mkdir(parents=True)
    old_launcher = tmp_path / "old-project/scripts/jarvis"
    (local_bin / "jarvis").symlink_to(old_launcher)
    answers = iter(["n", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    name, command, replacement = _choose_identity(
        UserSettings(persona_path=tmp_path / "Persona.md")
    )

    assert (name, command) == ("Jarvis", "jarvis")
    assert replacement == CommandReplacement(local_bin / "jarvis", str(old_launcher))


def test_unapproved_legacy_migration_does_not_change_link(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    local_bin = tmp_path / ".local/bin"
    local_bin.mkdir(parents=True)
    old_launcher = tmp_path / "old-project/scripts/jarvis"
    command = local_bin / "jarvis"
    command.symlink_to(old_launcher)

    with pytest.raises(ValueError, match="precisa de confirmação"):
        _apply_command("jarvis", "jarvis")

    assert command.readlink() == old_launcher


def test_rejects_changed_legacy_launcher_after_confirmation(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    local_bin = tmp_path / ".local/bin"
    local_bin.mkdir(parents=True)
    command = local_bin / "jarvis"
    command.symlink_to(tmp_path / "old-project/scripts/jarvis")
    replacement = _inspect_command("jarvis")
    command.unlink()
    command.symlink_to(tmp_path / "different-project/scripts/jarvis")

    with pytest.raises(ValueError, match="mudou"):
        _apply_command("jarvis", "jarvis", replacement)

    assert command.readlink() == tmp_path / "different-project/scripts/jarvis"


@pytest.mark.parametrize("kind", ["file", "live-link", "unknown-broken-link"])
def test_rejects_commands_not_owned_by_jarvis(
    tmp_path: Path, monkeypatch, kind: str
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    local_bin = tmp_path / ".local/bin"
    local_bin.mkdir(parents=True)
    command = local_bin / "jarvis"
    if kind == "file":
        command.write_text("third party", encoding="utf-8")
    elif kind == "live-link":
        program = tmp_path / "third-party"
        program.write_text("third party", encoding="utf-8")
        command.symlink_to(program)
    else:
        command.symlink_to(tmp_path / "missing-program")

    with pytest.raises(ValueError, match="outro comando"):
        _inspect_command("jarvis")


def test_commit_checks_command_before_writing_configuration(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("JARVIS_CONFIG_PATH", str(tmp_path / "config.xml"))
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr("jarvis.configurator.project_root", lambda: project)
    local_bin = tmp_path / ".local/bin"
    local_bin.mkdir(parents=True)
    (local_bin / "jarvis").write_text("third party", encoding="utf-8")
    settings = UserSettings(persona_path=project / "Persona.md")
    result = ConfigurationResult(JarvisConfig(settings=settings), "jarvis", False, False)

    with pytest.raises(ValueError, match="outro comando"):
        commit(result)

    assert not (tmp_path / "config.xml").exists()
    assert not (tmp_path / ".local/state/jarvis/runtime.env").exists()


def test_commit_preserves_advanced_xml_values(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    config_path = tmp_path / "config.xml"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("JARVIS_CONFIG_PATH", str(config_path))
    monkeypatch.setattr("jarvis.configurator.project_root", lambda: project)
    monkeypatch.setattr("jarvis.configurator._apply_command", lambda *args: None)
    monkeypatch.setattr("jarvis.configurator._apply_desktop_entry", lambda *args: None)
    original = JarvisConfig(
        settings=UserSettings(persona_path=project / "Persona.md"),
        advanced=AdvancedConfig(llm_base_url="http://advanced.test/v1", llm_api_key="secret"),
    )
    save_config(original, config_path)
    updated_settings = original.settings.model_copy(update={"assistant_name": "Bob"})

    commit(
        ConfigurationResult(
            original.model_copy(update={"settings": updated_settings}),
            "jarvis",
            False,
            False,
        )
    )

    saved = load_config(config_path)
    assert saved.settings.assistant_name == "Bob"
    assert saved.advanced.llm_base_url == "http://advanced.test/v1"
    assert saved.advanced.llm_api_key == "secret"


def test_desktop_entry_uses_custom_identity_and_icon(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    settings = UserSettings(
        assistant_name="Bob",
        command_name="bob",
        persona_path=tmp_path / "Persona.md",
    )

    _apply_desktop_entry(settings)

    desktop = (tmp_path / "data/applications/jarvis-local.desktop").read_text(encoding="utf-8")
    assert "Name=Bob" in desktop
    assert f'Exec="{tmp_path}/.local/bin/bob"' in desktop
    assert f"Icon={tmp_path}/data/icons/jarvis-local.png" in desktop
    assert (tmp_path / "data/icons/jarvis-local.png").read_bytes().startswith(b"\x89PNG")


def test_log_limit_accepts_negative_integer(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    answers = iter(["not-a-number", "-1"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert ask_integer("Limite", 100) == -1


def test_timeout_requires_positive_integer(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    answers = iter(["0", "-1", "60"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert ask_positive_integer("Timeout", 60) == 60


def test_menu_choice_keeps_default_and_rejects_invalid_values(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    answers = iter(["x", "9", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert ask_choice("Seção", ["a", "b", "c"], default=2) == 2


def test_menu_has_appearance_and_separate_timeouts() -> None:
    assert MENU_OPTIONS == (
        "Modelo, contexto e reasoning",
        "Identidade",
        "Comportamento",
        "Timeouts",
        "Permissões",
        "Logs e painel",
        "Aparência",
        "Persona e contexto",
        "Salvar e sair",
        "Sair sem salvar",
    )


def test_yes_no_uses_arrow_selector_when_available(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("jarvis.configurator.supports_arrow_selection", lambda: True)
    monkeypatch.setattr("jarvis.configurator.select_option", lambda *args: 2)

    from jarvis.configurator import ask_yes_no

    assert ask_yes_no("Salvar?", True) is False


def test_change_summary_only_prints_modified_values(capsys) -> None:  # type: ignore[no-untyped-def]
    previous = UserSettings(persona_path=Path("/tmp/Persona.md"))
    current = previous.model_copy(update={
        "default_reasoning_level": 3,
        "interaction_timeout_seconds": 900,
    })

    assert _changes_summary(previous, current, False, False, None)

    output = capsys.readouterr().out
    assert "Reasoning padrão: Off (nível 0) → High (nível 3)" in output
    assert "Timeout total: 600 segundos → 900 segundos" in output
    assert "Nome:" not in output
    assert "Permissão READ" not in output


def test_change_summary_reports_when_nothing_changed(capsys) -> None:  # type: ignore[no-untyped-def]
    settings = UserSettings(persona_path=Path("/tmp/Persona.md"))

    assert not _changes_summary(settings, settings, False, False, None)
    assert "Nenhuma configuração foi modificada" in capsys.readouterr().out


def test_full_summary_includes_unchanged_configuration(capsys) -> None:  # type: ignore[no-untyped-def]
    settings = UserSettings(persona_path=Path("/tmp/Persona.md"))

    _full_summary(settings, False, False)

    output = capsys.readouterr().out
    assert "Nome: Jarvis" in output
    assert "Reasoning padrão: Off (nível 0)" in output
    assert "Permissões:" in output


def test_model_category_updates_reasoning(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    project = tmp_path / "project"
    project.mkdir()
    (project / "Persona.md").write_text("persona", encoding="utf-8")
    (project / "Context.md").write_text("context", encoding="utf-8")
    paths = editable_paths(tmp_path / "config")
    settings = UserSettings(
        model_directory=tmp_path,
        model_path=model,
        persona_path=paths["persona"],
        context_path=paths["context"],
        waiting_messages_path=paths["waiting_messages"],
        goodbye_messages_path=paths["goodbye_messages"],
        blacklist_path=paths["blacklist"],
        whitelist_path=paths["whitelist"],
    )
    config = JarvisConfig(settings=settings)
    choices = iter([1, 4, 9])
    monkeypatch.setattr("jarvis.configurator.project_root", lambda: project)
    monkeypatch.setattr("jarvis.configurator.load_config", lambda **kwargs: config)
    monkeypatch.setattr("jarvis.configurator._choose_model", lambda current: (tmp_path, model))
    monkeypatch.setattr("jarvis.configurator.ask_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr("jarvis.configurator.ask_yes_no", lambda *args, **kwargs: True)
    monkeypatch.setattr("jarvis.configurator.ask_positive_integer", lambda *args, **kwargs: 4096)

    result = run_wizard()

    assert result is not None
    assert result.settings.default_reasoning_level == 3
    assert result.settings.context_size == 4096
    assert result.settings.interaction_timeout_seconds == settings.interaction_timeout_seconds


def test_setup_mode_requests_full_summary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    calls: list[bool] = []
    monkeypatch.setattr(
        "jarvis.configurator.run_wizard",
        lambda *, full_summary=False: calls.append(full_summary),
    )

    configurator_main(["--setup"])

    assert calls == [True]
