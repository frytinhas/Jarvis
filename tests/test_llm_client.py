from __future__ import annotations

import json
import httpx

from jarvis.llm.client import LlamaClient


def test_client_uses_configured_v1_chat_completions_route() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["body"] = request.read()
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]})

    with LlamaClient(
        "http://127.0.0.1:8080/v1",
        "local-model",
        transport=httpx.MockTransport(handler),
    ) as client:
        message = client.chat([{"role": "user", "content": "oi"}], [])

    assert observed["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert json.loads(observed["body"])["thinking_budget_tokens"] == 1024
    assert message.content == "ok"


def test_client_omits_tool_choice_when_no_tools_are_available() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        observed.update(json.loads(request.read()))
        return httpx.Response(200, json={"choices": [{"message": {"content": "summary"}}]})

    with LlamaClient(
        "http://127.0.0.1:8080/v1",
        "local-model",
        transport=httpx.MockTransport(handler),
    ) as client:
        client.chat([{"role": "user", "content": "summarize"}], [])

    assert "tools" not in observed
    assert "tool_choice" not in observed


def test_client_can_require_a_tool_call() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(json.loads(request.read()))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    tool = {
        "type": "function",
        "function": {"name": "get_system_info", "description": "specs", "parameters": {}},
    }
    with LlamaClient(
        "http://127.0.0.1:8080/v1",
        "local-model",
        transport=httpx.MockTransport(handler),
    ) as client:
        client.chat([{"role": "user", "content": "specs"}], [tool], tool_choice="required")

    assert observed["tool_choice"] == "required"


def test_client_uses_remaining_interaction_timeout() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(request.extensions["timeout"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    with LlamaClient(
        "http://127.0.0.1:8080/v1",
        "local-model",
        timeout=120,
        transport=httpx.MockTransport(handler),
    ) as client:
        client.chat([{"role": "user", "content": "oi"}], [], timeout=12.5)

    assert observed["read"] == 12.5
    assert observed["write"] == 12.5


def test_client_allows_per_request_reasoning_override() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed.update(json.loads(request.read()))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    with LlamaClient(
        "http://127.0.0.1:8080/v1", "local-model",
        thinking_budget_tokens=-1, transport=httpx.MockTransport(handler),
    ) as client:
        client.chat([{"role": "user", "content": "oi"}], [], thinking_budget_tokens=0)

    assert observed["thinking_budget_tokens"] == 0
