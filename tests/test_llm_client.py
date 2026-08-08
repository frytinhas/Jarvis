from __future__ import annotations

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
