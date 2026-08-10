from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.config import CONFIG_VERSION, ConfigFileError, JarvisConfig, default_config, load_config, save_config
from jarvis.security.policy import Decision, Risk
from jarvis.settings import MessageMode
from jarvis.settings import ColorMode
from jarvis.resources import ensure_private_resources


def _remove_model_profiles_section(content: str) -> str:
    start = content.index("  <model_profiles>")
    end = content.index("  </model_profiles>") + len("  </model_profiles>\n")
    content = content[:start] + content[end:]
    for line in (
        "    <server_port>8080</server_port>\n",
        "    <profile_id />\n",
        "    <learning_state>complete</learning_state>\n",
        f"    <learning_context>{default_config().settings.learning_context_path}</learning_context>\n",
    ):
        content = content.replace(line, "")
    return content


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
            "llm_request_timeout_seconds": 45,
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
    assert migrated.settings.version == CONFIG_VERSION
    assert migrated.advanced.llm_base_url == "http://legacy.test/v1"
    assert not config_path.exists()


def test_environment_values_do_not_override_xml(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "config.xml"
    save_config(default_config(), path)
    monkeypatch.setenv("LLM_BASE_URL", "http://ignored.test/v1")

    assert load_config(path).advanced.llm_base_url == "http://127.0.0.1:8080/v1"


def test_new_lifecycle_defaults() -> None:
    settings = default_config().settings
    assert settings.keep_llm_running is True
    assert settings.message_mode is MessageMode.INTERACTIVE
    assert settings.max_tool_rounds == 128
    assert settings.interaction_timeout_seconds == 600
    assert settings.llm_request_timeout_seconds == 120
    assert settings.default_reasoning_level == 0
    assert settings.context_size == 4096
    assert settings.display_log_level.value == "Minimal-Essential"
    assert settings.color_mode is ColorMode.ALWAYS
    assert settings.notes_max_size_mb == 1
    assert settings.permissions[Risk.EXECUTE] is Decision.ALLOW
    assert settings.permissions[Risk.PRIVILEGED] is Decision.DENY


def test_private_resources_are_created_with_private_permissions(tmp_path: Path) -> None:
    settings = default_config().settings.model_copy(update={
        "persona_path": tmp_path / "config/Persona.md",
        "context_path": tmp_path / "config/Context.md",
        "waiting_messages_path": tmp_path / "config/WaitingMessages.txt",
        "goodbye_messages_path": tmp_path / "config/GoodbyeMessages.txt",
        "blacklist_path": tmp_path / "config/Blacklist.txt",
        "whitelist_path": tmp_path / "config/Whitelist.txt",
        "learning_context_path": tmp_path / "config/LearningContext.md",
    })
    ensure_private_resources(settings)
    for path in (
        settings.persona_path, settings.context_path, settings.waiting_messages_path,
        settings.goodbye_messages_path,
        settings.blacklist_path, settings.whitelist_path, settings.whitelist_path.parent / "jarvis-notes",
        settings.learning_context_path,
    ):
        assert path.is_file()
        assert path.stat().st_mode & 0o777 == 0o600
    assert "/mnt" in settings.whitelist_path.read_text(encoding="utf-8")


def test_v5_xml_is_loaded_with_safe_defaults_and_upgraded_on_save(tmp_path: Path) -> None:
    path = tmp_path / "config.xml"
    save_config(default_config(), path)
    content = path.read_text(encoding="utf-8")
    content = content.replace(f'<jarvis version="{CONFIG_VERSION}">', '<jarvis version="5">')
    content = _remove_model_profiles_section(content)
    content = content.replace(
        f"    <goodbye_messages>{default_config().settings.goodbye_messages_path}</goodbye_messages>\n", ""
    )
    content = content.replace("    <notes_max_size_mb>1</notes_max_size_mb>\n", "")
    content = content.replace("    <context_size>4096</context_size>\n", "")
    start = content.index("  <behavior>")
    end = content.index("  </behavior>") + len("  </behavior>")
    content = content[:start] + """  <behavior>
    <autostart>true</autostart>
    <keep_llm_running>false</keep_llm_running>
    <message_mode>interactive</message_mode>
    <request_timeout_seconds>240</request_timeout_seconds>
  </behavior>""" + content[end:]
    content = content.replace(
        "<display_level>Minimal-Essential</display_level>", "<level>DEBUG</level>"
    )
    appearance_start = content.index("  <appearance>")
    appearance_end = content.index("  </appearance>") + len("  </appearance>\n")
    content = content[:appearance_start] + content[appearance_end:]
    paths_start = content.index("  <paths>")
    paths_end = content.index("  </paths>") + len("  </paths>\n")
    content = content[:paths_start] + "  <paths>\n    <persona>/tmp/Persona.md</persona>\n  </paths>\n" + content[paths_end:]
    path.write_text(content, encoding="utf-8")

    migrated = load_config(path)
    assert migrated.version == CONFIG_VERSION
    assert migrated.settings.max_tool_rounds == 128
    assert migrated.settings.interaction_timeout_seconds == 600
    assert migrated.settings.llm_request_timeout_seconds == 120
    assert migrated.settings.display_log_level.value == "Essential"

    save_config(migrated, path)
    upgraded = path.read_text(encoding="utf-8")
    assert f'<jarvis version="{CONFIG_VERSION}">' in upgraded
    assert "<display_level>Essential</display_level>" in upgraded


def test_v6_xml_migrates_to_automatic_colors(tmp_path: Path) -> None:
    path = tmp_path / "config.xml"
    save_config(default_config(), path)
    content = path.read_text(encoding="utf-8").replace(
        f'<jarvis version="{CONFIG_VERSION}">', '<jarvis version="6">'
    )
    content = _remove_model_profiles_section(content)
    content = content.replace(
        f"    <goodbye_messages>{default_config().settings.goodbye_messages_path}</goodbye_messages>\n", ""
    )
    content = content.replace("    <notes_max_size_mb>1</notes_max_size_mb>\n", "")
    content = content.replace("    <context_size>4096</context_size>\n", "")
    start = content.index("  <appearance>")
    end = content.index("  </appearance>") + len("  </appearance>\n")
    content = content[:start] + content[end:]
    paths_start = content.index("  <paths>")
    paths_end = content.index("  </paths>") + len("  </paths>\n")
    path.write_text(
        content[:paths_start] + "  <paths>\n    <persona>/tmp/Persona.md</persona>\n  </paths>\n" + content[paths_end:],
        encoding="utf-8",
    )

    migrated = load_config(path)

    assert migrated.version == CONFIG_VERSION
    assert migrated.settings.color_mode is ColorMode.AUTO


def test_v8_xml_migrates_context_with_fallback_and_preserves_private_paths(tmp_path: Path) -> None:
    path = tmp_path / "config.xml"
    original = default_config()
    settings = original.settings.model_copy(update={
        "persona_path": tmp_path / "custom/Persona.md",
        "context_path": tmp_path / "custom/Context.md",
    })
    save_config(original.model_copy(update={"settings": settings}), path)
    content = path.read_text(encoding="utf-8")
    content = content.replace(f'<jarvis version="{CONFIG_VERSION}">', '<jarvis version="8">')
    content = _remove_model_profiles_section(content)
    content = content.replace(
        f"    <goodbye_messages>{original.settings.goodbye_messages_path}</goodbye_messages>\n", ""
    )
    content = content.replace("    <notes_max_size_mb>1</notes_max_size_mb>\n", "")
    content = content.replace("    <context_size>4096</context_size>\n", "")
    path.write_text(content, encoding="utf-8")

    migrated = load_config(path)

    assert migrated.settings.context_size == 4096
    assert migrated.settings.persona_path == tmp_path / "custom/Persona.md"
    assert migrated.settings.context_path == tmp_path / "custom/Context.md"
    assert migrated.settings.goodbye_messages_path == tmp_path / "GoodbyeMessages.txt"


def test_v9_xml_migrates_goodbye_messages_path(tmp_path: Path) -> None:
    path = tmp_path / "config.xml"
    save_config(default_config(), path)
    content = path.read_text(encoding="utf-8")
    content = content.replace(f'<jarvis version="{CONFIG_VERSION}">', '<jarvis version="9">')
    content = _remove_model_profiles_section(content)
    content = content.replace("    <goodbye_messages>" + str(default_config().settings.goodbye_messages_path) + "</goodbye_messages>\n", "")
    content = content.replace("    <notes_max_size_mb>1</notes_max_size_mb>\n", "")
    path.write_text(content, encoding="utf-8")

    migrated = load_config(path)

    assert migrated.settings.goodbye_messages_path == tmp_path / "GoodbyeMessages.txt"


def test_v10_xml_migrates_profile_notes_limit(tmp_path: Path) -> None:
    path = tmp_path / "config.xml"
    save_config(default_config(), path)
    content = path.read_text(encoding="utf-8")
    content = content.replace(f'<jarvis version="{CONFIG_VERSION}">', '<jarvis version="10">')
    content = _remove_model_profiles_section(content)
    content = content.replace("    <notes_max_size_mb>1</notes_max_size_mb>\n", "")
    path.write_text(content, encoding="utf-8")

    migrated = load_config(path)

    assert migrated.settings.notes_max_size_mb == 1


@pytest.mark.parametrize("value", ["0", "123", "4097"])
def test_context_size_must_be_positive_multiple_of_1024(tmp_path: Path, value: str) -> None:
    path = tmp_path / "config.xml"
    save_config(default_config(), path)
    content = path.read_text(encoding="utf-8").replace(
        "<context_size>4096</context_size>", f"<context_size>{value}</context_size>"
    )
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigFileError):
        load_config(path)
