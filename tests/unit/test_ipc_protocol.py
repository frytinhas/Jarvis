from __future__ import annotations

from uuid import uuid4

import pytest

from jarvis.ipc.errors import IpcError
from jarvis.ipc.models import (
    CORE_HEALTH,
    IPC_PROTOCOL_VERSION,
    REQUEST_STREAM,
    CoreInstanceId,
    negotiate,
    parse_hello,
    parse_request,
)

pytestmark = pytest.mark.unit


def _hello(**changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "type": "hello",
        "supported_versions": [1],
        "required_capabilities": [REQUEST_STREAM],
        "optional_capabilities": [CORE_HEALTH, "future-capability"],
        "client_name": "test-client",
        "resume": None,
    }
    value.update(changes)
    return value


def test_negotiation_selects_version_and_known_capabilities() -> None:
    version, capabilities = negotiate(parse_hello(_hello()))
    assert version == IPC_PROTOCOL_VERSION
    assert capabilities == (CORE_HEALTH, REQUEST_STREAM)


def test_protocol_and_required_capability_mismatch_are_typed() -> None:
    with pytest.raises(IpcError) as version:
        negotiate(parse_hello(_hello(supported_versions=[9])))
    assert version.value.code == "ipc.protocol_mismatch"
    with pytest.raises(IpcError) as capability:
        negotiate(parse_hello(_hello(required_capabilities=["missing-v1"])))
    assert capability.value.code == "ipc.capability_mismatch"


def test_unknown_fields_and_noncanonical_ids_are_rejected() -> None:
    with pytest.raises(IpcError):
        parse_hello(_hello(extra=True))
    request_id = str(uuid4())
    request = {
        "type": "request",
        "protocol_version": 1,
        "request_id": request_id.upper(),
        "operation": "core.health",
        "payload": {},
    }
    with pytest.raises(IpcError) as caught:
        parse_request(request)
    assert caught.value.code == "ipc.invalid_message"


def test_typed_ids_require_canonical_uuid4() -> None:
    value = uuid4()
    assert str(CoreInstanceId.parse(str(value))) == str(value)
    with pytest.raises(ValueError):
        CoreInstanceId.parse(str(value).upper())
