from __future__ import annotations

import asyncio
import json
import struct

import pytest

from jarvis.ipc.codec import MAX_FRAME_BYTES, decode_payload, encode_frame, read_frame
from jarvis.ipc.errors import IpcError

pytestmark = pytest.mark.unit


def test_frame_round_trip_preserves_structural_characters_inside_strings() -> None:
    value: dict[str, object] = {
        "text": 'braces {[]} quotes " slash \\ unicode \u2603',
        "nested": [True, None, -7],
    }
    encoded = encode_frame(value)
    assert struct.unpack(">I", encoded[:4])[0] == len(encoded) - 4
    assert decode_payload(encoded[4:]) == value


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\xff",
        b"[]",
        b'{"a":1,"a":2}',
        b'{"n":1.0}',
        b'{"n":NaN}',
        b'{"n":9223372036854775808}',
        b'{"x":"\\uZZZZ"}',
    ],
)
def test_invalid_payloads_are_typed(raw: bytes) -> None:
    with pytest.raises(IpcError) as caught:
        decode_payload(raw)
    assert caught.value.code == "ipc.invalid_frame"


def test_structural_limits_are_enforced_after_json_parsing() -> None:
    nested: object = "end"
    for _ in range(33):
        nested = [nested]
    with pytest.raises(IpcError, match="ipc.invalid_frame"):
        decode_payload(json.dumps({"nested": nested}).encode())
    with pytest.raises(IpcError, match="ipc.invalid_frame"):
        decode_payload(json.dumps({"items": list(range(257))}).encode())
    with pytest.raises(IpcError, match="ipc.invalid_frame"):
        decode_payload(json.dumps({"text": "x" * 65_537}).encode())


def test_pathological_parser_recursion_is_translated() -> None:
    raw = b'{"value":' + b"[" * 2_000 + b"0" + b"]" * 2_000 + b"}"
    with pytest.raises(IpcError) as caught:
        decode_payload(raw)
    assert caught.value.code == "ipc.invalid_frame"


def test_oversized_declared_frame_is_not_drained() -> None:
    async def run() -> None:
        reader = asyncio.StreamReader()
        reader.feed_data(struct.pack(">I", MAX_FRAME_BYTES + 1))
        reader.feed_data(b"retained")
        with pytest.raises(IpcError) as caught:
            await read_frame(reader)
        assert caught.value.code == "ipc.message_too_large"
        assert await reader.read(8) == b"retained"

    asyncio.run(run())


def test_partial_header_and_body_fail_safely() -> None:
    async def run(data: bytes) -> str:
        reader = asyncio.StreamReader()
        reader.feed_data(data)
        reader.feed_eof()
        with pytest.raises(IpcError) as caught:
            await read_frame(reader)
        return caught.value.code

    assert asyncio.run(run(b"\x00\x01")) == "ipc.invalid_frame"
    assert asyncio.run(run(struct.pack(">I", 5) + b"{}")) == "ipc.invalid_frame"
