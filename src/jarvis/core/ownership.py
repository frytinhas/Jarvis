"""Descriptor-bound lifetime ownership and safe runtime-artifact recovery."""

from __future__ import annotations

import fcntl
import json
import os
import socket
import stat
import struct
from contextlib import suppress
from pathlib import Path

from jarvis.core.identity import CoreRuntimeIdentity
from jarvis.core.lifecycle import CoreLifecycleState
from jarvis.ipc.codec import decode_payload, encode_frame
from jarvis.ipc.errors import IpcError, ipc_error
from jarvis.ipc.models import IPC_PROTOCOL_VERSION, REQUEST_STREAM
from jarvis.storage.xdg import PRIVATE_FILE_MODE, verify_private_directory

LOCK_FILENAME = "core.lock"
SOCKET_FILENAME = "core.sock"
METADATA_FILENAME = "core-runtime.json"
MAX_METADATA_BYTES = 4_096
MAX_UNIX_PATH_BYTES = 107


def classify_lock_loser(runtime_directory: Path, *, timeout: float = 2.0) -> None:
    """Distinguish a reachable protocol-v1 owner without trusting runtime metadata."""

    path = runtime_directory / SOCKET_FILENAME
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(str(path))
        if hasattr(socket, "SO_PEERCRED"):
            raw = client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            _pid, uid, _gid = struct.unpack("3i", raw)
            if uid != os.getuid():
                raise OSError("Core peer UID mismatch")
        client.sendall(
            encode_frame(
                {
                    "type": "hello",
                    "supported_versions": [IPC_PROTOCOL_VERSION],
                    "required_capabilities": [REQUEST_STREAM],
                    "optional_capabilities": [],
                    "client_name": "jarvis-core-owner-probe",
                    "resume": None,
                }
            )
        )
        header = _recv_exact(client, 4)
        length = struct.unpack(">I", header)[0]
        if length <= 0 or length > 1_048_576:
            raise OSError("invalid Core probe frame")
        response = decode_payload(_recv_exact(client, length))
        if response.get("type") != "hello.ok":
            raise OSError("Core probe handshake failed")
    except (OSError, ValueError, IpcError) as error:
        raise ipc_error("ipc.core_unavailable", reason="owner_not_ready") from error
    finally:
        client.close()
    raise ipc_error("ipc.core_already_running")


def _recv_exact(client: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        chunk = client.recv(count - len(chunks))
        if not chunk:
            raise OSError("incomplete Core probe response")
        chunks.extend(chunk)
    return bytes(chunks)


def _private_regular(metadata: os.stat_result, uid: int) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_uid == uid
        and stat.S_IMODE(metadata.st_mode) == PRIVATE_FILE_MODE
        and metadata.st_nlink == 1
    )


