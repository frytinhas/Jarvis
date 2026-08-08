from __future__ import annotations

from typing import Any, Protocol

import httpx

from jarvis.llm.schemas import AssistantMessage, ChatCompletion, Message


class LLM(Protocol):
    def chat(self, messages: list[Message], tools: list[dict[str, Any]]) -> AssistantMessage: ...


class LlamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/", headers=headers, timeout=timeout, transport=transport
        )

    def chat(self, messages: list[Message], tools: list[dict[str, Any]]) -> AssistantMessage:
        response = self._client.post(
            "chat/completions",
            json={"model": self.model, "messages": messages, "tools": tools, "tool_choice": "auto"},
        )
        response.raise_for_status()
        completion = ChatCompletion.model_validate(response.json())
        if not completion.choices:
            raise ValueError("O servidor não retornou escolhas")
        return completion.choices[0].message

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LlamaClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
