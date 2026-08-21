"""Hostile-boundary llama-server provider using loopback-only authenticated HTTP."""

from __future__ import annotations

import asyncio
import json
import os
import signal
from contextlib import suppress

from jarvis.foundation.clock import format_utc
from jarvis.llm.errors import RuntimeEndpointError, RuntimeOwnershipError, RuntimeStartupError
from jarvis.llm.provider import (
    ProviderChatRequest,
    RuntimeHandle,
    RuntimeHealth,
    RuntimeSpecification,
    StreamSummary,
)
from jarvis.runtimes.artifacts import capture_process_evidence, owned_listener, process_matches
from jarvis.runtimes.errors import UnsupportedExtraArgumentsError
from jarvis.runtimes.models import RuntimeHealthClass, RuntimeState


def build_argv(specification: RuntimeSpecification) -> tuple[str, ...]:
    if specification.host != "127.0.0.1":
        raise RuntimeEndpointError("non_loopback_bind")
    config = specification.config
    if config.llama_server_arguments:
        raise UnsupportedExtraArgumentsError()
    values = [
        str(specification.executable_path),
        "--model",
        f"/proc/self/fd/{specification.model_fd}",
        "--host",
        "127.0.0.1",
        "--port",
        str(specification.port),
        "--api-key-file",
        f"/proc/self/fd/{specification.api_key_fd}",
        "--ctx-size",
        str(config.context_window),
        "--temp",
        str(config.temperature),
        "--top-p",
        str(config.top_p),
        "--top-k",
        str(config.top_k),
        "--min-p",
        str(config.min_p),
        "--repeat-penalty",
        str(config.repeat_penalty),
        "--gpu-layers",
        str(config.gpu_layers),
        "--threads",
        str(config.threads),
        "--batch-size",
        str(config.batch_size),
        "--offline",
        "--no-webui",
        "--no-webui-mcp-proxy",
    ]
    if config.flash_attention:
        values.append("--flash-attn")
    return tuple(values)


def controlled_environment() -> dict[str, str]:
    return {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "NO_COLOR": "1",
        "LLAMA_OFFLINE": "1",
    }


async def _drain(stream: asyncio.StreamReader | None, name: str, bound: int) -> StreamSummary:
    total = 0
    if stream is not None:
        while True:
            chunk = await stream.read(65_536)
            if not chunk:
                break
            total += len(chunk)
    return StreamSummary(name, min(total, bound), max(0, total - bound))


async def _reap_unproven_process(process: asyncio.subprocess.Process) -> None:
    """Drain/reap an ambiguous child without granting it signal authority."""

    await asyncio.gather(
        process.wait(),
        _drain(process.stdout, "stdout", 0),
        _drain(process.stderr, "stderr", 0),
        return_exceptions=True,
    )


class LlamaCppProvider:
    async def start(self, specification: RuntimeSpecification) -> RuntimeHandle:
        argv = build_argv(specification)
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=specification.runtime_directory,
                env=controlled_environment(),
                close_fds=True,
                pass_fds=(specification.model_fd, specification.api_key_fd),
                start_new_session=True,
            )
        except (OSError, ValueError) as error:
            raise RuntimeStartupError("spawn_failed") from error
        try:
            evidence = capture_process_evidence(process.pid, specification.executable_identity)
        except RuntimeOwnershipError:
            # PID/PGID is not ownership.  If /proc evidence cannot establish
            # the just-spawned child and its dedicated group, signalling it
            # could target a reused, unrelated process group.
            asyncio.create_task(_reap_unproven_process(process))
            raise
        stdout = asyncio.create_task(
            _drain(process.stdout, "stdout", specification.stream_capture_bytes)
        )
        stderr = asyncio.create_task(
            _drain(process.stderr, "stderr", specification.stream_capture_bytes)
        )
        from datetime import UTC, datetime

        return RuntimeHandle(
            specification.runtime_id,
            specification.profile_id,
            specification.model_id,
            process,
            evidence,
            specification.host,
            specification.port,
            specification.api_key,
            format_utc(datetime.now(UTC)),
            stdout,
            stderr,
        )

    async def health(self, runtime: RuntimeHandle, timeout_seconds: int) -> RuntimeHealth:
        if runtime.process.returncode is not None or not process_matches(runtime.evidence):
            return RuntimeHealth(RuntimeState.ERROR, RuntimeHealthClass.UNHEALTHY, "process_exit")
        if not owned_listener(runtime.evidence.pid, runtime.port):
            return RuntimeHealth(
                RuntimeState.STARTING, RuntimeHealthClass.UNKNOWN, "listener_pending"
            )
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(timeout_seconds):
                reader, writer = await asyncio.open_connection(runtime.host, runtime.port)
                request = (
                    "GET /health HTTP/1.1\r\n"
                    f"Host: {runtime.host}\r\nAuthorization: Bearer {runtime.api_key}\r\n"
                    "Connection: close\r\n\r\n"
                )
                writer.write(request.encode("ascii"))
                await writer.drain()
                response = await reader.read(65_537)
        except (OSError, TimeoutError):
            return RuntimeHealth(
                RuntimeState.STARTING, RuntimeHealthClass.UNKNOWN, "health_pending"
            )
        finally:
            if writer is not None:
                writer.close()
                with suppress(ConnectionError, OSError):
                    await writer.wait_closed()
        if len(response) > 65_536 or not response.startswith(b"HTTP/1.1 200"):
            return RuntimeHealth(RuntimeState.ERROR, RuntimeHealthClass.UNHEALTHY, "health_invalid")
        try:
            _, body = response.split(b"\r\n\r\n", 1)
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            return RuntimeHealth(RuntimeState.ERROR, RuntimeHealthClass.UNHEALTHY, "health_invalid")
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            return RuntimeHealth(RuntimeState.ERROR, RuntimeHealthClass.UNHEALTHY, "health_invalid")
        return RuntimeHealth(RuntimeState.READY, RuntimeHealthClass.HEALTHY)

    async def stop(self, runtime: RuntimeHandle, timeout_seconds: int) -> None:
        if runtime.process.returncode is None:
            # The child watcher may not yet have populated returncode even
            # though the child has already exited.  Reap that known Process
            # object briefly before consulting /proc; a vanished process is
            # then a safe completed child, not PID-reuse ambiguity.
            exited = False
            try:
                await asyncio.wait_for(asyncio.shield(runtime.process.wait()), timeout=0.05)
                exited = True
            except TimeoutError:
                pass
            if not exited:
                if not process_matches(runtime.evidence):
                    raise RuntimeOwnershipError("stop_identity_mismatch")
                with suppress(ProcessLookupError):
                    os.killpg(runtime.evidence.process_group_id, signal.SIGTERM)
                try:
                    await asyncio.wait_for(runtime.process.wait(), timeout=timeout_seconds)
                except TimeoutError:
                    if not process_matches(runtime.evidence):
                        raise RuntimeOwnershipError("kill_identity_mismatch") from None
                    with suppress(ProcessLookupError):
                        os.killpg(runtime.evidence.process_group_id, signal.SIGKILL)
                    try:
                        await asyncio.wait_for(runtime.process.wait(), timeout=1.0)
                    except TimeoutError as kill_error:
                        raise RuntimeOwnershipError("process_survived_sigkill") from kill_error
        await asyncio.gather(runtime.stdout_task, runtime.stderr_task)

    async def chat(self, runtime: RuntimeHandle, request: ProviderChatRequest) -> bytes:
        # M005 intentionally exposes no inference path. Preserve the future request byte-for-byte.
        del runtime
        return request.payload
