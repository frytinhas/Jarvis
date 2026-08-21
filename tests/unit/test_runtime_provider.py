from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.llm.llama_cpp import build_argv, controlled_environment
from jarvis.llm.provider import ExecutableIdentity, ProviderChatRequest, RuntimeSpecification
from jarvis.models.models import ModelId, ModelRuntimeConfig
from jarvis.profiles.models import ProfileId
from jarvis.runtimes.errors import RuntimeEndpointError, UnsupportedExtraArgumentsError
from jarvis.runtimes.models import RuntimeId, RuntimeState, is_legal_transition

pytestmark = pytest.mark.unit


def _specification(
    tmp_path: Path, config: ModelRuntimeConfig | None = None
) -> RuntimeSpecification:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"GGUF")
    descriptor = os.open(model, os.O_RDONLY)
    key = tmp_path / "api-key"
    key.write_text("secret-value")
    key_descriptor = os.open(key, os.O_RDONLY)
    return RuntimeSpecification(
        RuntimeId.new(),
        ProfileId(uuid4()),
        ModelId.new(),
        descriptor,
        Path("/usr/bin/gnutrue"),
        ExecutableIdentity(1, 2),
        tmp_path,
        "127.0.0.1",
        12345,
        key,
        key_descriptor,
        "secret-value",
        config or ModelRuntimeConfig(),
        1024,
    )


def test_llama_argv_is_structured_loopback_offline_and_secret_free(tmp_path: Path) -> None:
    specification = _specification(tmp_path)
    try:
        argv = build_argv(specification)
    finally:
        os.close(specification.model_fd)
        os.close(specification.api_key_fd)
    assert argv[0] == "/usr/bin/gnutrue"
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert "--offline" in argv and "--no-webui" in argv and "--no-webui-mcp-proxy" in argv
    assert specification.api_key not in argv
    assert argv[argv.index("--api-key-file") + 1] == f"/proc/self/fd/{specification.api_key_fd}"
    assert all("0.0.0.0" not in value and value != "::" for value in argv)


def test_non_loopback_and_extra_arguments_fail_before_spawn(tmp_path: Path) -> None:
    specification = _specification(tmp_path)
    try:
        object.__setattr__(specification, "host", "0.0.0.0")
        with pytest.raises(RuntimeEndpointError):
            build_argv(specification)
        object.__setattr__(specification, "host", "127.0.0.1")
        object.__setattr__(
            specification,
            "config",
            ModelRuntimeConfig(llama_server_arguments=("--host", "0.0.0.0")),
        )
        with pytest.raises(UnsupportedExtraArgumentsError):
            build_argv(specification)
    finally:
        os.close(specification.model_fd)
        os.close(specification.api_key_fd)


def test_environment_is_exact_allowlist_without_proxy_home_path_or_secrets() -> None:
    environment = controlled_environment()
    assert environment == {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "NO_COLOR": "1",
        "LLAMA_OFFLINE": "1",
    }


def test_provider_chat_request_is_opaque_and_runtime_states_are_explicit() -> None:
    payload = b"uncensored offensive-security reverse-engineering request\x00bytes"
    assert ProviderChatRequest(payload).payload == payload
    assert {state.value for state in RuntimeState} == {
        "STARTING",
        "READY",
        "BUSY",
        "ERROR",
        "STOPPING",
        "STOPPED",
    }


def test_runtime_state_transition_table_is_strict() -> None:
    assert is_legal_transition(None, RuntimeState.STARTING)
    assert is_legal_transition(RuntimeState.STARTING, RuntimeState.READY)
    assert is_legal_transition(RuntimeState.READY, RuntimeState.BUSY)
    assert is_legal_transition(RuntimeState.BUSY, RuntimeState.READY)
    assert is_legal_transition(RuntimeState.READY, RuntimeState.STOPPING)
    assert is_legal_transition(RuntimeState.STOPPING, RuntimeState.STOPPED)
    assert is_legal_transition(RuntimeState.ERROR, RuntimeState.STARTING)
    assert not is_legal_transition(None, RuntimeState.READY)
    assert not is_legal_transition(RuntimeState.READY, RuntimeState.STARTING)
    assert not is_legal_transition(RuntimeState.STOPPED, RuntimeState.READY)
