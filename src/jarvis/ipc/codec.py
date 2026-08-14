"""Bounded length-prefixed UTF-8 JSON framing for local IPC."""

from __future__ import annotations

import asyncio
import json
import struct
from collections.abc import Mapping
from typing import NoReturn

from jarvis.ipc.errors import IpcError, ipc_error

MAX_FRAME_BYTES = 1_048_576
MAX_DEPTH = 32
MAX_CONTAINER_ENTRIES = 256
MAX_NODES = 4_096
MAX_KEY_BYTES = 128
MAX_STRING_BYTES = 65_536
SIGNED_64_MIN = -(2**63)
SIGNED_64_MAX = 2**63 - 1
FRAME_TIMEOUT_SECONDS = 5.0


def _reject_float(_value: str) -> NoReturn:
    raise ValueError("floating-point values are not allowed")


def _parse_int(value: str) -> int:
    digits = value.removeprefix("-")
    if len(digits) > 19 or len(value) > 20:
        raise ValueError("integer representation is too long")
    parsed = int(value)
    if parsed < SIGNED_64_MIN or parsed > SIGNED_64_MAX:
        raise ValueError("integer is outside signed 64-bit range")
    return parsed


def _object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    if len(pairs) > MAX_CONTAINER_ENTRIES:
        raise ValueError("object has too many entries")
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate object key")
        result[key] = value
    return result


def decode_payload(payload: bytes) -> dict[str, object]:
    if not payload:
        raise ipc_error("ipc.invalid_frame", reason="zero_length")
    if len(payload) > MAX_FRAME_BYTES:
        raise ipc_error("ipc.message_too_large", maximum_bytes=MAX_FRAME_BYTES)
    try:
        text = payload.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_int=_parse_int,
            parse_float=_reject_float,
            parse_constant=_reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as error:
        raise ipc_error("ipc.invalid_frame", reason="invalid_json") from error
    if not isinstance(value, dict):
        raise ipc_error("ipc.invalid_frame", reason="root_not_object")
    _validate_tree(value)
    return value


def _validate_tree(root: object) -> None:
    stack: list[tuple[object, int]] = [(root, 1)]
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES:
            raise ipc_error("ipc.invalid_frame", reason="node_limit")
        if depth > MAX_DEPTH:
            raise ipc_error("ipc.invalid_frame", reason="depth_limit")
        if isinstance(value, dict):
            if len(value) > MAX_CONTAINER_ENTRIES:
                raise ipc_error("ipc.invalid_frame", reason="container_limit")
            for key, child in value.items():
                if not isinstance(key, str) or len(key.encode("utf-8")) > MAX_KEY_BYTES:
                    raise ipc_error("ipc.invalid_frame", reason="invalid_key")
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            if len(value) > MAX_CONTAINER_ENTRIES:
                raise ipc_error("ipc.invalid_frame", reason="container_limit")
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            if len(value.encode("utf-8")) > MAX_STRING_BYTES:
                raise ipc_error("ipc.invalid_frame", reason="string_limit")
        elif value is None or type(value) in {bool, int}:
            if type(value) is int and not SIGNED_64_MIN <= value <= SIGNED_64_MAX:
                raise ipc_error("ipc.invalid_frame", reason="integer_limit")
        else:
            raise ipc_error("ipc.invalid_frame", reason="invalid_scalar")


def encode_frame(value: Mapping[str, object]) -> bytes:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as error:
        raise ipc_error("ipc.invalid_message", reason="serialization_failed") from error
    decode_payload(payload)
    if len(payload) > MAX_FRAME_BYTES:
        raise ipc_error("ipc.message_too_large", maximum_bytes=MAX_FRAME_BYTES)
    return struct.pack(">I", len(payload)) + payload


async def read_frame(
    reader: asyncio.StreamReader, *, timeout: float = FRAME_TIMEOUT_SECONDS
) -> dict[str, object]:
    try:
        header = await asyncio.wait_for(reader.readexactly(4), timeout)
    except (asyncio.IncompleteReadError, TimeoutError) as error:
        raise ipc_error("ipc.invalid_frame", reason="incomplete_header") from error
    length = struct.unpack(">I", header)[0]
    if length == 0:
        raise ipc_error("ipc.invalid_frame", reason="zero_length")
    if length > MAX_FRAME_BYTES:
        raise ipc_error("ipc.message_too_large", maximum_bytes=MAX_FRAME_BYTES)
    try:
        payload = await asyncio.wait_for(reader.readexactly(length), timeout)
    except (asyncio.IncompleteReadError, TimeoutError) as error:
        raise ipc_error("ipc.invalid_frame", reason="incomplete_body") from error
    return decode_payload(payload)


async def write_frame(
    writer: asyncio.StreamWriter,
    value: Mapping[str, object],
    *,
    timeout: float = FRAME_TIMEOUT_SECONDS,
) -> None:
    writer.write(encode_frame(value))
    try:
        await asyncio.wait_for(writer.drain(), timeout)
    except (ConnectionError, TimeoutError) as error:
        raise IpcError(
            code="ipc.core_unavailable",
            message_key="error.ipc.transport_failed",
        ) from error
