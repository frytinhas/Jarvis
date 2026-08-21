"""Typed, client-neutral protocol values and exact message validation."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, Self
from uuid import RFC_4122, UUID, uuid4

from jarvis.ipc.errors import IpcError, ipc_error
from jarvis.profiles.models import ProfileId

IPC_PROTOCOL_VERSION = 1
SUPPORTED_PROTOCOL_VERSIONS = (IPC_PROTOCOL_VERSION,)

REQUEST_STREAM = "request-stream-v1"
REQUEST_CANCEL = "request-cancel-v1"
CORE_HEALTH = "core-health-v1"
PROFILE_CATALOG = "profile-catalog-v1"
PROFILE_MANAGEMENT = "profile-management-v1"
MODEL_REGISTRY = "model-registry-v1"
RUNTIME_MANAGER = "runtime-manager-v1"
CHAT_V1 = "chat-v1"
SESSION_RESUME = "session-resume-v1"
EVENT_REPLAY = "event-replay-v1"
CORE_CONTROL = "core-control-v1"
SERVER_CAPABILITIES = frozenset(
    {
        REQUEST_STREAM,
        REQUEST_CANCEL,
        CORE_HEALTH,
        PROFILE_CATALOG,
        PROFILE_MANAGEMENT,
        MODEL_REGISTRY,
        RUNTIME_MANAGER,
        CHAT_V1,
        SESSION_RESUME,
        EVENT_REPLAY,
        CORE_CONTROL,
    }
)


@dataclass(frozen=True, slots=True)
class _Uuid4Id:
    value: UUID

    def __post_init__(self) -> None:
        if self.value.version != 4 or self.value.variant != RFC_4122:
            raise ValueError("identifier must be an RFC 4122 version-4 UUID")

    @classmethod
    def parse(cls, value: str) -> Self:
        if not isinstance(value, str):
            raise ValueError("identifier must be text")
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError("identifier must use canonical lowercase UUID text")
        return cls(parsed)

    def __str__(self) -> str:
        return str(self.value)


class CoreInstanceId(_Uuid4Id):
    pass


class ConnectionId(_Uuid4Id):
    pass


class RequestId(_Uuid4Id):
    pass


class ProtocolIdGenerator(Protocol):
    def new_core_instance_id(self) -> CoreInstanceId: ...

    def new_connection_id(self) -> ConnectionId: ...


class RandomProtocolIdGenerator:
    def new_core_instance_id(self) -> CoreInstanceId:
        return CoreInstanceId(uuid4())

    def new_connection_id(self) -> ConnectionId:
        return ConnectionId(uuid4())


class DeterministicProtocolIdGenerator:
    def __init__(self, values: Iterable[UUID]) -> None:
        self._values = deque(values)

    def _next(self) -> UUID:
        try:
            return self._values.popleft()
        except IndexError as error:
            raise RuntimeError("deterministic protocol identifier sequence exhausted") from error

    def new_core_instance_id(self) -> CoreInstanceId:
        return CoreInstanceId(self._next())

    def new_connection_id(self) -> ConnectionId:
        return ConnectionId(self._next())


class RequestState(StrEnum):
    RECEIVED = "RECEIVED"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"

    @property
    def terminal(self) -> bool:
        return self in {self.COMPLETED, self.CANCELLED, self.FAILED}


@dataclass(frozen=True, slots=True)
class ResumeProof:
    expected_core_instance_id: CoreInstanceId
    connection_id: ConnectionId
    resume_token: str


@dataclass(frozen=True, slots=True)
class Hello:
    supported_versions: tuple[int, ...]
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...]
    client_name: str
    resume: ResumeProof | None


@dataclass(frozen=True, slots=True)
class IpcRequest:
    request_id: RequestId
    operation: str
    profile_id: ProfileId | None
    payload: Mapping[str, object]


_CLIENT_NAME_MAX_BYTES = 128
_CAPABILITY_MAX_BYTES = 128
_TOKEN_MAX_BYTES = 256


def _exact_fields(value: Mapping[str, object], allowed: set[str], required: set[str]) -> None:
    keys = set(value)
    if keys - allowed or not required.issubset(keys):
        raise ipc_error("ipc.invalid_message", reason="invalid_fields")


def _string_tuple(value: object, *, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 32:
        raise ipc_error("ipc.invalid_message", reason=f"invalid_{name}")
    result: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or not item
            or len(item.encode("utf-8")) > _CAPABILITY_MAX_BYTES
        ):
            raise ipc_error("ipc.invalid_message", reason=f"invalid_{name}")
        result.append(item)
    if len(set(result)) != len(result):
        raise ipc_error("ipc.invalid_message", reason=f"duplicate_{name}")
    return tuple(result)


def parse_hello(value: Mapping[str, object]) -> Hello:
    _exact_fields(
        value,
        {
            "type",
            "supported_versions",
            "required_capabilities",
            "optional_capabilities",
            "client_name",
            "resume",
        },
        {
            "type",
            "supported_versions",
            "required_capabilities",
            "optional_capabilities",
            "client_name",
            "resume",
        },
    )
    if value["type"] != "hello":
        raise ipc_error("ipc.invalid_message", reason="hello_required")
    versions = value["supported_versions"]
    if (
        not isinstance(versions, list)
        or not versions
        or len(versions) > 16
        or any(type(item) is not int or item <= 0 for item in versions)
    ):
        raise ipc_error("ipc.invalid_message", reason="invalid_versions")
    client_name = value["client_name"]
    if (
        not isinstance(client_name, str)
        or not client_name
        or len(client_name.encode("utf-8")) > _CLIENT_NAME_MAX_BYTES
    ):
        raise ipc_error("ipc.invalid_message", reason="invalid_client_name")
    resume_raw = value["resume"]
    resume: ResumeProof | None = None
    if resume_raw is not None:
        if not isinstance(resume_raw, dict):
            raise ipc_error("ipc.invalid_message", reason="invalid_resume")
        _exact_fields(
            resume_raw,
            {"expected_core_instance_id", "connection_id", "resume_token"},
            {"expected_core_instance_id", "connection_id", "resume_token"},
        )
        token = resume_raw["resume_token"]
        if not isinstance(token, str) or not token or len(token.encode("utf-8")) > _TOKEN_MAX_BYTES:
            raise ipc_error("ipc.invalid_message", reason="invalid_resume")
        try:
            resume = ResumeProof(
                CoreInstanceId.parse(str(resume_raw["expected_core_instance_id"])),
                ConnectionId.parse(str(resume_raw["connection_id"])),
                token,
            )
        except (ValueError, TypeError) as error:
            raise ipc_error("ipc.invalid_message", reason="invalid_resume") from error
    return Hello(
        tuple(versions),
        _string_tuple(value["required_capabilities"], name="required_capabilities"),
        _string_tuple(value["optional_capabilities"], name="optional_capabilities"),
        client_name,
        resume,
    )


def negotiate(hello: Hello) -> tuple[int, tuple[str, ...]]:
    common = sorted(set(hello.supported_versions) & set(SUPPORTED_PROTOCOL_VERSIONS), reverse=True)
    if not common:
        raise ipc_error("ipc.protocol_mismatch", supported_versions="1")
    missing = set(hello.required_capabilities) - SERVER_CAPABILITIES
    if missing:
        raise ipc_error("ipc.capability_mismatch", reason="required_capability_missing")
    capabilities = sorted(
        (set(hello.required_capabilities) | set(hello.optional_capabilities)) & SERVER_CAPABILITIES
    )
    return common[0], tuple(capabilities)


def parse_request(value: Mapping[str, object]) -> IpcRequest:
    _exact_fields(
        value,
        {"type", "protocol_version", "request_id", "operation", "profile_id", "payload"},
        {"type", "protocol_version", "request_id", "operation", "payload"},
    )
    if value["type"] != "request" or value["protocol_version"] != IPC_PROTOCOL_VERSION:
        raise ipc_error("ipc.invalid_message", reason="invalid_request_header")
    operation = value["operation"]
    payload = value["payload"]
    if not isinstance(operation, str) or not operation or len(operation.encode()) > 128:
        raise ipc_error("ipc.invalid_message", reason="invalid_operation")
    if not isinstance(payload, dict):
        raise ipc_error("ipc.invalid_message", reason="invalid_payload")
    try:
        request_id = RequestId.parse(str(value["request_id"]))
        profile_raw = value.get("profile_id")
        profile_id = None if profile_raw is None else ProfileId.parse(str(profile_raw))
    except (ValueError, TypeError) as error:
        raise ipc_error("ipc.invalid_message", reason="invalid_identifier") from error
    return IpcRequest(request_id, operation, profile_id, payload)


def parse_control_request(value: Mapping[str, object], expected_type: str) -> RequestId:
    _exact_fields(
        value,
        {"type", "protocol_version", "request_id"},
        {"type", "protocol_version", "request_id"},
    )
    if value["type"] != expected_type or value["protocol_version"] != IPC_PROTOCOL_VERSION:
        raise ipc_error("ipc.invalid_message", reason="invalid_control_message")
    try:
        return RequestId.parse(str(value["request_id"]))
    except (ValueError, TypeError) as error:
        raise ipc_error("ipc.invalid_message", reason="invalid_request_id") from error


def parse_replay_request(value: Mapping[str, object]) -> tuple[RequestId, int]:
    _exact_fields(
        value,
        {"type", "protocol_version", "request_id", "after_sequence"},
        {"type", "protocol_version", "request_id", "after_sequence"},
    )
    if value["type"] != "replay" or value["protocol_version"] != IPC_PROTOCOL_VERSION:
        raise ipc_error("ipc.invalid_message", reason="invalid_replay_message")
    after = value["after_sequence"]
    if type(after) is not int or after < 0:
        raise ipc_error("ipc.invalid_message", reason="invalid_after_sequence")
    try:
        return RequestId.parse(str(value["request_id"])), after
    except (ValueError, TypeError) as error:
        raise ipc_error("ipc.invalid_message", reason="invalid_request_id") from error


def safe_error_payload(error: BaseException) -> dict[str, object]:
    if isinstance(error, IpcError):
        return error.to_safe_dict()
    from jarvis.foundation.errors import JarvisError

    if isinstance(error, JarvisError):
        return error.to_safe_dict()
    return IpcError().to_safe_dict()
