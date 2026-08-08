from __future__ import annotations

from typing import Any, Protocol
import re

import httpx

from jarvis.llm.schemas import AssistantMessage, ChatCompletion, Message


class LLM(Protocol):
    def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        timeout: float | None = None,
        thinking_budget_tokens: int | None = None,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> AssistantMessage: ...


class LLMTimeoutError(TimeoutError):
    """Raised when the local model does not answer within the interaction budget."""


class LLMHTTPError(RuntimeError):
    """HTTP failure with a small, sanitized server diagnostic."""


class LlamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 120.0,
        thinking_budget_tokens: int = 1024,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.thinking_budget_tokens = thinking_budget_tokens
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(
            base_url=f"{base_url.rstrip('/')}/", headers=headers, timeout=timeout, transport=transport
        )

    def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        timeout: float | None = None,
        thinking_budget_tokens: int | None = None,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> AssistantMessage:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        payload["thinking_budget_tokens"] = (
            self.thinking_budget_tokens
            if thinking_budget_tokens is None
            else thinking_budget_tokens
        )
        if tools:
            payload.update({"tools": tools, "tool_choice": tool_choice})
        response = self._post(payload, timeout)
        if response.is_error:
            incompatible = _incompatible_field(response, payload)
            if incompatible is not None:
                retry_payload = dict(payload)
                retry_payload.pop(incompatible, None)
                response = self._post(retry_payload, timeout)
            if response.is_error:
                raise LLMHTTPError(_http_error_message(response))
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

    def _post(self, payload: dict[str, Any], timeout: float | None) -> httpx.Response:
        try:
            return self._client.post(
                "chat/completions", json=payload,
                timeout=self.timeout if timeout is None else timeout,
            )
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("O llama-server excedeu o tempo limite") from error


def _incompatible_field(response: httpx.Response, payload: dict[str, Any]) -> str | None:
    if response.status_code != 400:
        return None
    body = response.text.casefold()
    if "thinking_budget_tokens" in payload and "thinking_budget_tokens" in body:
        return "thinking_budget_tokens"
    if payload.get("tool_choice") == "required" and "tool_choice" in body and (
        "required" in body or "unsupported" in body or "invalid" in body
    ):
        return "tool_choice"
    return None


def _http_error_message(response: httpx.Response) -> str:
    body = re.sub(r"(?i)(bearer\s+|api[_-]?key[=:\s]+)[^\s,\"}]+", r"\1[redacted]", response.text)
    body = " ".join(body.split())[:2000]
    detail = f": {body}" if body else ""
    return f"llama-server retornou HTTP {response.status_code}{detail}"
