"""Hostile-boundary llama-server provider using loopback-only authenticated HTTP."""

from __future__ import annotations

import asyncio
import json
import os
import signal
from collections.abc import AsyncIterator
from contextlib import suppress

from jarvis.foundation.clock import format_utc
from jarvis.llm.errors import RuntimeEndpointError, RuntimeOwnershipError, RuntimeStartupError
from jarvis.llm.provider import (
    ExecutableIdentity,
    ProcessEvidence,
    ProviderChatRequest,
    ProviderStreamEvent,
    ProviderStreamEventKind,
    RuntimeHandle,
    RuntimeHealth,
    RuntimeSpecification,
    StreamSummary,
)
from jarvis.runtimes.artifacts import capture_process_evidence, owned_listener, process_matches
from jarvis.runtimes.errors import UnsupportedExtraArgumentsError
from jarvis.runtimes.models import RuntimeHealthClass, RuntimeState

_PROCESS_EVIDENCE_SETTLE_SECONDS = 1.0


def _unique_json_object(pairs: list[tuple[object, object]]) -> dict[str, object]:
    """Decode JSON objects without accepting duplicate response fields."""

    result: dict[str, object] = {}
    for key, value in pairs:
        if not isinstance(key, str) or key in result:
            raise ValueError("invalid health JSON object")
        result[key] = value
    return result


def _is_documented_loading_response(payload: object) -> bool:
    """Match only llama-server's typed authenticated loading response."""

    if not isinstance(payload, dict) or set(payload) != {"error"}:
        return False
    error = payload["error"]
    return (
        isinstance(error, dict)
        and set(error) == {"message", "type", "code"}
        and error["message"] == "Loading model"
        and error["type"] == "unavailable_error"
        and type(error["code"]) is int
        and error["code"] == 503
    )


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


