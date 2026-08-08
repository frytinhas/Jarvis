from pathlib import Path

from jarvis.security.policy import Decision, Risk
from jarvis.settings import UserSettings, load_settings, save_settings


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
