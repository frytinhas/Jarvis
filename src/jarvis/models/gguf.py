"""Bounded metadata-only GGUF reader.

GGUF stores magic/version, uint64 tensor/KV counts, then length-prefixed keys and
typed values.  This implementation follows ggml's documented v1-v3 layout and
intentionally stops before tensor descriptors/data.
"""

from __future__ import annotations

import hashlib
import math
import os
import stat
import struct
from dataclasses import dataclass

from .errors import InvalidGgufError, UnreadableModelError

MAX_HEADER_BYTES = 16 * 1024 * 1024
MAX_METADATA_ENTRIES = 8192
MAX_TENSOR_COUNT = 1_000_000
MAX_ARRAY_DEPTH = 16
MAX_KEY_BYTES = 256
MAX_DISPLAY_STRING_BYTES = 16 * 1024
MAX_ARRAY_PAYLOAD_BYTES = 64 * 1024
MAX_METADATA_PAYLOAD_BYTES = 16 * 1024 * 1024
DISPLAY_KEYS = frozenset(
    {
        "general.name",
        "general.architecture",
        "general.description",
        "general.file_type",
        "general.quantization_version",
        "general.size_label",
        "general.basename",
        "tokenizer.ggml.model",
    }
)
_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


@dataclass(frozen=True, slots=True)
class GgufMetadata:
    metadata: dict[str, object]
    header_digest: str
    device: int
    inode: int
    size: int
    mtime_ns: int


class _Reader:
    def __init__(self, fd: int, size: int) -> None:
        self.fd = fd
        self.size = size
        self.offset = 0
        self.used = 0
        self.digest = hashlib.sha256()

    def read(self, amount: int, *, digest: bool = True) -> bytes:
        if (
            amount < 0
            or amount > MAX_HEADER_BYTES
            or self.offset + amount > self.size
            or self.used + amount > MAX_HEADER_BYTES
        ):
            raise InvalidGgufError("truncated_or_budget")
        data = os.pread(self.fd, amount, self.offset)
        if len(data) != amount:
            raise InvalidGgufError("truncated")
        self.offset += amount
        self.used += amount
        if digest:
            self.digest.update(data)
        return data

    def number(self, fmt: str) -> int | float:
        value = struct.unpack(fmt, self.read(struct.calcsize(fmt)))[0]
        if not isinstance(value, int | float):
            raise InvalidGgufError("numeric_value")
        return value

    def string(self, maximum: int) -> bytes:
        n = self.number("<Q")
        if not isinstance(n, int) or n > maximum:
            raise InvalidGgufError("string_length")
        return self.read(n)


def _skip_value(
    reader: _Reader,
    value_type: int,
    *,
    array_budget: int = MAX_ARRAY_PAYLOAD_BYTES,
    depth: int = 0,
) -> object | None:
    if value_type in _SIZES:
        raw = reader.read(_SIZES[value_type])
        if value_type == 7:
            if raw not in (b"\0", b"\1"):
                raise InvalidGgufError("invalid_bool")
            return raw == b"\1"
        if value_type in (0, 2, 4, 10):
            return int.from_bytes(raw, "little", signed=False)
        if value_type in (1, 3, 5, 11):
            return int.from_bytes(raw, "little", signed=True)
        if value_type == 6:
            value = float(struct.unpack("<f", raw)[0])
            if not math.isfinite(value):
                raise InvalidGgufError("nonfinite_numeric")
            return value
        if value_type == 12:
            value = float(struct.unpack("<d", raw)[0])
            if not math.isfinite(value):
                raise InvalidGgufError("nonfinite_numeric")
            return value
    if value_type == 8:
        raw = reader.string(MAX_DISPLAY_STRING_BYTES)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if value_type == 9:
        if depth >= MAX_ARRAY_DEPTH:
            raise InvalidGgufError("array_depth")
        element_type = reader.number("<I")
        count = reader.number("<Q")
        if (
            not isinstance(element_type, int)
            or not isinstance(count, int)
            or element_type not in {*_SIZES, 8, 9}
            or count > MAX_ARRAY_PAYLOAD_BYTES
        ):
            raise InvalidGgufError("array_header")
        if element_type in _SIZES and count * _SIZES[element_type] > array_budget:
            raise InvalidGgufError("array_budget")
        start = reader.used
        # Arrays may be nested by format; bounded recursive skipping handles them exactly.
        for _ in range(count):
            _skip_value(reader, element_type, array_budget=array_budget, depth=depth + 1)
            if reader.used - start > array_budget:
                raise InvalidGgufError("array_budget")
        return None
    raise InvalidGgufError("unknown_value_type")


