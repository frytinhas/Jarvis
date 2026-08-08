import pytest

from jarvis.main import REASONING_BUDGETS, parse_initial_message, parse_invocation


def test_initial_message_accepts_quoted_argument() -> None:
    assert parse_initial_message(["quais são as especificações?"]) == "quais são as especificações?"


def test_initial_message_joins_unquoted_words() -> None:
    assert parse_initial_message(["como", "está", "o", "sistema?"]) == "como está o sistema?"


def test_initial_message_is_optional() -> None:
    assert parse_initial_message([]) is None


def test_reasoning_flag_is_removed_from_message_and_resolves_default() -> None:
    invocation = parse_invocation(["--r", "-1", "analise", "isto"], default_reasoning_level=3)
    assert invocation.message == "analise isto"
    assert invocation.reasoning_level == 3


@pytest.mark.parametrize("level,budget", [(0, 0), (1, 512), (2, 1024), (3, 2048), (4, -1)])
def test_reasoning_levels_have_expected_budgets(level: int, budget: int) -> None:
    assert REASONING_BUDGETS[level] == budget


def test_invalid_reasoning_level_is_rejected() -> None:
    with pytest.raises(SystemExit):
        parse_invocation(["--r", "5"])
