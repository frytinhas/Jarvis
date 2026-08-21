"""Opaque model identities and validated M004 registry values."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from uuid import RFC_4122, UUID, uuid4

from jarvis.models.errors import InvalidRuntimeConfigurationError


class ModelId:
    def __init__(self, value: UUID) -> None:
        if value.version != 4 or value.variant != RFC_4122:
            raise ValueError("model ID must be an RFC 4122 version-4 UUID")
        self.value = value

    @classmethod
    def new(cls) -> ModelId:
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> ModelId:
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError("model ID must use canonical lowercase UUID text")
        return cls(parsed)

    def __str__(self) -> str:
        return str(self.value)

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ModelId) and self.value == other.value


class ModelAvailability(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNREADABLE = "unreadable"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ModelRuntimeConfig:
    reasoning: str = "medium"
    context_window: int = 8192
    temperature: float = 0.8
    top_p: float = 0.95
    top_k: int = 40
    min_p: float = 0.0
    repeat_penalty: float = 1.1
    gpu_layers: int = 0
    threads: int = 1
    batch_size: int = 1
    flash_attention: bool = False
    startup_timeout_seconds: int = 60
    generation_timeout_seconds: int = 600
    tool_timeout_seconds: int = 60
    network_timeout_seconds: int = 30
    shutdown_timeout_seconds: int = 30
    llama_server_arguments: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.reasoning, str)
            or self.reasoning not in {"off", "low", "medium", "high", "max"}
            or type(self.context_window) is not int
            or not 1 <= self.context_window <= 1_000_000
        ):
            raise InvalidRuntimeConfigurationError("reasoning_or_context")
        if any(
            type(value) not in (int, float)
            for value in (self.temperature, self.top_p, self.min_p, self.repeat_penalty)
        ) or not (
            0 <= self.temperature <= 5
            and 0 <= self.top_p <= 1
            and 0 <= self.min_p <= 1
            and 0 <= self.repeat_penalty <= 10
        ):
            raise InvalidRuntimeConfigurationError("sampling")
        if type(self.top_k) is not int or not 0 <= self.top_k <= 100_000:
            raise InvalidRuntimeConfigurationError("top_k")
        if (
            any(
                type(value) is not int or not 0 <= value <= 1_000_000
                for value in (self.gpu_layers, self.threads, self.batch_size)
            )
            or type(self.flash_attention) is not bool
        ):
            raise InvalidRuntimeConfigurationError("resources")
        if any(
            type(value) is not int or not 1 <= value <= 86_400
            for value in (
                self.startup_timeout_seconds,
                self.generation_timeout_seconds,
                self.tool_timeout_seconds,
                self.network_timeout_seconds,
                self.shutdown_timeout_seconds,
            )
        ):
            raise InvalidRuntimeConfigurationError("timeouts")
        if (
            not isinstance(self.llama_server_arguments, tuple)
            or len(self.llama_server_arguments) > 64
        ):
            raise InvalidRuntimeConfigurationError("arguments")
        for value in self.llama_server_arguments:
            if not isinstance(value, str) or "\0" in value:
                raise InvalidRuntimeConfigurationError("arguments")
            try:
                if len(value.encode("utf-8")) > 4096:
                    raise InvalidRuntimeConfigurationError("arguments")
            except UnicodeEncodeError as error:
                raise InvalidRuntimeConfigurationError("arguments") from error

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: object) -> ModelRuntimeConfig:
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise InvalidRuntimeConfigurationError("wire_fields")
        copied = dict(value)
        args = copied.get("llama_server_arguments")
        if not isinstance(args, list | tuple):
            raise InvalidRuntimeConfigurationError("arguments")
        copied["llama_server_arguments"] = tuple(args)
        return cls(**copied)


@dataclass(frozen=True, slots=True)
class RuntimeLocationConfig:
    model_directories: tuple[Path, ...] = ()
    llama_server_path: Path | None = None
    revision: int = 1


@dataclass(frozen=True, slots=True)
class ModelRecord:
    model_id: ModelId
    canonical_path: Path
    device: int
    inode: int
    size_bytes: int
    mtime_ns: int
    metadata: dict[str, object]
    fingerprint_sha256: str
    availability: ModelAvailability
    availability_reason: str | None
    last_scanned_at_utc: str
