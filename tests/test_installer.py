from pathlib import Path

from jarvis.config import AdvancedConfig, JarvisConfig, load_config, save_config
from jarvis.installer import clone_config_for_root, repair_user_config
from jarvis.security.policy import Decision, Risk
from jarvis.settings import UserSettings, editable_paths


def test_root_configuration_is_independent_and_uses_private_paths(tmp_path: Path) -> None:
    user_home = tmp_path / "user"
    root_home = tmp_path / "root"
    root_project = tmp_path / "root-install"
    source = user_home / ".config/jarvis/config.xml"
    target = root_home / ".config/jarvis/config.xml"
    model = user_home / "models/model.gguf"
    original = JarvisConfig(
        settings=UserSettings(
            model_directory=model.parent,
            model_path=model,
            persona_path=user_home / "Persona.md",
        ),
        advanced=AdvancedConfig(
            llm_api_key="private-key",
            audit_db_path=user_home / ".local/state/jarvis/audit.db",
        ),
    )
    save_config(original, source)

    clone_config_for_root(
        source,
        target,
        root_home=root_home,
        root_project=root_project,
    )

    cloned = load_config(target)
    assert cloned.settings.model_path == model
    assert cloned.settings.permissions[Risk.READ] is Decision.ALLOW
    assert cloned.settings.permissions[Risk.DELETE] is Decision.CONFIRM
    assert cloned.settings.permissions[Risk.PRIVILEGED] is Decision.DENY
    assert cloned.settings.persona_path == editable_paths(root_home / ".config/jarvis")["persona"]
    assert cloned.advanced.audit_db_path == root_home / ".local/state/jarvis/audit.db"
    assert cloned.advanced.llm_api_key == "private-key"
    assert target.stat().st_mode & 0o777 == 0o600


def test_runtime_paths_are_separate_for_each_home(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from jarvis.settings import runtime_path

    first = tmp_path / "first"
    second = tmp_path / "second"
    monkeypatch.setenv("HOME", str(first))
    first_runtime = runtime_path()
    monkeypatch.setenv("HOME", str(second))
    second_runtime = runtime_path()

    assert first_runtime == first / ".local/state/jarvis/runtime.env"
    assert second_runtime == second / ".local/state/jarvis/runtime.env"
    assert first_runtime != second_runtime


def test_existing_root_configuration_is_preserved(tmp_path: Path) -> None:
    source = tmp_path / "user.xml"
    target = tmp_path / "root.xml"
    source_config = JarvisConfig(
        settings=UserSettings(assistant_name="User", persona_path=tmp_path / "user-persona")
    )
    root_config = JarvisConfig(
        settings=UserSettings(assistant_name="Root", persona_path=tmp_path / "root-persona")
    )
    save_config(source_config, source)
    save_config(root_config, target)

    clone_config_for_root(
        source,
        target,
        root_home=tmp_path / "root",
        root_project=tmp_path / "root-project",
        preserve_existing=True,
    )

    assert load_config(target).settings.assistant_name == "Root"


def test_repair_user_config_preserves_settings_and_creates_missing_resources(tmp_path: Path) -> None:
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
