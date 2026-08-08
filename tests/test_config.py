from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.config import ConfigFileError, JarvisConfig, default_config, load_config, save_config
from jarvis.security.policy import Decision, Risk
from jarvis.settings import MessageMode


def test_xml_config_round_trip_with_comments_and_private_mode(tmp_path: Path) -> None:
    path = tmp_path / "config.xml"
    original = default_config()
    settings = original.settings.model_copy(
        update={
            "model_directory": tmp_path,
            "model_path": tmp_path / "model.gguf",
            "assistant_name": "João & Jarvis",
            "command_name": "jarvis",
            "autostart": False,
            "request_timeout_seconds": 45,
        }
    )
    config = original.model_copy(update={"settings": settings})

    save_config(config, path)

    assert load_config(path) == config
    content = path.read_text(encoding="utf-8")
    assert "PT-BR:" in content
    assert "EN:" in content
    assert "João &amp; Jarvis" in content
    assert path.stat().st_mode & 0o777 == 0o600


def test_save_preserves_custom_xml_comments(tmp_path: Path) -> None:
    path = tmp_path / "config.xml"
    save_config(default_config(), path)
    content = path.read_text(encoding="utf-8").replace(
        "<identity>", "<!-- Meu comentário personalizado -->\n  <identity>"
    )
    path.write_text(content, encoding="utf-8")
    config = load_config(path)

    save_config(config, path)

    assert "Meu comentário personalizado" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "replacement, message",
    [
        ("<identity>", "<unknown />\n  <identity>"),
        ("<READ>ALLOW</READ>", "<READ>ALLOW</READ><READ>DENY</READ>"),
        ("<PRIVILEGED>DENY</PRIVILEGED>", "<PRIVILEGED>ALLOW</PRIVILEGED>"),
    ],
)
def test_xml_rejects_unknown_duplicate_and_privileged_values(
    tmp_path: Path, replacement: str, message: str
) -> None:
    path = tmp_path / "config.xml"
    save_config(default_config(), path)
    content = path.read_text(encoding="utf-8").replace(replacement, message)
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigFileError):
        load_config(path)


def test_missing_xml_requires_configurator(tmp_path: Path) -> None:
    with pytest.raises(ConfigFileError, match="execute jarvis-config"):
        load_config(tmp_path / "missing.xml")


def test_malformed_xml_reports_its_location(tmp_path: Path) -> None:
    path = tmp_path / "config.xml"
    path.write_text("<jarvis><broken></jarvis>", encoding="utf-8")

    with pytest.raises(ConfigFileError, match=r"linha 1, coluna"):
        load_config(path)


def test_legacy_files_are_only_loaded_when_explicitly_allowed(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    config_path = tmp_path / "config.xml"
    legacy_settings = tmp_path / "settings.json"
    legacy_settings.write_text(
        '{"version":4,"assistant_name":"Bob","command_name":"bob",'
        '"autostart":true,"persona_path":"/tmp/Persona.md"}',
        encoding="utf-8",
    )
    project = tmp_path / "project"
    project.mkdir()
    (project / ".env").write_text("LLM_BASE_URL=http://legacy.test/v1\n", encoding="utf-8")
    monkeypatch.setattr("jarvis.config.project_root", lambda: project)

    with pytest.raises(ConfigFileError):
        load_config(config_path)
    migrated = load_config(config_path, allow_legacy=True)

    assert migrated.settings.assistant_name == "Bob"
    assert migrated.settings.version == 5
    assert migrated.advanced.llm_base_url == "http://legacy.test/v1"
    assert not config_path.exists()


def test_environment_values_do_not_override_xml(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "config.xml"
    save_config(default_config(), path)
    monkeypatch.setenv("LLM_BASE_URL", "http://ignored.test/v1")

    assert load_config(path).advanced.llm_base_url == "http://127.0.0.1:8080/v1"


def test_new_lifecycle_defaults() -> None:
    settings = default_config().settings
    assert settings.keep_llm_running is False
    assert settings.message_mode is MessageMode.INTERACTIVE
    assert settings.request_timeout_seconds == 60
    assert settings.permissions[Risk.PRIVILEGED] is Decision.DENY
