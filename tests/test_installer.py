from pathlib import Path

from jarvis.config import JarvisConfig, load_config, save_config
from jarvis.installer import repair_user_config
from jarvis.settings import UserSettings, editable_paths


def test_repair_user_config_preserves_settings_and_creates_missing_resources(
    tmp_path: Path,
) -> None:
    target = tmp_path / "config.xml"
    paths = editable_paths(tmp_path / "config")
    config = JarvisConfig(settings=UserSettings(
        assistant_name="Preservado",
        persona_path=paths["persona"],
        context_path=paths["context"],
        waiting_messages_path=paths["waiting_messages"],
        goodbye_messages_path=paths["goodbye_messages"],
        blacklist_path=paths["blacklist"],
        whitelist_path=paths["whitelist"],
    ))
    save_config(config, target)

    repair_user_config(target)

    repaired = load_config(target)
    assert repaired.settings.assistant_name == "Preservado"
    assert repaired.settings.goodbye_messages_path.is_file()
