from __future__ import annotations

from typing import Any, Literal
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ToolFunctionCall(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolFunctionCall


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class ChatChoice(BaseModel):
    message: AssistantMessage


class ChatCompletion(BaseModel):
    choices: list[ChatChoice]


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PathInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str


class ListDirectoryInput(PathInput):
    recursive: bool = False


class SearchFilesInput(PathInput):
    pattern: str = Field(min_length=1, max_length=256)
    max_results: int = Field(default=100, ge=1, le=1000)
    case_sensitive: bool = False


class SearchConversationLogsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=500)
    date_from: date | None = None
    date_to: date | None = None
    max_results: int = Field(default=5, ge=1, le=10)


class WriteFileInput(PathInput):
    content: str


class MoveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    destination: str


class RenameInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    new_name: str = Field(min_length=1, max_length=255)


Message = dict[str, Any]
