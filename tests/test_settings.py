from pathlib import Path

from jarvis.security.policy import Decision, Risk
from jarvis.settings import MessageMode, UserSettings, default_settings, load_settings, save_settings


def test_settings_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = UserSettings(
        model_directory=tmp_path,
        model_path=tmp_path / "model.gguf",
        permissions={Risk.READ: Decision.DENY, Risk.PRIVILEGED: Decision.DENY},
        assistant_name="Bob",
        command_name="bob",
        autostart=False,
        persona_path=tmp_path / "Persona.md",
    )
    save_settings(settings, path)
    assert load_settings(path) == settings
    assert path.stat().st_mode & 0o777 == 0o600


def test_new_lifecycle_defaults() -> None:
    settings = default_settings()
    assert settings.keep_llm_running is False
    assert settings.message_mode is MessageMode.INTERACTIVE


def test_version_one_settings_are_migrated(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        '{"version":1,"assistant_name":"Jarvis","command_name":"jarvis",'
        '"autostart":true,"persona_path":"/tmp/Persona.md"}',
        encoding="utf-8",
    )

    settings = load_settings(path)

    assert settings.version == 3
    assert settings.keep_llm_running is False
    assert settings.message_mode is MessageMode.INTERACTIVE
    assert settings.log_max_size_mb == 100
    assert settings.log_retention_days == 30
