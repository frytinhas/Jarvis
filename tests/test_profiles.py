from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.config import JarvisConfig, load_config, save_config
from jarvis.settings import UserSettings
from jarvis.configurator import _displace_named_profile
from jarvis.profiles import (
    allocate_server_port, build_profile_config, normalize_profile_name,
    config_root, migrate_legacy_profile, profile_config_directory, profile_locations,
    profile_state_directory, state_root,
)
from jarvis.resources import ensure_private_resources


def _environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("JARVIS_CONFIG_PATH", raising=False)
    monkeypatch.delenv("JARVIS_PROFILE", raising=False)


def test_named_profiles_have_isolated_config_state_and_ports(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _environment(tmp_path, monkeypatch)
    first_model = tmp_path / "models/first.gguf"
    second_model = tmp_path / "models/second.gguf"
    first_model.parent.mkdir()
    first_model.write_bytes(b"one")
    second_model.write_bytes(b"two")

    first = build_profile_config(first_model, "Jarvis")
    ensure_private_resources(first.settings)
    save_config(first, profile_config_directory("jarvis") / "config.xml")
    second = build_profile_config(second_model, "Bryan")
    ensure_private_resources(second.settings)
    save_config(second, profile_config_directory("bryan") / "config.xml")

    assert first.settings.server_port != second.settings.server_port
    assert first.settings.persona_path.parent == profile_config_directory("jarvis")
    assert second.advanced.audit_db_path.parent == profile_state_directory("bryan")
    assert {item.slug for item in profile_locations()} == {"jarvis", "bryan"}
    assert allocate_server_port() not in {first.settings.server_port, second.settings.server_port}


@pytest.mark.parametrize("name", ["Joao Augusto", "joao_augusto", "jõao", "1joao"])
def test_new_profile_names_reject_spaces_underscore_accents_and_leading_number(name: str) -> None:
    with pytest.raises(ValueError):
        normalize_profile_name(name)


def test_displaced_profile_preserves_private_data_without_a_command(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _environment(tmp_path, monkeypatch)
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    config = build_profile_config(model, "Jarvis")
    ensure_private_resources(config.settings)
    config.settings.learning_context_path.write_text("user: Gabriel\n", encoding="utf-8")
    save_config(config, profile_config_directory("jarvis") / "config.xml")
    state = profile_state_directory("jarvis")
    state.mkdir(parents=True)
    (state / "audit.db").write_bytes(b"audit")

    location = _displace_named_profile("jarvis")

    assert location.slug is None
    retained = load_config(location.config_file)
    assert retained.settings.learning_context_path.read_text(encoding="utf-8") == "user: Gabriel\n"
    assert retained.advanced.audit_db_path.read_bytes() == b"audit"
    assert not profile_config_directory("jarvis").exists()


def test_single_profile_layout_migrates_without_forcing_learning(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _environment(tmp_path, monkeypatch)
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    legacy = JarvisConfig(settings=UserSettings(
        model_directory=tmp_path, model_path=model,
        persona_path=config_root() / "Persona.md",
        context_path=config_root() / "Context.md",
        waiting_messages_path=config_root() / "WaitingMessages.txt",
        goodbye_messages_path=config_root() / "GoodbyeMessages.txt",
        blacklist_path=config_root() / "Blacklist.txt",
        whitelist_path=config_root() / "Whitelist.txt",
        learning_context_path=config_root() / "LearningContext.md",
    ))
    ensure_private_resources(legacy.settings)
    save_config(legacy, config_root() / "config.xml")
    (state_root() / "logs").mkdir(parents=True)
    (state_root() / "logs/conversations.db").write_bytes(b"memory")

    assert migrate_legacy_profile() == "jarvis"

    migrated = load_config(profile_config_directory("jarvis") / "config.xml")
    assert migrated.settings.learning_state == "complete"
    assert migrated.settings.persona_path.parent == profile_config_directory("jarvis")
    assert (profile_state_directory("jarvis") / "logs/conversations.db").read_bytes() == b"memory"
    assert not (config_root() / "config.xml").exists()
