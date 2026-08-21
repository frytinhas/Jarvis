"""Hostile-boundary process evidence and private runtime artifacts."""

from __future__ import annotations

import fcntl
import json
import os
import socket
import stat
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import RFC_4122, UUID

from jarvis.llm.provider import ExecutableIdentity, ProcessEvidence
from jarvis.runtimes.errors import RuntimeArtifactError, RuntimeOwnershipError

MAX_METADATA_BYTES: Final = 16_384


def boot_id() -> str:
    value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    if len(value) != 36:
        raise RuntimeOwnershipError("boot_id_unavailable")
    return value


def process_start_ticks(pid: int) -> int:
    try:
        value = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        closing = value.rfind(")")
        fields = value[closing + 2 :].split()
        # starttime is field 22; fields begins with field 3.
        return int(fields[19])
    except (OSError, UnicodeError, ValueError, IndexError) as error:
        raise RuntimeOwnershipError("process_evidence_unavailable") from error


def executable_identity(path: Path) -> ExecutableIdentity:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RuntimeOwnershipError("executable_unavailable") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise RuntimeOwnershipError("executable_not_private_regular")
        if metadata.st_mode & 0o111 == 0:
            raise RuntimeOwnershipError("executable_not_executable")
        return ExecutableIdentity(metadata.st_dev, metadata.st_ino)
    finally:
        os.close(descriptor)


def capture_process_evidence(pid: int, expected: ExecutableIdentity) -> ProcessEvidence:
    try:
        metadata = os.stat(f"/proc/{pid}/exe")
        group = os.getpgid(pid)
    except OSError as error:
        raise RuntimeOwnershipError("process_evidence_unavailable") from error
    actual = ExecutableIdentity(metadata.st_dev, metadata.st_ino)
    if actual != expected or group != pid:
        raise RuntimeOwnershipError("executable_identity_mismatch")
    return ProcessEvidence(pid, group, boot_id(), process_start_ticks(pid), actual)


def process_matches(evidence: ProcessEvidence) -> bool:
    try:
        return capture_process_evidence(evidence.pid, evidence.executable) == evidence
    except RuntimeOwnershipError:
        return False


def process_owns_file(pid: int, device: int, inode: int) -> bool:
    try:
        entries = tuple(Path(f"/proc/{pid}/fd").iterdir())
    except OSError:
        return False
    for entry in entries:
        try:
            metadata = os.stat(entry)
        except OSError:
            continue
        if (metadata.st_dev, metadata.st_ino) == (device, inode):
            return True
    return False


def owned_listener(pid: int, port: int) -> bool:
    """Prove the expected process owns an IPv4 127.0.0.1 LISTEN socket."""

    socket_inodes: set[str] = set()
    try:
        for entry in Path(f"/proc/{pid}/fd").iterdir():
            try:
                target = os.readlink(entry)
            except OSError:
                continue
            if target.startswith("socket:[") and target.endswith("]"):
                socket_inodes.add(target[8:-1])
        lines = Path("/proc/net/tcp").read_text(encoding="ascii").splitlines()[1:]
    except OSError:
        return False
    expected_port = f"{port:04X}"
    for line in lines:
        fields = line.split()
        if len(fields) < 10:
            continue
        local, state, inode = fields[1], fields[3], fields[9]
        address, candidate_port = local.split(":", 1)
        if (
            address == "0100007F"
            and candidate_port == expected_port
            and state == "0A"
            and inode in socket_inodes
        ):
            return True
    return False


def allocate_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        candidate.bind(("127.0.0.1", 0))
        host, port = candidate.getsockname()
        if host != "127.0.0.1":
            raise RuntimeOwnershipError("non_loopback_endpoint")
        return int(port)


