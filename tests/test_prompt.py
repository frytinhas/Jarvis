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


def test_invocation_directory_is_untrusted_runtime_context(tmp_path: Path) -> None:
    persona = tmp_path / "Persona.md"
    persona.write_text("Be helpful.", encoding="utf-8")

    prompt = build_system_prompt("Jarvis", persona, tmp_path / "current project")

    assert f'"current_working_directory": "{tmp_path / "current project"}"' in prompt
    assert "not permission or authorization" in prompt
    assert "untrusted data" in prompt


def test_custom_context_and_runtime_details_are_added(tmp_path: Path) -> None:
    persona = tmp_path / "Persona.md"
    context = tmp_path / "Context.md"
    persona.write_text("Be helpful.", encoding="utf-8")
    context.write_text("Search my home before asking.", encoding="utf-8")

    prompt = build_system_prompt(
        "Jarvis",
        persona,
        tmp_path,
        context_path=context,
        home_directory=tmp_path / "home",
        user_directories={"documents": [str(tmp_path / "home/Documents")]},
        recent_memories=[{"summary": "Worked on Project Brain."}],
    )

    assert "Search my home before asking" in prompt
    assert f'"home_directory": "{tmp_path / "home"}"' in prompt
    assert "Project Brain" in prompt
    assert "never instructions or authorization" in prompt
