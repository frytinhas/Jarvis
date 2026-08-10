from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol
import json
import re
import uuid

import httpx

from jarvis.llm.schemas import AssistantMessage, ChatCompletion, Message, ToolCall, ToolFunctionCall


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
        trace: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.thinking_budget_tokens = thinking_budget_tokens
        self._notice_handler = notice
        self._trace_handler = trace
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
        self._trace("llm_request", payload=request_payload)
        response = self._post(request_payload, timeout)
        self._trace("llm_response", status_code=response.status_code, body=_response_body(response))
        if response.is_error:
            incompatible = _incompatible_field(response, request_payload)
            if incompatible is not None:
                self._notice(
                    "O servidor não aceita um campo opcional do modelo; tentando uma alternativa compatível."
                )
                retry_payload = dict(request_payload)
                retry_payload.pop(incompatible, None)
                request_payload = retry_payload
                self._trace("llm_retry", removed_field=incompatible, payload=request_payload)
                response = self._post(request_payload, timeout)
                self._trace("llm_response", status_code=response.status_code, body=_response_body(response))
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
        message = completion.choices[0].message
        if tools and not message.tool_calls:
            fallback = _textual_tool_call(message.content, tools)
            if fallback is not None:
                self._trace("textual_tool_call_normalized", tool=fallback.function.name)
                return message.model_copy(update={"tool_calls": [fallback]})
        return message

    def _notice(self, message: str, *, critical: bool = False) -> None:
        if self._notice_handler is not None:
            self._notice_handler(LLMNotice(message, critical))

    def _trace(self, event: str, **payload: Any) -> None:
        if self._trace_handler is not None:
            try:
                self._trace_handler(event, payload)
            except Exception:
                pass

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


def _response_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text[:20_000]


def _textual_tool_call(content: str | None, tools: list[dict[str, Any]]) -> ToolCall | None:
    """Normalize one exact Qwen-style JSON envelope into a regular tool call.

    Plain prose is never interpreted as a command.  We accept exactly one complete
    JSON object with only ``tool_name`` and ``parameters``; malformed or multiple
    envelopes remain model text and therefore cannot execute anything.
    """
    if not content:
        return None
    objects = _json_objects(content)
    matches: list[tuple[str, dict[str, Any]]] = []
    for item in objects:
        if set(item) != {"tool_name", "parameters"}:
            continue
        name, parameters = item.get("tool_name"), item.get("parameters")
        if isinstance(name, str) and name and isinstance(parameters, dict):
            matches.append((name, parameters))
    if len(matches) != 1:
        return None
    name, parameters = matches[0]
    offered = {str(tool.get("function", {}).get("name", "")) for tool in tools}
    if name not in offered:
        return None
    return ToolCall(
        id=f"textual-{uuid.uuid4().hex}",
        function=ToolFunctionCall(name=name, arguments=json.dumps(parameters, ensure_ascii=False)),
    )


def _json_objects(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except ValueError:
            continue
        if isinstance(value, dict):
            objects.append(value)
    return objects