@dataclass(slots=True)
class RuntimeArtifacts:
    directory: Path
    directory_fd: int
    lock_fd: int
    metadata_identity: tuple[int, int] | None = None
    secret_identity: tuple[int, int] | None = None

    @classmethod
    def acquire(cls, root: Path, profile_id: str) -> RuntimeArtifacts:
        try:
            parsed = UUID(profile_id)
        except ValueError as error:
            raise RuntimeArtifactError("invalid_profile_id") from error
        if str(parsed) != profile_id or parsed.version != 4 or parsed.variant != RFC_4122:
            raise RuntimeArtifactError("invalid_profile_id")
        root_metadata = os.stat(root, follow_symlinks=False)
        if not stat.S_ISDIR(root_metadata.st_mode) or root_metadata.st_mode & 0o777 != 0o700:
            raise RuntimeArtifactError("unsafe_runtime_root")
        container = root / "runtimes"
        with suppress(FileExistsError):
            container.mkdir(mode=0o700)
        container_metadata = os.stat(container, follow_symlinks=False)
        if (
            not stat.S_ISDIR(container_metadata.st_mode)
            or container_metadata.st_mode & 0o777 != 0o700
        ):
            raise RuntimeArtifactError("unsafe_runtime_container")
        directory = container / profile_id
        with suppress(FileExistsError):
            directory.mkdir(mode=0o700)
        directory_metadata = os.stat(directory, follow_symlinks=False)
        if (
            not stat.S_ISDIR(directory_metadata.st_mode)
            or directory_metadata.st_mode & 0o777 != 0o700
        ):
            raise RuntimeArtifactError("unsafe_runtime_directory")
        directory_fd = os.open(
            directory,
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        opened_directory = os.fstat(directory_fd)
        if (opened_directory.st_dev, opened_directory.st_ino) != (
            directory_metadata.st_dev,
            directory_metadata.st_ino,
        ):
            os.close(directory_fd)
            raise RuntimeArtifactError("runtime_directory_changed")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open("runtime.lock", flags, 0o600, dir_fd=directory_fd)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise RuntimeArtifactError("unsafe_lock")
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, RuntimeArtifactError) as error:
            if "descriptor" in locals():
                os.close(descriptor)
            os.close(directory_fd)
            if isinstance(error, RuntimeArtifactError):
                raise
            raise RuntimeArtifactError("runtime_locked") from error
        return cls(directory, directory_fd, descriptor)

    def write_secret(self, secret: str) -> Path:
        path = self.directory / "api-key"
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            descriptor = os.open("api-key", flags, 0o600, dir_fd=self.directory_fd)
            os.write(descriptor, secret.encode("ascii"))
            os.fsync(descriptor)
            metadata = os.fstat(descriptor)
            self.secret_identity = (metadata.st_dev, metadata.st_ino)
        except OSError as error:
            raise RuntimeArtifactError("secret_file_failed") from error
        finally:
            if "descriptor" in locals():
                os.close(descriptor)
        return path

    def open_secret_descriptor(self) -> int:
        """Return a descriptor for the exact secret object created by this owner.

        llama-server accepts a pathname, but passing that pathname would let a
        same-user rename race substitute a key after Jarvis validates it.  The
        provider instead receives this descriptor and gives the child its own
        ``/proc/self/fd`` reference.
        """

        if self.secret_identity is None:
            raise RuntimeArtifactError("secret_identity_missing")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open("api-key", flags, dir_fd=self.directory_fd)
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or metadata.st_mode & 0o777 != 0o600
                or (metadata.st_dev, metadata.st_ino) != self.secret_identity
            ):
                raise RuntimeArtifactError("unsafe_secret")
            return descriptor
        except OSError as error:
            raise RuntimeArtifactError("secret_open_failed") from error
        except BaseException:
            if "descriptor" in locals():
                os.close(descriptor)
            raise

    def remove_secret_if_owned(self) -> None:
        self._unlink_if_owned("api-key", self.secret_identity)

    def read_metadata(self) -> dict[str, object] | None:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open("runtime.json", flags, dir_fd=self.directory_fd)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise RuntimeArtifactError("metadata_open_failed") from error
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or metadata.st_mode & 0o777 != 0o600
                or metadata.st_size > MAX_METADATA_BYTES
            ):
                raise RuntimeArtifactError("unsafe_metadata")
            payload = os.read(descriptor, MAX_METADATA_BYTES + 1)
            if len(payload) > MAX_METADATA_BYTES:
                raise RuntimeArtifactError("metadata_oversized")
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise RuntimeArtifactError("metadata_invalid")
            self.metadata_identity = (metadata.st_dev, metadata.st_ino)
            try:
                secret_metadata = os.stat(
                    "api-key", dir_fd=self.directory_fd, follow_symlinks=False
                )
            except FileNotFoundError:
                pass
            else:
                if (
                    not stat.S_ISREG(secret_metadata.st_mode)
                    or secret_metadata.st_nlink != 1
                    or secret_metadata.st_mode & 0o777 != 0o600
                ):
                    raise RuntimeArtifactError("unsafe_secret")
                self.secret_identity = (secret_metadata.st_dev, secret_metadata.st_ino)
            return value
        except (UnicodeError, ValueError) as error:
            raise RuntimeArtifactError("metadata_invalid") from error
        finally:
            os.close(descriptor)

    def write_metadata(self, value: dict[str, object]) -> None:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_METADATA_BYTES:
            raise RuntimeArtifactError("metadata_oversized")
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            descriptor = os.open("runtime.json.new", flags, 0o600, dir_fd=self.directory_fd)
            os.write(descriptor, encoded)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.replace(
                "runtime.json.new",
                "runtime.json",
                src_dir_fd=self.directory_fd,
                dst_dir_fd=self.directory_fd,
            )
            metadata = os.stat("runtime.json", dir_fd=self.directory_fd, follow_symlinks=False)
            self.metadata_identity = (metadata.st_dev, metadata.st_ino)
            os.fsync(self.directory_fd)
        except OSError as error:
            raise RuntimeArtifactError("metadata_write_failed") from error
        finally:
            if "descriptor" in locals() and descriptor >= 0:
                os.close(descriptor)

    def cleanup(self) -> None:
        self.remove_secret_if_owned()
        self._unlink_if_owned("runtime.json", self.metadata_identity)
        fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
        os.close(self.lock_fd)
        os.close(self.directory_fd)

    def _unlink_if_owned(self, name: str, expected: tuple[int, int] | None) -> None:
        try:
            metadata = os.stat(name, dir_fd=self.directory_fd, follow_symlinks=False)
            if (
                stat.S_ISREG(metadata.st_mode)
                and metadata.st_nlink == 1
                and metadata.st_mode & 0o777 == 0o600
                and expected is not None
                and expected == (metadata.st_dev, metadata.st_ino)
            ):
                os.unlink(name, dir_fd=self.directory_fd)
        except FileNotFoundError:
            pass

    def release_lock(self) -> None:
        fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
        os.close(self.lock_fd)
        os.close(self.directory_fd)
