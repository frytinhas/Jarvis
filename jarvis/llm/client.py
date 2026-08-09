from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol
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


class LLMToolGrammarError(LLMHTTPError):
    """The server could not construct the constrained tool-call grammar."""


@dataclass(frozen=True)
class LLMNotice:
    message: str
    critical: bool = False


class LlamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 120.0,
        thinking_budget_tokens: int = 1024,
        transport: httpx.BaseTransport | None = None,
        notice: Callable[[LLMNotice], None] | None = None,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.thinking_budget_tokens = thinking_budget_tokens
        self._notice_handler = notice
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
        request_payload = payload
        response = self._post(request_payload, timeout)
        if response.is_error:
            incompatible = _incompatible_field(response, request_payload)
            if incompatible is not None:
                self._notice(
                    "O servidor não aceita um campo opcional do modelo; tentando uma alternativa compatível."
                )
                retry_payload = dict(request_payload)
                retry_payload.pop(incompatible, None)
                request_payload = retry_payload
                response = self._post(request_payload, timeout)
        if response.is_error and _grammar_failure(response) and "tools" in request_payload:
            # Never turn a failed local-data request into an unconstrained chat
            # response: that permits a model to pretend it used a tool.
            raise LLMToolGrammarError(_http_error_message(response))
        if response.is_error:
            message = _http_error_message(response)
            self._notice(message, critical=True)
            raise LLMHTTPError(message)
        try:
            completion = ChatCompletion.model_validate(response.json())
        except ValueError as error:
            self._notice("O servidor retornou uma resposta inválida do modelo.", critical=True)
            raise ValueError("O servidor retornou uma resposta inválida do modelo") from error
        if not completion.choices:
            self._notice("O servidor não retornou uma resposta do modelo.", critical=True)
            raise ValueError("O servidor não retornou escolhas")
        return completion.choices[0].message

    def _notice(self, message: str, *, critical: bool = False) -> None:
        if self._notice_handler is not None:
            self._notice_handler(LLMNotice(message, critical))

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
            self._notice("O llama-server excedeu o tempo limite da chamada.", critical=True)
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


def _grammar_failure(response: httpx.Response) -> bool:
    if response.status_code != 400:
        return False
    body = response.text.casefold()
    return "failed to parse grammar" in body or "failed to initialize samplers" in body


def _http_error_message(response: httpx.Response) -> str:
    body = re.sub(r"(?i)(bearer\s+|api[_-]?key[=:\s]+)[^\s,\"}]+", r"\1[redacted]", response.text)
    body = " ".join(body.split())[:2000]
    detail = f": {body}" if body else ""
    return f"llama-server retornou HTTP {response.status_code}{detail}"
