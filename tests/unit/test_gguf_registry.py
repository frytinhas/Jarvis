from __future__ import annotations

import os
import struct
from pathlib import Path

import pytest

from jarvis.config.defaults import DefaultsRegistry
from jarvis.models import gguf, scanner
from jarvis.models.errors import InvalidGgufError, UnreadableModelError
from jarvis.models.gguf import (
    MAX_ARRAY_DEPTH,
    MAX_ARRAY_PAYLOAD_BYTES,
    MAX_DISPLAY_STRING_BYTES,
    MAX_METADATA_ENTRIES,
    MAX_TENSOR_COUNT,
    read_gguf,
    read_gguf_fd,
)
from jarvis.models.models import ModelAvailability
from jarvis.models.scanner import ScanHooks, scan_directories

pytestmark = pytest.mark.unit


def _string(value: bytes) -> bytes:
    return struct.pack("<Q", len(value)) + value


def _fixture(path: Path) -> None:
    entries = [
        (b"general.name", 8, _string(b"Tiny")),
        (b"general.file_type", 4, struct.pack("<I", 7)),
    ]
    payload = b"GGUF" + struct.pack("<IQQ", 3, 0, len(entries))
    for key, kind, value in entries:
        payload += _string(key) + struct.pack("<I", kind) + value
    path.write_bytes(payload)


def test_reader_extracts_only_bounded_metadata(tmp_path: Path) -> None:
    path = tmp_path / "tiny.gguf"
    _fixture(path)
    result = read_gguf(path)
    assert result.metadata == {"general.name": "Tiny", "general.file_type": 7}
    assert result.size == path.stat().st_size


@pytest.mark.parametrize("version", [1, 2, 3])
def test_reader_accepts_each_supported_metadata_header_version(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / f"v{version}.gguf"
    path.write_bytes(b"GGUF" + struct.pack("<IQQ", version, 0, 0))
    assert read_gguf(path).metadata == {}


@pytest.mark.parametrize("payload", [b"BAD!", b"GGUF" + struct.pack("<IQQ", 99, 0, 0)])
def test_reader_rejects_bad_magic_or_version(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "bad.gguf"
    path.write_bytes(payload)
    with pytest.raises(InvalidGgufError):
        read_gguf(path)


def test_reader_rejects_attacker_controlled_string_length(tmp_path: Path) -> None:
    path = tmp_path / "bad.gguf"
    path.write_bytes(b"GGUF" + struct.pack("<IQQQ", 3, 0, 1, 2**63))
    with pytest.raises(InvalidGgufError):
        read_gguf(path)


def test_reader_rejects_truncation_count_and_oversized_display_metadata(tmp_path: Path) -> None:
    for name, payload in {
        "truncated.gguf": b"GGUF" + struct.pack("<IQQ", 3, 0, 1),
        "count.gguf": b"GGUF" + struct.pack("<IQQ", 3, 0, MAX_METADATA_ENTRIES + 1),
        "display.gguf": b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + _string(b"general.name")
        + struct.pack("<I", 8)
        + struct.pack("<Q", MAX_DISPLAY_STRING_BYTES + 1),
    }.items():
        path = tmp_path / name
        path.write_bytes(payload)
        with pytest.raises(InvalidGgufError):
            read_gguf(path)


def test_scanner_skips_links_deduplicates_hardlinks_and_retains_invalid_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "models"
    root.mkdir()
    valid = root / "valid.gguf"
    _fixture(valid)
    (root / "invalid.gguf").write_bytes(b"not-gguf")
    (root / "unrelated.txt").write_text("nothing")
    (root / "hard.gguf").hardlink_to(valid)
    (root / "link.gguf").symlink_to(valid)
    nested = root / "nested"
    nested.mkdir()
    (nested / "nested-link").symlink_to(root, target_is_directory=True)
    result = scan_directories((root,))
    assert len(result.records) == 2
    assert {record.availability for record in result.records} == {
        ModelAvailability.AVAILABLE,
        ModelAvailability.INVALID,
    }
    assert result.partial_reason is None


@pytest.mark.parametrize(
    "body",
    [
        _string(b"general.name") + struct.pack("<I", 13),
        _string(b"general.name") + struct.pack("<I", 6) + struct.pack("<f", float("inf")),
        _string(b"\xff") + struct.pack("<I", 0) + b"\0",
    ],
)
def test_reader_rejects_unsupported_nonfinite_and_malformed_metadata(
    tmp_path: Path, body: bytes
) -> None:
    path = tmp_path / "hostile.gguf"
    path.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, 0, 1) + body)
    with pytest.raises(InvalidGgufError):
        read_gguf(path)


