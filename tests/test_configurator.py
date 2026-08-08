from pathlib import Path

import pytest

from jarvis.configurator import _apply_command, discover_models, normalize_command_name


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
