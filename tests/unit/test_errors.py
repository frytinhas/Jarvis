from __future__ import annotations

from uuid import UUID

import pytest

from jarvis.foundation.errors import ConfigurationError
from jarvis.foundation.identifiers import CorrelationId

pytestmark = pytest.mark.unit


def test_safe_error_projection_excludes_internal_details_and_cause() -> None:
    correlation_id = CorrelationId(UUID("10000000-0000-4000-8000-000000000001"))
    try:
        raise ValueError("synthetic-password")
    except ValueError as cause:
        error = ConfigurationError(
            code="defaults.invalid",
            message_key="error.defaults.invalid",
            correlation_id=correlation_id,
            safe_details={"version": 1},
            internal_message="parser failed around synthetic-password",
        )
        error.__cause__ = cause

    safe = error.to_safe_dict()
    assert safe == {
        "envelope_version": 1,
        "code": "defaults.invalid",
        "message_key": "error.defaults.invalid",
        "correlation_id": str(correlation_id),
        "details": {"version": 1},
    }
    assert "synthetic-password" not in repr(safe)
    assert "traceback" not in repr(safe).lower()


def test_safe_details_are_copied_and_immutable() -> None:
    source = {"path_kind": "runtime"}
    error = ConfigurationError(safe_details=source)
    source["path_kind"] = "changed"
    assert error.safe_details["path_kind"] == "runtime"
    with pytest.raises(TypeError):
        error.safe_details["new"] = "value"  # type: ignore[index]


def test_safe_details_reject_nested_or_arbitrary_values() -> None:
    with pytest.raises(TypeError):
        ConfigurationError(safe_details={"unsafe": ["value"]})  # type: ignore[dict-item]


def test_safe_projection_rejects_secret_detail_keys_and_unstable_names() -> None:
    with pytest.raises(TypeError, match="secrets"):
        ConfigurationError(safe_details={"api_token": "synthetic-secret"})
    with pytest.raises(ValueError, match="error code"):
        ConfigurationError(code="synthetic-password")
    with pytest.raises(ValueError, match="message key"):
        ConfigurationError(message_key="Synthetic Password")
