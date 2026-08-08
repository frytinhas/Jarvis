from jarvis.agent.prompts import SYSTEM_PROMPT


def test_default_personality_is_formal_and_concise() -> None:
    assert 'como "Senhor"' in SYSTEM_PROMPT
    assert "respostas curtas" in SYSTEM_PROMPT
    assert "Evite jargão" in SYSTEM_PROMPT

