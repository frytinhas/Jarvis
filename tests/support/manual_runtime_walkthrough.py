"""Disposable installed-wheel M005 walkthrough; never targets real user state."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import signal
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from jarvis.ipc.client import JarvisIpcClient
from jarvis.ipc.models import (
    EVENT_REPLAY,
    MODEL_REGISTRY,
    PROFILE_CATALOG,
    PROFILE_MANAGEMENT,
    REQUEST_STREAM,
    RUNTIME_MANAGER,
    SESSION_RESUME,
)
from jarvis.profiles.models import ProfileId


def _gguf(path: Path, name: bytes) -> None:
    key = b"general.name"
    path.write_bytes(
        b"GGUF"
        + struct.pack("<IQQ", 3, 0, 1)
        + struct.pack("<Q", len(key))
        + key
        + struct.pack("<I", 8)
        + struct.pack("<Q", len(name))
        + name
    )


def _manage(executable: Path, environment: dict[str, str], *arguments: str) -> dict[str, Any]:
    result = subprocess.run(
        [str(executable), *arguments],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    output = result.stdout.strip()
    if not output:
        raise AssertionError(f"jarvis-manage emitted no result: {result.stderr.strip()}")
    value: dict[str, Any] = json.loads(output.splitlines()[-1])
    if result.returncode != 0:
        raise AssertionError(f"jarvis-manage failed safely: {value}")
    return value


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    value = event["payload"]
    assert isinstance(value, dict)
    return value


async def _request(
    socket_path: Path,
    operation: str,
    *,
    profile_id: str | None = None,
    payload: dict[str, object] | None = None,
) -> dict[str, Any]:
    capabilities = (
        REQUEST_STREAM,
        MODEL_REGISTRY,
        RUNTIME_MANAGER,
        PROFILE_CATALOG,
        PROFILE_MANAGEMENT,
        SESSION_RESUME,
        EVENT_REPLAY,
    )
    client = await JarvisIpcClient.connect(
        socket_path, required_capabilities=capabilities, client_name="m005-walkthrough"
    )
    try:
        events = [
            event
            async for event in client.request(
                operation,
                payload=payload or {},
                profile_id=None if profile_id is None else ProfileId(UUID(profile_id)),
            )
        ]
        result = events[-1]
        if result.get("event_type") != "request.completed":
            raise AssertionError(f"IPC request failed: {result}")
        return result
    finally:
        await client.close()


def _wait_socket(
    socket_path: Path,
    process: subprocess.Popen[bytes],
    previous_identity: tuple[int, int] | None,
) -> None:
    for _ in range(500):
        try:
            metadata = socket_path.stat()
        except FileNotFoundError:
            pass
        else:
            if previous_identity != (metadata.st_dev, metadata.st_ino):
                return
        if process.poll() is not None:
            raise AssertionError(f"jarvisd exited before readiness: {process.returncode}")
        time.sleep(0.01)
    raise AssertionError("jarvisd did not create its socket")


def _start_core(
    executable: Path, environment: dict[str, str], socket_path: Path
) -> subprocess.Popen[bytes]:
    try:
        old = socket_path.stat()
        previous_identity = (old.st_dev, old.st_ino)
    except FileNotFoundError:
        previous_identity = None
    process = subprocess.Popen(
        [str(executable)],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _wait_socket(socket_path, process, previous_identity)
    return process


def _metadata(runtime_root: Path, profile_id: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            (runtime_root / "jarvis-cli" / "runtimes" / profile_id / "runtime.json").read_text()
        ),
    )


def _listener_is_only_loopback(pid: int, port: int) -> bool:
    inodes = {
        target[8:-1]
        for item in Path(f"/proc/{pid}/fd").iterdir()
        if (target := os.readlink(item)).startswith("socket:[")
    }
    matches = []
    for line in Path("/proc/net/tcp").read_text(encoding="ascii").splitlines()[1:]:
        fields = line.split()
        address, candidate_port = fields[1].split(":")
        if fields[9] in inodes and int(candidate_port, 16) == port and fields[3] == "0A":
            matches.append(address)
    return matches == ["0100007F"]


async def _walk(root: Path, source: Path) -> dict[str, object]:
    if root.exists():
        raise AssertionError("walkthrough root must not pre-exist")
    root.mkdir(mode=0o700)
    roots = {name: root / name for name in ("home", "config", "data", "state", "cache", "runtime")}
    for path in roots.values():
        path.mkdir(mode=0o700)
    environment = {
        "HOME": str(roots["home"]),
        "XDG_CONFIG_HOME": str(roots["config"]),
        "XDG_DATA_HOME": str(roots["data"]),
        "XDG_STATE_HOME": str(roots["state"]),
        "XDG_CACHE_HOME": str(roots["cache"]),
        "XDG_RUNTIME_DIR": str(roots["runtime"]),
        "PATH": str(Path(sys.executable).parent),
        "LANG": "C.UTF-8",
    }
    binary = root / "fake-llama-server"
    subprocess.run(
        ["/usr/bin/cc", "-std=c11", "-O2", "-o", str(binary), str(source)],
        check=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )
    models = root / "models"
    models.mkdir(mode=0o700)
    first_model = models / "one.gguf"
    second_model = models / "two.gguf"
    _gguf(first_model, b"One")
    _gguf(second_model, b"Two")
    before = {
        path.name: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
        for path in models.iterdir()
    }
    bindir = Path(sys.executable).parent
    jarvisd = bindir / "jarvisd"
    manage = bindir / "jarvis-manage"
    socket_path = roots["runtime"] / "jarvis-cli" / "core.sock"
    core = _start_core(jarvisd, environment, socket_path)
    _manage(
        manage,
        environment,
        "runtime-update",
        "--directory",
        str(models),
        "--runtime-path",
        str(binary),
    )
    refreshed = _payload(_manage(manage, environment, "refresh"))["models"]
    model_ids = {item["metadata"]["general.name"]: item["model_id"] for item in refreshed}
    profiles = _payload(await _request(socket_path, "profiles.list"))["profiles"]
    jarvis_id = next(item["profile_id"] for item in profiles if item["command_alias"] == "jarvis")
    _manage(
        manage,
        environment,
        "select",
        "--profile-id",
        jarvis_id,
        model_ids["One"],
        "--revision",
        "0",
    )
    policy = _payload(_manage(manage, environment, "runtime-policy-get"))
    assert policy["max_concurrent_runtimes"] == 2
    started = _payload(_manage(manage, environment, "runtime-start", "--profile-id", jarvis_id))
    assert started["state"] == "READY"
    evidence = _metadata(roots["runtime"], jarvis_id)
    assert _listener_is_only_loopback(evidence["pid"], evidence["endpoint_port"])
    assert not (roots["runtime"] / "jarvis-cli" / "runtimes" / jarvis_id / "api-key").exists()

    second = _payload(
        await _request(socket_path, "profiles.create", payload={"display_name": "Second"})
    )["profile"]
    second_started = _payload(
        _manage(manage, environment, "runtime-start", "--profile-id", second["profile_id"])
    )
    assert second_started["runtime_id"] != started["runtime_id"]
    third = _payload(
        await _request(socket_path, "profiles.create", payload={"display_name": "Third"})
    )["profile"]
    pending = subprocess.Popen(
        [str(manage), "runtime-start", "--profile-id", third["profile_id"]],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    await asyncio.sleep(0.2)
    assert pending.poll() is None
    os.kill(evidence["pid"], 0)
    _manage(manage, environment, "runtime-stop", "--profile-id", jarvis_id)
    output, error = pending.communicate(timeout=10)
    assert pending.returncode == 0, error
    assert _payload(json.loads(output.splitlines()[-1]))["state"] == "READY"
    _manage(manage, environment, "runtime-stop", "--profile-id", second["profile_id"])

    switched = _payload(
        _manage(
            manage,
            environment,
            "runtime-switch",
            "--profile-id",
            jarvis_id,
            model_ids["Two"],
            "--revision",
            "1",
        )
    )
    assert switched["model_id"] == model_ids["Two"]
    _manage(manage, environment, "runtime-stop", "--profile-id", jarvis_id)
    _manage(
        manage,
        environment,
        "runtime-update",
        "--directory",
        str(models),
        "--runtime-path",
        "/usr/bin/gnufalse",
    )
    failed = subprocess.run(
        [
            str(manage),
            "runtime-switch",
            "--profile-id",
            jarvis_id,
            model_ids["One"],
            "--revision",
            "1",
        ],
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert failed.returncode == 1 and '"code": "runtime.' in failed.stdout
    associations = _payload(
        await _request(socket_path, "profiles.models.list", profile_id=jarvis_id)
    )["associations"]
    assert next(item for item in associations if item["selected"])["model_id"] == model_ids["Two"]
    _manage(
        manage,
        environment,
        "runtime-update",
        "--directory",
        str(models),
        "--runtime-path",
        str(binary),
    )

    _manage(manage, environment, "runtime-start", "--profile-id", jarvis_id)
    preview = _payload(
        await _request(
            socket_path,
            "profiles.reset.preview",
            profile_id=jarvis_id,
            payload={"scope": "whole-profile"},
        )
    )["preview"]
    await _request(
        socket_path,
        "profiles.reset.confirm",
        profile_id=jarvis_id,
        payload={
            "scope": "whole-profile",
            "operation_id": preview["operation_id"],
            "confirmation_token": preview["confirmation_token"],
        },
    )
    _manage(manage, environment, "runtime-start", "--profile-id", second["profile_id"])
    deletion = _payload(
        await _request(socket_path, "profiles.delete.preview", profile_id=second["profile_id"])
    )["preview"]
    await _request(
        socket_path,
        "profiles.delete.confirm",
        profile_id=second["profile_id"],
        payload={
            "operation_id": deletion["operation_id"],
            "confirmation_token": deletion["confirmation_token"],
        },
    )

    orphan = _metadata(roots["runtime"], third["profile_id"])
    os.killpg(core.pid, signal.SIGKILL)
    core.wait(timeout=5)
    os.kill(orphan["pid"], 0)
    core = _start_core(jarvisd, environment, socket_path)
    for _ in range(200):
        try:
            os.kill(orphan["pid"], 0)
        except ProcessLookupError:
            break
        await asyncio.sleep(0.01)
    else:
        raise AssertionError("owned orphan survived Core restart recovery")
    core.send_signal(signal.SIGTERM)
    core.wait(timeout=5)

    ambiguous = subprocess.Popen(
        ["/usr/bin/sleep", "30"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    ambiguous_metadata = (
        roots["runtime"] / "jarvis-cli" / "runtimes" / third["profile_id"] / "runtime.json"
    )
    ambiguous_metadata.write_text(
        json.dumps(
            {
                "runtime_id": str(uuid4()),
                "profile_id": third["profile_id"],
                "model_id": model_ids["One"],
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                "pid": ambiguous.pid,
                "start_ticks": 1,
                "process_group_id": ambiguous.pid,
                "executable_device": 1,
                "executable_inode": 1,
                "model_device": first_model.stat().st_dev,
                "model_inode": first_model.stat().st_ino,
                "endpoint_host": "127.0.0.1",
                "endpoint_port": 12345,
                "state": "READY",
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    ambiguous_metadata.chmod(0o600)
    rejected = subprocess.Popen(
        [str(jarvisd)],
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    assert rejected.wait(timeout=5) == 1
    os.kill(ambiguous.pid, 0)
    ambiguous.send_signal(signal.SIGTERM)
    ambiguous.wait(timeout=5)
    ambiguous_metadata.unlink()
    final_core = _start_core(jarvisd, environment, socket_path)
    final_core.send_signal(signal.SIGTERM)
    final_core.wait(timeout=5)

    after = {
        path.name: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
        for path in models.iterdir()
    }
    assert before == after
    diagnostic_bytes = b"".join(
        path.read_bytes() for path in roots["state"].rglob("*") if path.is_file()
    )
    assert b"RAW_SERVER_OUTPUT_MUST_NOT_PERSIST" not in diagnostic_bytes
    assert not list(root.rglob("*.service"))
    return {
        "schema": 4,
        "defaults": 4,
        "same_model_independent": True,
        "capacity_queue": True,
        "switch_rollback": True,
        "reset_delete_quiesced": True,
        "orphan_recovered": True,
        "ambiguous_process_not_signalled": True,
        "loopback_only": True,
        "model_unchanged": True,
        "raw_output_absent": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--fake-source", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(asyncio.run(_walk(arguments.root, arguments.fake_source)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
