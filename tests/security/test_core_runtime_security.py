from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

from jarvis.core.ownership import METADATA_FILENAME, SOCKET_FILENAME, RuntimeOwnership
from jarvis.ipc.errors import IpcError
from jarvis.storage.xdg import initialize_xdg_directories, resolve_xdg_paths

pytestmark = pytest.mark.security


def _runtime() -> Path:
    paths = resolve_xdg_paths()
    initialize_xdg_directories(paths)
    return paths.runtime


def test_lock_is_lifetime_authority_and_loser_cleans_nothing() -> None:
    runtime = _runtime()
    first = RuntimeOwnership.acquire(runtime)
    try:
        with pytest.raises(IpcError) as caught:
            RuntimeOwnership.acquire(runtime)
        assert caught.value.code == "ipc.core_already_running"
        assert (runtime / "core.lock").exists()
    finally:
        first.close()


def test_fifo_at_lock_path_fails_closed_without_blocking() -> None:
    runtime = _runtime()
    lock = runtime / "core.lock"
    os.mkfifo(lock, 0o600)
    with pytest.raises(IpcError) as caught:
        RuntimeOwnership.acquire(runtime)
    assert caught.value.code == "ipc.core_unavailable"
    assert lock.is_fifo()


@pytest.mark.parametrize("kind", ["symlink", "regular", "directory", "fifo"])
def test_unsafe_stale_socket_fails_closed(kind: str, tmp_path: Path) -> None:
    runtime = _runtime()
    target = runtime / SOCKET_FILENAME
    if kind == "symlink":
        target.symlink_to(tmp_path / "elsewhere")
    elif kind == "regular":
        target.write_text("not a socket")
        target.chmod(0o600)
    elif kind == "directory":
        target.mkdir(mode=0o700)
    else:
        os.mkfifo(target, 0o600)
    with pytest.raises(IpcError) as caught:
        RuntimeOwnership.acquire(runtime)
    assert caught.value.code == "ipc.core_unavailable"
    assert target.exists() or target.is_symlink()


def test_valid_stale_socket_and_metadata_are_recovered_without_pid_action() -> None:
    runtime = _runtime()
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(str(runtime / SOCKET_FILENAME))
    stale.close()
    (runtime / SOCKET_FILENAME).chmod(0o600)
    metadata = runtime / METADATA_FILENAME
    metadata.write_text('{"pid":1}\n')
    metadata.chmod(0o600)
    ownership = RuntimeOwnership.acquire(runtime)
    try:
        assert not (runtime / SOCKET_FILENAME).exists()
        assert not metadata.exists()
    finally:
        ownership.close()


def test_bound_socket_is_private_and_identity_safe_on_cleanup() -> None:
    runtime = _runtime()
    ownership = RuntimeOwnership.acquire(runtime)
    server = ownership.bind_socket()
    try:
        metadata = (runtime / SOCKET_FILENAME).lstat()
        assert metadata.st_uid == os.getuid()
        assert metadata.st_mode & 0o777 == 0o600
    finally:
        server.close()
        ownership.close()
    assert not (runtime / SOCKET_FILENAME).exists()
    assert (runtime / "core.lock").exists()


def test_runtime_path_bound_is_checked_before_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _runtime()
    ownership = RuntimeOwnership.acquire(runtime)
    try:
        monkeypatch.setattr(ownership, "socket_path", Path("/" + "x" * 200))
        with pytest.raises(IpcError) as caught:
            ownership.validate_socket_path()
        assert caught.value.code == "ipc.runtime_path_too_long"
    finally:
        ownership.close()
