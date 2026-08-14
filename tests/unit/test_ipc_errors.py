from __future__ import annotations

import pytest

from jarvis.ipc.errors import ipc_error
from jarvis.ipc.models import safe_error_payload

pytestmark = pytest.mark.unit


def test_ipc_error_has_only_safe_fields() -> None:
    error = ipc_error("ipc.invalid_message", reason="invalid_fields")
    assert error.to_safe_dict() == {
        "envelope_version": 1,
        "code": "ipc.invalid_message",
        "message_key": "error.ipc.invalid_message",
        "details": {"reason": "invalid_fields"},
    }


def test_unknown_exception_becomes_generic_internal_error() -> None:
    assert safe_error_payload(RuntimeError("private /home/path"))["code"] == "ipc.internal_error"