class RuntimeOwnership:
    """The held lock descriptor is the sole cooperating-Core ownership authority."""

    def __init__(self, runtime_directory: Path, directory_fd: int, lock_fd: int) -> None:
        self.runtime_directory = runtime_directory
        self.socket_path = runtime_directory / SOCKET_FILENAME
        self._directory_fd = directory_fd
        self._lock_fd = lock_fd
        self._socket_identity: tuple[int, int] | None = None
        self._metadata_identity: tuple[int, int] | None = None
        self._closed = False

    @classmethod
    def acquire(cls, runtime_directory: Path) -> RuntimeOwnership:
        expected_directory = verify_private_directory(runtime_directory)
        flags = os.O_RDONLY | os.O_DIRECTORY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        directory_fd = os.open(runtime_directory, flags)
        lock_fd: int | None = None
        try:
            opened_directory = os.fstat(directory_fd)
            if (opened_directory.st_dev, opened_directory.st_ino) != (
                expected_directory.st_dev,
                expected_directory.st_ino,
            ):
                raise ipc_error("ipc.core_unavailable", reason="runtime_directory_changed")
            lock_flags = os.O_RDWR | os.O_CREAT
            if hasattr(os, "O_CLOEXEC"):
                lock_flags |= os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                lock_flags |= os.O_NOFOLLOW
            lock_fd = os.open(LOCK_FILENAME, lock_flags, PRIVATE_FILE_MODE, dir_fd=directory_fd)
            descriptor_metadata = os.fstat(lock_fd)
            path_metadata = os.stat(LOCK_FILENAME, dir_fd=directory_fd, follow_symlinks=False)
            if not _private_regular(descriptor_metadata, os.getuid()) or (
                descriptor_metadata.st_dev,
                descriptor_metadata.st_ino,
            ) != (path_metadata.st_dev, path_metadata.st_ino):
                raise ipc_error("ipc.core_unavailable", reason="unsafe_lock")
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ipc_error("ipc.core_already_running") from error
            ownership = cls(runtime_directory, directory_fd, lock_fd)
            ownership._recover_stale_artifacts()
            return ownership
        except BaseException:
            if lock_fd is not None:
                os.close(lock_fd)
            os.close(directory_fd)
            raise

    def _lstat_optional(self, name: str) -> os.stat_result | None:
        try:
            return os.stat(name, dir_fd=self._directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None

    def _unlink_matching(self, name: str, expected: os.stat_result) -> None:
        current = os.stat(name, dir_fd=self._directory_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (expected.st_dev, expected.st_ino):
            raise ipc_error("ipc.core_unavailable", reason="runtime_artifact_changed")
        os.unlink(name, dir_fd=self._directory_fd)
        os.fsync(self._directory_fd)

    def _recover_stale_artifacts(self) -> None:
        uid = os.getuid()
        socket_metadata = self._lstat_optional(SOCKET_FILENAME)
        if socket_metadata is not None:
            if (
                not stat.S_ISSOCK(socket_metadata.st_mode)
                or socket_metadata.st_uid != uid
                or stat.S_IMODE(socket_metadata.st_mode) != PRIVATE_FILE_MODE
                or socket_metadata.st_nlink != 1
            ):
                raise ipc_error("ipc.core_unavailable", reason="unsafe_stale_socket")
            self._unlink_matching(SOCKET_FILENAME, socket_metadata)
        metadata = self._lstat_optional(METADATA_FILENAME)
        if metadata is not None:
            if not _private_regular(metadata, uid) or metadata.st_size > MAX_METADATA_BYTES:
                raise ipc_error("ipc.core_unavailable", reason="unsafe_runtime_metadata")
            self._unlink_matching(METADATA_FILENAME, metadata)

    def validate_socket_path(self) -> None:
        if len(os.fsencode(self.socket_path)) > MAX_UNIX_PATH_BYTES:
            raise ipc_error("ipc.runtime_path_too_long", maximum_bytes=MAX_UNIX_PATH_BYTES)

    def bind_socket(self, *, backlog: int = 32) -> socket.socket:
        self.validate_socket_path()
        if self._lstat_optional(SOCKET_FILENAME) is not None:
            raise ipc_error("ipc.core_unavailable", reason="socket_already_exists")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        previous_umask = os.umask(0o177)
        try:
            server.bind(str(self.socket_path))
        except BaseException:
            server.close()
            raise
        finally:
            os.umask(previous_umask)
        try:
            os.chmod(self.socket_path, PRIVATE_FILE_MODE, follow_symlinks=False)
            metadata = os.stat(SOCKET_FILENAME, dir_fd=self._directory_fd, follow_symlinks=False)
            if (
                not stat.S_ISSOCK(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != PRIVATE_FILE_MODE
                or metadata.st_nlink != 1
            ):
                raise ipc_error("ipc.core_unavailable", reason="unsafe_bound_socket")
            self._socket_identity = (metadata.st_dev, metadata.st_ino)
            server.listen(backlog)
            server.setblocking(False)
            os.fsync(self._directory_fd)
            return server
        except BaseException:
            server.close()
            self._cleanup_socket()
            raise

    def publish_metadata(
        self,
        identity: CoreRuntimeIdentity,
        state: CoreLifecycleState,
        capabilities: list[str],
    ) -> None:
        payload = (
            json.dumps(
                identity.to_metadata(
                    state=state.value,
                    protocol_version=IPC_PROTOCOL_VERSION,
                    capabilities=capabilities,
                ),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
        if len(payload) > MAX_METADATA_BYTES:
            raise ipc_error("ipc.internal_error", reason="runtime_metadata_too_large")
        temporary = f".{METADATA_FILENAME}.tmp-{identity.core_instance_id}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, PRIVATE_FILE_MODE, dir_fd=self._directory_fd)
        try:
            offset = 0
            while offset < len(payload):
                written = os.write(descriptor, payload[offset:])
                if written <= 0:
                    raise OSError("zero-length runtime metadata write")
                offset += written
            os.fsync(descriptor)
            created = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        try:
            os.replace(
                temporary,
                METADATA_FILENAME,
                src_dir_fd=self._directory_fd,
                dst_dir_fd=self._directory_fd,
            )
            current = os.stat(METADATA_FILENAME, dir_fd=self._directory_fd, follow_symlinks=False)
            if not _private_regular(current, os.getuid()) or (
                current.st_dev,
                current.st_ino,
            ) != (created.st_dev, created.st_ino):
                raise ipc_error("ipc.core_unavailable", reason="runtime_metadata_changed")
            self._metadata_identity = (current.st_dev, current.st_ino)
            os.fsync(self._directory_fd)
        except BaseException:
            with suppress(OSError):
                os.unlink(temporary, dir_fd=self._directory_fd)
            raise

    def _cleanup_socket(self) -> None:
        if self._socket_identity is None:
            return
        try:
            current = os.stat(SOCKET_FILENAME, dir_fd=self._directory_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) == self._socket_identity:
                os.unlink(SOCKET_FILENAME, dir_fd=self._directory_fd)
                os.fsync(self._directory_fd)
        except FileNotFoundError:
            pass
        self._socket_identity = None

    def _cleanup_metadata(self) -> None:
        if self._metadata_identity is None:
            return
        try:
            current = os.stat(METADATA_FILENAME, dir_fd=self._directory_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) == self._metadata_identity:
                os.unlink(METADATA_FILENAME, dir_fd=self._directory_fd)
                os.fsync(self._directory_fd)
        except FileNotFoundError:
            pass
        self._metadata_identity = None

    def close(self) -> None:
        if self._closed:
            return
        self._cleanup_socket()
        self._cleanup_metadata()
        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        os.close(self._lock_fd)
        os.close(self._directory_fd)
        self._closed = True

    def __enter__(self) -> RuntimeOwnership:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
