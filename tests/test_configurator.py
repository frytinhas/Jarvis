from pathlib import Path

import pytest

from jarvis.configurator import (
    _apply_command,
    _apply_desktop_entry,
    ask_integer,
    discover_models,
    normalize_command_name,
)
from jarvis.settings import UserSettings


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