def test_reader_bounds_tensor_count_and_nested_arrays(tmp_path: Path) -> None:
    excessive = tmp_path / "tensor-count.gguf"
    excessive.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, MAX_TENSOR_COUNT + 1, 0))
    with pytest.raises(InvalidGgufError):
        read_gguf(excessive)

    value = struct.pack("<IQB", 0, 1, 1)
    for _ in range(MAX_ARRAY_DEPTH + 1):
        value = struct.pack("<IQ", 9, 1) + value
    nested = tmp_path / "nested.gguf"
    nested.write_bytes(
        b"GGUF" + struct.pack("<IQQ", 3, 0, 1) + _string(b"ignored") + struct.pack("<I", 9) + value
    )
    with pytest.raises(InvalidGgufError):
        read_gguf(nested)

    huge = tmp_path / "array.gguf"
    huge.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + _string(b"ignored")
        + struct.pack("<IIQ", 9, 12, MAX_ARRAY_PAYLOAD_BYTES // 8 + 1)
    )
    with pytest.raises(InvalidGgufError):
        read_gguf(huge)


def test_reader_omits_invalid_utf8_display_value_and_rejects_non_regular_fd(
    tmp_path: Path,
) -> None:
    path = tmp_path / "utf8.gguf"
    path.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + _string(b"general.name")
        + struct.pack("<I", 8)
        + _string(b"\xff")
    )
    assert read_gguf(path).metadata == {}
    read_fd, write_fd = os.pipe()
    try:
        with pytest.raises(UnreadableModelError):
            read_gguf_fd(read_fd)
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_reader_and_scanner_do_not_block_on_fifo_swaps(tmp_path: Path) -> None:
    fifo = tmp_path / "fifo.gguf"
    os.mkfifo(fifo)
    with pytest.raises(UnreadableModelError):
        read_gguf(fifo)

    root = tmp_path / "models"
    root.mkdir()
    candidate = root / "candidate.gguf"
    _fixture(candidate)

    def replace_with_fifo(path: Path) -> None:
        path.unlink()
        os.mkfifo(path)

    result = scan_directories((root,), hooks=ScanHooks(before_candidate_open=replace_with_fifo))
    assert result.records[0].availability is ModelAvailability.UNREADABLE
    assert result.records[0].availability_reason == "candidate_changed_before_open"


def test_depth_limit_makes_the_scan_explicitly_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "models"
    root.mkdir()
    (root / "nested").mkdir()
    _fixture(root / "nested" / "candidate.gguf")
    monkeypatch.setattr("jarvis.models.scanner.MAX_DEPTH", 0)
    result = scan_directories((root,))
    assert result.records == ()
    assert result.partial_reason == "depth"


