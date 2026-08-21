from __future__ import annotations

import asyncio
import os
import socket
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.foundation.bootstrap import DATABASE_FILENAME, initialize_foundation
from jarvis.llm.fake import FakeLLMProvider
from jarvis.llm.llama_cpp import LlamaCppProvider
from jarvis.llm.provider import RuntimeSpecification
from jarvis.models.models import ModelId, ModelRuntimeConfig
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.models import ProfileId
from jarvis.profiles.service import ProfileService
from jarvis.runtimes.artifacts import (
    RuntimeArtifacts,
    allocate_loopback_port,
    executable_identity,
    owned_listener,
)
from jarvis.runtimes.manager import RuntimeManager
from jarvis.runtimes.models import RuntimeHealthClass, RuntimeId, RuntimeState
from jarvis.storage.xdg import resolve_xdg_paths

pytestmark = pytest.mark.security

_ORIGINAL_CONNECT = socket.socket.connect
_ORIGINAL_CONNECT_EX = socket.socket.connect_ex


def test_native_provider_authenticates_owned_loopback_listener_and_stops_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path("tests/support/fake_llama_server.c").resolve()
    executable = tmp_path / "fake-llama-server"
    subprocess.run(
        ["cc", "-std=c11", "-O2", "-o", str(executable), str(source)],
        check=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )
    model = tmp_path / "model.gguf"
    model.write_bytes(b"GGUF-test-model")
    before = (model.read_bytes(), model.stat().st_mtime_ns)
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir(mode=0o700)
    initialize_foundation()
    paths = resolve_xdg_paths()
    profile_id = ProfileService(paths.data / DATABASE_FILENAME).ensure_jarvis().profile.profile_id
    artifacts = RuntimeArtifacts.acquire(runtime_root, str(profile_id))
    secret = "test-authentication-secret-never-log"
    key_path = artifacts.write_secret(secret)
    key_fd = artifacts.open_secret_descriptor()
    substituted = tmp_path / "substituted-key"
    substituted.write_text("attacker-controlled")
    key_path.unlink()
    key_path.symlink_to(substituted)
    model_fd = os.open(model, os.O_RDONLY | os.O_CLOEXEC)
    port = allocate_loopback_port()
    specification = RuntimeSpecification(
        RuntimeId.new(),
        profile_id,
        ModelId.new(),
        model_fd,
        executable,
        executable_identity(executable),
        artifacts.directory,
        "127.0.0.1",
        port,
        key_path,
        key_fd,
        secret,
        ModelRuntimeConfig(startup_timeout_seconds=3, network_timeout_seconds=1),
        4096,
    )
    monkeypatch.setattr(socket.socket, "connect", _ORIGINAL_CONNECT)
    monkeypatch.setattr(socket.socket, "connect_ex", _ORIGINAL_CONNECT_EX)
    monkeypatch.setenv("JARVIS_TEST_SECRET", "must-not-be-inherited")

    async def run() -> None:
        provider = LlamaCppProvider()
        handle = await provider.start(specification)
        os.close(model_fd)
        os.close(key_fd)
        for _ in range(100):
            health = await provider.health(handle, 1)
            if health.health is RuntimeHealthClass.HEALTHY:
                break
            await asyncio.sleep(0.01)
        assert health.state is RuntimeState.READY
        assert owned_listener(handle.evidence.pid, port)
        environment = {
            item.split(b"=", 1)[0].decode("ascii"): item.split(b"=", 1)[1].decode("ascii")
            for item in Path(f"/proc/{handle.evidence.pid}/environ").read_bytes().split(b"\0")
            if b"=" in item
        }
        assert environment == {
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "TZ": "UTC",
            "NO_COLOR": "1",
            "LLAMA_OFFLINE": "1",
        }
        assert Path(f"/proc/{handle.evidence.pid}/cwd").resolve() == artifacts.directory
        assert os.readlink(f"/proc/{handle.evidence.pid}/fd/0") == "/dev/null"
        assert secret.encode() not in Path(f"/proc/{handle.evidence.pid}/cmdline").read_bytes()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect(("127.0.0.1", port))
            client.sendall(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
            assert b"401 Unauthorized" in client.recv(1024)
        artifacts.remove_secret_if_owned()
        assert key_path.is_symlink()
        assert substituted.read_text() == "attacker-controlled"
        key_path.unlink()
        artifacts.write_metadata(
            {
                "runtime_id": str(handle.runtime_id),
                "profile_id": str(profile_id),
                "model_id": str(handle.model_id),
                "boot_id": handle.evidence.boot_id,
                "pid": handle.evidence.pid,
                "start_ticks": handle.evidence.start_ticks,
                "process_group_id": handle.evidence.process_group_id,
                "executable_device": handle.evidence.executable.device,
                "executable_inode": handle.evidence.executable.inode,
                "model_device": model.stat().st_dev,
                "model_inode": model.stat().st_ino,
                "endpoint_host": "127.0.0.1",
                "endpoint_port": port,
                "state": "READY",
            }
        )
        artifacts.release_lock()
        recovery = RuntimeManager(
            database_path=paths.data / DATABASE_FILENAME,
            runtime_root=runtime_root,
            models=ModelRegistryService(paths.data / DATABASE_FILENAME),
            provider=FakeLLMProvider(),
        )
        await recovery.recover_stale()
        await asyncio.wait_for(handle.process.wait(), 2)
        assert handle.process.returncode in {0, -9}
        stdout, stderr = await asyncio.gather(handle.stdout_task, handle.stderr_task)
        assert stdout.byte_count == stderr.byte_count == 4096
        assert stdout.dropped_bytes > 0 and stderr.dropped_bytes > 0

    asyncio.run(run())
    assert (model.read_bytes(), model.stat().st_mtime_ns) == before
    persisted = b"".join(path.read_bytes() for path in paths.state.rglob("*") if path.is_file())
    assert b"RAW_SERVER_OUTPUT_MUST_NOT_PERSIST" not in persisted
    assert secret.encode() not in persisted
    assert secret.encode() not in (paths.data / DATABASE_FILENAME).read_bytes()


def test_runtime_metadata_contains_no_secret_path_or_raw_argv(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    artifacts = RuntimeArtifacts.acquire(root, str(uuid4()))
    secret = "super-secret-runtime-token"
    artifacts.write_secret(secret)
    artifacts.write_metadata(
        {
            "runtime_id": str(uuid4()),
            "state": "STARTING",
            "endpoint_host": "127.0.0.1",
            "endpoint_port": 1234,
        }
    )
    payload = (artifacts.directory / "runtime.json").read_text()
    assert secret not in payload
    assert "api-key" not in payload
    assert "argv" not in payload
    artifacts.cleanup()


def test_provider_never_signals_an_unproven_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "exit.c"
    source.write_text("int main(void) { return 0; }\n")
    executable = tmp_path / "exit-server"
    subprocess.run(
        ["cc", "-std=c11", "-O2", "-o", str(executable), str(source)],
        check=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )
    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    artifacts = RuntimeArtifacts.acquire(root, str(uuid4()))
    key_path = artifacts.write_secret("test-key")
    key_fd = artifacts.open_secret_descriptor()
    model = tmp_path / "model.gguf"
    model.write_bytes(b"GGUF")
    model_fd = os.open(model, os.O_RDONLY)
    specification = RuntimeSpecification(
        RuntimeId.new(),
        ProfileId(uuid4()),
        ModelId.new(),
        model_fd,
        executable,
        executable_identity(executable),
        artifacts.directory,
        "127.0.0.1",
        allocate_loopback_port(),
        key_path,
        key_fd,
        "test-key",
        ModelRuntimeConfig(),
        128,
    )
    from jarvis.llm import llama_cpp
    from jarvis.runtimes.errors import RuntimeOwnershipError

    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(
        llama_cpp,
        "capture_process_evidence",
        lambda _pid, _identity: (_ for _ in ()).throw(RuntimeOwnershipError()),
    )
    monkeypatch.setattr(os, "killpg", lambda group, value: signals.append((group, value)))

    async def run() -> None:
        with pytest.raises(RuntimeOwnershipError):
            await LlamaCppProvider().start(specification)
        await asyncio.sleep(0.05)

    try:
        asyncio.run(run())
        assert signals == []
    finally:
        os.close(model_fd)
        os.close(key_fd)
        artifacts.cleanup()


def test_provider_reaps_an_already_exited_owned_child_without_pid_identity_error(
    tmp_path: Path,
) -> None:
    source = tmp_path / "exit.c"
    source.write_text("int main(void) { return 0; }\n")
    executable = tmp_path / "exit-server"
    subprocess.run(
        ["cc", "-std=c11", "-O2", "-o", str(executable), str(source)],
        check=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )
    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    artifacts = RuntimeArtifacts.acquire(root, str(uuid4()))
    key_path = artifacts.write_secret("test-key")
    key_fd = artifacts.open_secret_descriptor()
    model = tmp_path / "model.gguf"
    model.write_bytes(b"GGUF")
    model_fd = os.open(model, os.O_RDONLY)
    specification = RuntimeSpecification(
        RuntimeId.new(),
        ProfileId(uuid4()),
        ModelId.new(),
        model_fd,
        executable,
        executable_identity(executable),
        artifacts.directory,
        "127.0.0.1",
        allocate_loopback_port(),
        key_path,
        key_fd,
        "test-key",
        ModelRuntimeConfig(),
        128,
    )

    async def run() -> None:
        provider = LlamaCppProvider()
        handle = await provider.start(specification)
        await provider.stop(handle, 1)
        assert handle.process.returncode == 0

    try:
        asyncio.run(run())
    finally:
        os.close(model_fd)
        os.close(key_fd)
        artifacts.cleanup()