def read_gguf(path: str | os.PathLike[str]) -> GgufMetadata:
    # O_NONBLOCK is required before fstat: a pathname can change from a regular
    # candidate into a FIFO between caller validation and this open.  Metadata
    # parsing uses pread, so nonblocking mode has no effect for regular files.
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise UnreadableModelError("open_failed") from e
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise UnreadableModelError("not_regular")
        reader = _Reader(fd, before.st_size)
        if reader.read(4) != b"GGUF":
            raise InvalidGgufError("magic")
        version = reader.number("<I")
        if version not in (1, 2, 3):
            raise InvalidGgufError("version")
        tensors = reader.number("<Q")
        entries = reader.number("<Q")
        if (
            not isinstance(tensors, int)
            or not isinstance(entries, int)
            or tensors > MAX_TENSOR_COUNT
            or entries > MAX_METADATA_ENTRIES
        ):
            raise InvalidGgufError("metadata_count")
        metadata: dict[str, object] = {}
        for _ in range(entries):
            key_raw = reader.string(MAX_KEY_BYTES)
            try:
                key = key_raw.decode("ascii")
            except UnicodeDecodeError as e:
                raise InvalidGgufError("key_encoding") from e
            value_type = reader.number("<I")
            if not isinstance(value_type, int):
                raise InvalidGgufError("value_type")
            value = _skip_value(reader, value_type)
            if key in DISPLAY_KEYS and value is not None:
                metadata[key] = value
            if reader.used > MAX_METADATA_PAYLOAD_BYTES:
                raise InvalidGgufError("metadata_budget")
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise UnreadableModelError("changed_during_scan")
        return GgufMetadata(
            metadata,
            reader.digest.hexdigest(),
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
    finally:
        os.close(fd)


def read_gguf_fd(fd: int) -> GgufMetadata:
    """Parse an already-open read-only descriptor without reopening its pathname."""
    duplicate = os.dup(fd)
    try:
        before = os.fstat(duplicate)
        if not stat.S_ISREG(before.st_mode):
            raise UnreadableModelError("not_regular")
        reader = _Reader(duplicate, before.st_size)
        if reader.read(4) != b"GGUF":
            raise InvalidGgufError("magic")
        version = reader.number("<I")
        if version not in (1, 2, 3):
            raise InvalidGgufError("version")
        tensors = reader.number("<Q")
        entries = reader.number("<Q")
        if (
            not isinstance(tensors, int)
            or not isinstance(entries, int)
            or tensors > MAX_TENSOR_COUNT
            or entries > MAX_METADATA_ENTRIES
        ):
            raise InvalidGgufError("metadata_count")
        metadata: dict[str, object] = {}
        for _ in range(entries):
            try:
                key = reader.string(MAX_KEY_BYTES).decode("ascii")
            except UnicodeDecodeError as error:
                raise InvalidGgufError("key_encoding") from error
            value_type = reader.number("<I")
            if not isinstance(value_type, int):
                raise InvalidGgufError("value_type")
            value = _skip_value(reader, value_type)
            if key in DISPLAY_KEYS and value is not None:
                metadata[key] = value
            if reader.used > MAX_METADATA_PAYLOAD_BYTES:
                raise InvalidGgufError("metadata_budget")
        after = os.fstat(duplicate)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise UnreadableModelError("changed_during_scan")
        return GgufMetadata(
            metadata,
            reader.digest.hexdigest(),
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        )
    finally:
        os.close(duplicate)