async def _capture_started_process_evidence(
    process: asyncio.subprocess.Process, expected: ExecutableIdentity
) -> ProcessEvidence:
    """Wait briefly for execve, while requiring the final exact process evidence."""

    deadline = asyncio.get_running_loop().time() + _PROCESS_EVIDENCE_SETTLE_SECONDS
    while True:
        try:
            return capture_process_evidence(process.pid, expected)
        except RuntimeOwnershipError:
            if asyncio.get_running_loop().time() >= deadline:
                raise
            await asyncio.sleep(0.01)


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
            evidence = await _capture_started_process_evidence(
                process, specification.executable_identity
            )
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
        try:
            if len(response) > 65_536:
                raise ValueError("oversized health response")
            head, body = response.split(b"\r\n\r\n", 1)
            status_parts = head.split(b"\r\n", 1)[0].split(b" ")
            if (
                len(status_parts) < 2
                or status_parts[0] != b"HTTP/1.1"
                or len(status_parts[1]) != 3
                or not status_parts[1].isdigit()
            ):
                raise ValueError("invalid health status")
            status = int(status_parts[1])
            payload = json.loads(body, object_pairs_hook=_unique_json_object)
        except (ValueError, UnicodeError):
            return RuntimeHealth(RuntimeState.ERROR, RuntimeHealthClass.UNHEALTHY, "health_invalid")
        if status == 503 and _is_documented_loading_response(payload):
            return RuntimeHealth(RuntimeState.STARTING, RuntimeHealthClass.UNKNOWN, "model_loading")
        if status != 200:
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

    async def chat(
        self, runtime: RuntimeHandle, request: ProviderChatRequest
    ) -> AsyncIterator[ProviderStreamEvent]:
        """Stream llama.cpp's authenticated loopback SSE without leaking transport upward."""

        from jarvis.chat.errors import ProviderStreamError

        if runtime.host != "127.0.0.1":
            raise ProviderStreamError("non_loopback_runtime")
        body = json.dumps(
            {
                "messages": [
                    {"role": message.role.value, "content": message.content}
                    for message in request.messages
                ],
                "temperature": request.temperature,
                "top_p": request.top_p,
                "top_k": request.top_k,
                "min_p": request.min_p,
                "repeat_penalty": request.repeat_penalty,
                "stream": True,
                "stream_options": {"include_usage": True},
            },
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(request.generation_timeout_seconds):
                reader, writer = await asyncio.open_connection(runtime.host, runtime.port)
                header = (
                    "POST /v1/chat/completions HTTP/1.1\r\n"
                    f"Host: {runtime.host}\r\n"
                    f"Authorization: Bearer {runtime.api_key}\r\n"
                    "Content-Type: application/json\r\n"
                    "Accept: text/event-stream\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
                writer.write(header + body)
                await writer.drain()
                status_and_headers = await reader.readuntil(b"\r\n\r\n")
                if len(status_and_headers) > 65_536:
                    raise ProviderStreamError("response_headers_too_large")
                head = status_and_headers.decode("ascii", "strict")
                lines = head.split("\r\n")
                if not lines or not lines[0].startswith("HTTP/1.1 200"):
                    raise ProviderStreamError("http_status")
                headers: dict[str, str] = {}
                for line in lines[1:]:
                    if not line:
                        continue
                    name, separator, value = line.partition(":")
                    if not separator:
                        raise ProviderStreamError("malformed_headers")
                    headers[name.strip().lower()] = value.strip().lower()
                total = 0
                frame = bytearray()
                completed = False
                usage: tuple[int | None, int | None] = (None, None)
                finish_reason: str | None = None
                async for chunk in _response_chunks(reader, headers, request.max_sse_frame_bytes):
                    total += len(chunk)
                    if total > request.max_response_bytes:
                        raise ProviderStreamError("response_too_large")
                    frame.extend(chunk)
                    if len(frame) > request.max_sse_frame_bytes:
                        raise ProviderStreamError("sse_frame_too_large")
                    while (located := _sse_boundary(frame)) is not None:
                        boundary, delimiter_size = located
                        raw = bytes(frame[:boundary]).replace(b"\r\n", b"\n")
                        del frame[: boundary + delimiter_size]
                        data_lines = [
                            line[5:].lstrip()
                            for line in raw.split(b"\n")
                            if line.startswith(b"data:")
                        ]
                        if not data_lines:
                            continue
                        data = b"\n".join(data_lines)
                        try:
                            decoded = data.decode("utf-8", "strict")
                        except UnicodeDecodeError as error:
                            raise ProviderStreamError("invalid_utf8") from error
                        if decoded == "[DONE]":
                            completed = True
                            yield ProviderStreamEvent(
                                ProviderStreamEventKind.COMPLETED,
                                prompt_tokens=usage[0],
                                completion_tokens=usage[1],
                                finish_reason=finish_reason,
                            )
                            return
                        try:
                            payload = json.loads(decoded)
                            if not isinstance(payload, dict):
                                raise ValueError
                            raw_usage = payload.get("usage")
                            if isinstance(raw_usage, dict):
                                prompt = raw_usage.get("prompt_tokens")
                                completion = raw_usage.get("completion_tokens")
                                usage = (
                                    prompt if type(prompt) is int and prompt >= 0 else None,
                                    (
                                        completion
                                        if type(completion) is int and completion >= 0
                                        else None
                                    ),
                                )
                            choices = payload.get("choices", [])
                            if not isinstance(choices, list):
                                raise ValueError
                            for choice in choices:
                                if not isinstance(choice, dict):
                                    raise ValueError
                                delta = choice.get("delta", {})
                                if not isinstance(delta, dict):
                                    raise ValueError
                                content = delta.get("content", "")
                                if content is None:
                                    content = ""
                                if not isinstance(content, str):
                                    raise ValueError
                                raw_finish_reason = choice.get("finish_reason")
                                if raw_finish_reason is not None:
                                    if (
                                        not isinstance(raw_finish_reason, str)
                                        or len(raw_finish_reason.encode("utf-8")) > 128
                                    ):
                                        raise ValueError
                                    finish_reason = raw_finish_reason
                                if len(content.encode("utf-8")) > request.max_delta_bytes:
                                    raise ProviderStreamError("delta_too_large")
                                if content:
                                    yield ProviderStreamEvent(
                                        ProviderStreamEventKind.TEXT_DELTA, text=content
                                    )
                        except (ValueError, TypeError, json.JSONDecodeError) as error:
                            raise ProviderStreamError("malformed_sse_json") from error
                if frame.strip():
                    raise ProviderStreamError("truncated_sse_frame")
                if not completed:
                    raise ProviderStreamError("provider_disconnected")
        except TimeoutError as error:
            raise ProviderStreamError("timeout") from error
        except asyncio.LimitOverrunError as error:
            raise ProviderStreamError("response_headers_too_large") from error
        except (OSError, asyncio.IncompleteReadError, UnicodeError) as error:
            raise ProviderStreamError("transport_failure") from error
        finally:
            if writer is not None:
                writer.close()
                with suppress(ConnectionError, OSError):
                    await writer.wait_closed()


async def _response_chunks(
    reader: asyncio.StreamReader, headers: dict[str, str], maximum_chunk: int
) -> AsyncIterator[bytes]:
    """Decode bounded HTTP/1.1 content-length, chunked, or close-delimited bodies."""

    from jarvis.chat.errors import ProviderStreamError

    if "chunked" in headers.get("transfer-encoding", ""):
        while True:
            line = await reader.readline()
            if len(line) > 128 or not line.endswith(b"\n"):
                raise ProviderStreamError("malformed_http_chunk")
            try:
                size = int(line.split(b";", 1)[0].strip(), 16)
            except ValueError as error:
                raise ProviderStreamError("malformed_http_chunk") from error
            if size == 0:
                await reader.readuntil(b"\r\n")
                return
            if size > maximum_chunk:
                raise ProviderStreamError("http_chunk_too_large")
            yield await reader.readexactly(size)
            if await reader.readexactly(2) != b"\r\n":
                raise ProviderStreamError("malformed_http_chunk")
    length = headers.get("content-length")
    if length is not None:
        try:
            remaining = int(length)
        except ValueError as error:
            raise ProviderStreamError("malformed_content_length") from error
        if remaining < 0:
            raise ProviderStreamError("malformed_content_length")
        while remaining:
            chunk = await reader.read(min(remaining, 65_536))
            if not chunk:
                raise ProviderStreamError("provider_disconnected")
            remaining -= len(chunk)
            yield chunk
        return
    while chunk := await reader.read(65_536):
        yield chunk


def _sse_boundary(frame: bytearray) -> tuple[int, int] | None:
    lf = frame.find(b"\n\n")
    crlf = frame.find(b"\r\n\r\n")
    candidates = [(offset, size) for offset, size in ((lf, 2), (crlf, 4)) if offset >= 0]
    return min(candidates) if candidates else None
