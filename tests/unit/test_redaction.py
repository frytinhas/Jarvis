from __future__ import annotations

from collections.abc import Iterator

import pytest

from jarvis.diagnostics.redaction import DEPTH_LIMIT, REDACTED, TRUNCATED, Redactor

pytestmark = pytest.mark.unit


def _redactor(**overrides: object) -> Redactor:
    values: dict[str, object] = {
        "max_text_bytes": 1024,
        "max_depth": 4,
        "max_container_entries": 4,
        "sensitive_environment_names": ("SYNTHETIC_CREDENTIAL",),
    }
    values.update(overrides)
    return Redactor(**values)  # type: ignore[arg-type]


def test_sensitive_nested_keys_are_replaced_wholesale() -> None:
    source = {
        "safe": "visible",
        "Password": "synthetic-password",
        "nested": {
            "api_key": "synthetic-api-key",
            "SYNTHETIC_CREDENTIAL": "synthetic-env-secret",
        },
    }
    result = _redactor().redact_value(source)
    assert result.value == {
        "safe": "visible",
        "Password": REDACTED,
        "nested": {"api_key": REDACTED, "SYNTHETIC_CREDENTIAL": REDACTED},
    }
    assert result.metadata.redacted_values == 3
    assert "synthetic" not in repr(result.value)


@pytest.mark.parametrize(
    "key",
    [
        "database_password",
        "OPENAI_API_KEY",
        "auth_token_value",
        "aws_secret_access_key",
        "credentials",
    ],
)
def test_composite_sensitive_keys_are_replaced_wholesale(key: str) -> None:
    result = _redactor().redact_value({key: "synthetic-composite-secret"})
    assert result.value == {key: REDACTED}


def test_secrets_embedded_in_mapping_keys_are_redacted() -> None:
    result = _redactor().redact_value({"token=synthetic-key-secret": "value"})
    assert "synthetic-key-secret" not in repr(result.value)
    assert isinstance(result.value, dict)
    assert f"token={REDACTED}" in result.value


@pytest.mark.parametrize(
    "secret_text",
    [
        "Authorization: Bearer synthetic-bearer-token",
        "Proxy-Authorization: Basic dXNlcjpwYXNz",
        "Cookie: session=synthetic-cookie",
        "token=synthetic-token",
        "https://synthetic-user:synthetic-password@example.test/path",
        "https://example.test/path?api_key=synthetic-api-key&safe=yes",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzeW50aGV0aWMifQ.signature1234",
        "-----BEGIN PRIVATE KEY-----\nsynthetic-private-key\n-----END PRIVATE KEY-----",
    ],
)
def test_text_patterns_remove_synthetic_secrets(secret_text: str) -> None:
    result = _redactor().redact_text(secret_text)
    assert result.metadata.redacted_values >= 1
    assert "synthetic" not in str(result.value)
    assert REDACTED in str(result.value)


def test_depth_and_collection_bounds_are_deterministic() -> None:
    result = _redactor(max_depth=2, max_container_entries=2).redact_value(
        {"a": [1, {"deep": "value"}, 3], "b": "value", "c": "dropped"}
    )
    assert result.value == {"a": [1, DEPTH_LIMIT], "b": "value"}
    assert result.metadata.dropped_items == 2
    assert result.metadata.depth_limited_values == 1


def test_oversized_text_is_bounded_before_matching_and_discards_boundary_overlap() -> None:
    prefix = "a" * 700
    secret = "synthetic-boundary-secret"
    text = prefix + secret + ("b" * 1000)
    result = _redactor(max_text_bytes=800).redact_text(text)
    encoded = str(result.value).encode()
    assert len(encoded) <= 800
    assert secret not in str(result.value)
    assert str(result.value).endswith(TRUNCATED)
    assert result.metadata.truncated_values == 1


def test_secret_length_is_not_preserved() -> None:
    short = _redactor().redact_value({"token": "x"})
    long = _redactor().redact_value({"token": "x" * 500})
    assert short.value == long.value == {"token": REDACTED}


def test_arbitrary_objects_are_bounded_as_text_without_environment_enumeration() -> None:
    class Synthetic:
        def __str__(self) -> str:
            return "password=synthetic-password"

    result = _redactor().redact_value(Synthetic())
    assert result.value == f"password={REDACTED}"


def test_container_bounds_do_not_materialize_an_entire_sequence() -> None:
    class ExplosiveTail(list[int]):
        def __iter__(self) -> Iterator[int]:
            yield 1
            yield 2
            yield 3
            raise AssertionError("the discarded tail must not be materialized")

    result = _redactor(max_container_entries=2).redact_value(ExplosiveTail())
    assert result.value == [1, 2]
    assert result.metadata.dropped_items == 1