def test_scanner_detects_candidate_swaps_before_and_after_descriptor_open(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    candidate = root / "model.gguf"
    replacement = root / "replacement"
    _fixture(candidate)
    _fixture(replacement)

    def replace_before_open(path: Path) -> None:
        path.unlink()
        replacement.replace(path)

    before = scan_directories((root,), hooks=ScanHooks(before_candidate_open=replace_before_open))
    assert before.records[0].availability is ModelAvailability.UNREADABLE
    assert before.records[0].availability_reason == "candidate_changed_before_open"

    _fixture(replacement)

    def replace_after_open(path: Path, _fd: int) -> None:
        path.unlink()
        path.symlink_to(replacement)

    after = scan_directories((root,), hooks=ScanHooks(after_candidate_open=replace_after_open))
    assert after.records[0].availability is ModelAvailability.UNREADABLE
    assert after.records[0].availability_reason == "path_identity_mismatch"


def test_scanner_detects_directory_and_post_parse_path_replacement(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    candidate = root / "model.gguf"
    _fixture(candidate)
    moved = tmp_path / "original-models"

    def replace_directory(path: Path) -> None:
        path.rename(moved)
        path.mkdir()

    directory_result = scan_directories(
        (root,), hooks=ScanHooks(before_directory_read=replace_directory)
    )
    assert directory_result.records == ()
    assert directory_result.partial_reason == "directory_changed_during_scan"

    original = moved / "model.gguf"

    def disappear_after_parse(path: Path, _fd: int) -> None:
        path.unlink()

    disappeared = scan_directories(
        (moved,), hooks=ScanHooks(after_candidate_parse=disappear_after_parse)
    )
    assert disappeared.records[0].availability is ModelAvailability.UNREADABLE
    assert disappeared.records[0].availability_reason == "path_identity_mismatch"
    assert not original.exists()


def test_scanner_is_deterministic_bounded_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "models"
    root.mkdir()
    first = root / "a.gguf"
    _fixture(first)
    (root / "z.gguf").hardlink_to(first)
    second = root / "b.gguf"
    _fixture(second)
    before = {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in (first, second)}
    monkeypatch.setattr("jarvis.models.scanner.MAX_CANDIDATES", 1)
    result = scan_directories((root,))
    assert result.partial_reason == "candidates"
    assert [record.canonical_path.name for record in result.records] == ["a.gguf"]
    assert before == {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in (first, second)
    }


def test_scanner_reports_disappearing_or_symlinked_configured_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    assert scan_directories((missing,)).partial_reason == "root_unavailable"
    assert scan_directories((link,)).partial_reason == "root_unavailable"


def test_scanner_detects_regular_to_nonregular_and_concurrent_truncation(tmp_path: Path) -> None:
    nonregular_root = tmp_path / "nonregular"
    nonregular_root.mkdir()
    nonregular = nonregular_root / "model.gguf"
    _fixture(nonregular)

    def replace_with_directory(path: Path) -> None:
        path.unlink()
        path.mkdir()

    changed_type = scan_directories(
        (nonregular_root,), hooks=ScanHooks(before_candidate_open=replace_with_directory)
    )
    assert changed_type.records[0].availability is ModelAvailability.UNREADABLE
    assert changed_type.records[0].availability_reason == "candidate_changed_before_open"

    truncated_root = tmp_path / "truncated"
    truncated_root.mkdir()
    truncated = truncated_root / "model.gguf"
    _fixture(truncated)

    def truncate_open_descriptor(path: Path, _fd: int) -> None:
        path.write_bytes(b"GGUF")

    truncated_result = scan_directories(
        (truncated_root,), hooks=ScanHooks(after_candidate_open=truncate_open_descriptor)
    )
    assert truncated_result.records[0].availability is ModelAvailability.UNREADABLE
    assert truncated_result.records[0].availability_reason == "changed_during_scan"


def test_scanner_fingerprint_is_stable_then_invalidates_on_bounded_metadata_change(
    tmp_path: Path,
) -> None:
    root = tmp_path / "fingerprint"
    root.mkdir()
    path = root / "model.gguf"
    _fixture(path)
    first = scan_directories((root,)).records[0]
    unchanged = scan_directories((root,)).records[0]
    assert first.fingerprint_sha256 == unchanged.fingerprint_sha256
    _fixture(path)
    payload = path.read_bytes().replace(b"Tiny", b"Wide")
    path.write_bytes(payload)
    changed = scan_directories((root,)).records[0]
    assert changed.fingerprint_sha256 != first.fingerprint_sha256


def test_packaged_scanner_limits_match_enforced_constants() -> None:
    limits = DefaultsRegistry.load_packaged().current().model_defaults.scanner_limits
    assert dict(limits) == {
        "max_directories": scanner.MAX_DIRECTORIES,
        "max_path_bytes": scanner.MAX_PATH_BYTES,
        "max_depth": scanner.MAX_DEPTH,
        "max_directory_entries": scanner.MAX_DIRECTORY_ENTRIES,
        "max_candidates": scanner.MAX_CANDIDATES,
        "metadata_budget_bytes": gguf.MAX_HEADER_BYTES,
        "max_metadata_entries": gguf.MAX_METADATA_ENTRIES,
        "max_key_bytes": gguf.MAX_KEY_BYTES,
        "max_display_string_bytes": gguf.MAX_DISPLAY_STRING_BYTES,
        "max_array_payload_bytes": gguf.MAX_ARRAY_PAYLOAD_BYTES,
        "max_metadata_payload_bytes": gguf.MAX_METADATA_PAYLOAD_BYTES,
    }


def test_scanner_retains_non_utf8_candidate_as_sanitized_unreadable_record(
    tmp_path: Path,
) -> None:
    root = tmp_path / "non-utf8"
    root.mkdir()
    fixture = tmp_path / "fixture.gguf"
    _fixture(fixture)
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        candidate_fd = os.open(
            b"\xff.gguf", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=root_fd
        )
        try:
            os.write(candidate_fd, fixture.read_bytes())
        finally:
            os.close(candidate_fd)
    finally:
        os.close(root_fd)
    result = scan_directories((root,))
    assert len(result.records) == 1
    assert result.records[0].availability is ModelAvailability.UNREADABLE
    assert result.records[0].availability_reason == "path_encoding"
    str(result.records[0].canonical_path).encode("utf-8")
