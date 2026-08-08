from jarvis.main import parse_initial_message


def test_initial_message_accepts_quoted_argument() -> None:
    assert parse_initial_message(["quais são as especificações?"]) == "quais são as especificações?"


def test_initial_message_joins_unquoted_words() -> None:
    assert parse_initial_message(["como", "está", "o", "sistema?"]) == "como está o sistema?"


def test_initial_message_is_optional() -> None:
    assert parse_initial_message([]) is None

