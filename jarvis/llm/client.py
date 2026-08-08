from __future__ import annotations

from typing import Any, Protocol

import httpx

from jarvis.llm.schemas import AssistantMessage, ChatCompletion, Message


class LLM(Protocol):
    def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        timeout: float | None = None,
    ) -> AssistantMessage: ...


class LLMTimeoutError(TimeoutError):
    """Raised when the local model does not answer within the interaction budget."""


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
        self.timeout = timeout
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/", headers=headers, timeout=timeout, transport=transport
        )

    def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        timeout: float | None = None,
    ) -> AssistantMessage:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            payload.update({"tools": tools, "tool_choice": "auto"})
        try:
            response = self._client.post(
                "chat/completions",
                json=payload,
                timeout=self.timeout if timeout is None else timeout,
            )
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("O llama-server excedeu o tempo limite") from error
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
