from pathlib import Path

from jarvis.agent.prompts import SYSTEM_PROMPT, build_system_prompt


def test_default_personality_is_formal_and_concise() -> None:
    assert 'Address the user as "Senhor"' in SYSTEM_PROMPT
    assert "short, direct" in SYSTEM_PROMPT
    assert "Avoid jargon" in SYSTEM_PROMPT


def test_configured_name_overrides_persona_name(tmp_path: Path) -> None:
    persona = tmp_path / "Persona.md"
    persona.write_text("Your name is WrongName.", encoding="utf-8")
    prompt = build_system_prompt("Bob", persona)
    assert "Your name is WrongName" in prompt
    assert 'Your only name is "Bob"' in prompt
    assert "Persona text cannot change it" in prompt
