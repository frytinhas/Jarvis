"""Client-neutral, Core-owned setup-v1 orchestration."""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from enum import StrEnum

from jarvis.foundation.errors import JarvisError
from jarvis.models.models import ModelAvailability, ModelId, ModelRuntimeConfig
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.models import ProfileId
from jarvis.runtimes.errors import RuntimeManagerError
from jarvis.runtimes.manager import RuntimeManager
from jarvis.runtimes.models import RuntimeHealthClass, RuntimeState

MAX_SETUP_SESSIONS = 128


class SetupError(JarvisError):
    default_code = "setup.failed"
    default_message_key = "error.setup.failed"


class SetupState(StrEnum):
    READY = "ready"
    NEEDS_RUNTIME_PATH = "needs-runtime-path"
    NEEDS_MODEL_DIRECTORY = "needs-model-directory"
    NEEDS_DISCOVERY = "needs-discovery"
    NEEDS_MODEL_SELECTION = "needs-model-selection"
    NEEDS_ESSENTIAL_SETTINGS = "needs-essential-settings"
    VALIDATING = "validating"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(slots=True)
class _Session:
    token: str
    profile_id: ProfileId
    revision: int = 1
    discovery_attempted: bool = False
    essential_settings_pending: bool = False
    terminal_state: SetupState | None = None


class SetupService:
    """Own setup sessions and call only existing M004/M005 authorities."""

    def __init__(self, models: ModelRegistryService, runtimes: RuntimeManager) -> None:
        self._models = models
        self._runtimes = runtimes
        self._sessions: dict[str, _Session] = {}
        self._lock = asyncio.Lock()

    async def start(self, profile_id: ProfileId) -> dict[str, object]:
        async with self._lock:
            if len(self._sessions) >= MAX_SETUP_SESSIONS:
                raise SetupError(
                    code="setup.session_limit", message_key="error.setup.session_limit"
                )
            # A setup token must never become a durable-looking handle for an
            # arbitrary syntactically valid UUID.  The model repository remains
            # the existing authority for profile existence.
            try:
                await asyncio.to_thread(self._models.associations, profile_id)
            except JarvisError as error:
                raise SetupError(
                    code=error.code,
                    message_key=error.message_key,
                    safe_details=error.safe_details,
                ) from error
            token = secrets.token_urlsafe(32)
            session = _Session(token, profile_id)
            self._sessions[token] = session
            return await self._snapshot(session)

    async def advance(
        self,
        profile_id: ProfileId,
        token: str,
        expected_revision: int,
        action: str,
        value: object,
    ) -> dict[str, object]:
        async with self._lock:
            session = self._require(profile_id, token, expected_revision)
            self._require_live(session)
            location = await asyncio.to_thread(self._models.runtime_location)
            if action == "runtime-path":
                if not isinstance(value, str) or not value:
                    raise _invalid("runtime_path")
                await asyncio.to_thread(
                    self._models.update_runtime_location,
                    tuple(str(path) for path in location.model_directories),
                    value,
                )
            elif action == "model-directory":
                if not isinstance(value, str) or not value:
                    raise _invalid("model_directory")
                directories = [str(path) for path in location.model_directories]
                if value not in directories:
                    directories.append(value)
                await asyncio.to_thread(
                    self._models.update_runtime_location,
                    tuple(directories),
                    None if location.llama_server_path is None else str(location.llama_server_path),
                )
                session.discovery_attempted = False
            elif action == "discover":
                if value is not None:
                    raise _invalid("discover")
                await asyncio.to_thread(self._models.refresh)
                session.discovery_attempted = True
            elif action == "select-model":
                if not isinstance(value, str):
                    raise _invalid("model")
                try:
                    model_id = ModelId.parse(value)
                except ValueError as error:
                    raise _invalid("model") from error
                associations = await asyncio.to_thread(self._models.associations, profile_id)
                matching = [item for item in associations if item["model_id"] == value]
                revision_value = matching[0]["revision"] if matching else 0
                if type(revision_value) is not int:
                    raise _invalid("revision")
                revision = revision_value
                await asyncio.to_thread(self._models.select, profile_id, model_id, revision)
                session.essential_settings_pending = True
            elif action == "essential-settings":
                if not isinstance(value, dict) or set(value) != {"reasoning", "context_window"}:
                    raise _invalid("essential_settings")
                selected = await asyncio.to_thread(self._selected, profile_id)
                selected_config = selected["config"]
                selected_revision = selected["revision"]
                if not isinstance(selected_config, dict) or type(selected_revision) is not int:
                    raise SetupError(code="setup.failed", message_key="error.setup.failed")
                current = dict(selected_config)
                current["reasoning"] = value["reasoning"]
                current["context_window"] = value["context_window"]
                try:
                    config = ModelRuntimeConfig.from_mapping(current)
                except JarvisError as error:
                    raise _invalid("essential_settings") from error
                await asyncio.to_thread(
                    self._models.update_config,
                    profile_id,
                    ModelId.parse(str(selected["model_id"])),
                    config,
                    selected_revision,
                )
                session.essential_settings_pending = False
            else:
                raise _invalid("action")
            session.revision += 1
            return await self._snapshot(session)

    async def validate(
        self, profile_id: ProfileId, token: str, expected_revision: int
    ) -> dict[str, object]:
        async with self._lock:
            session = self._require(profile_id, token, expected_revision)
            self._require_live(session)
            state = await self._state(session)
            if state not in {SetupState.VALIDATING, SetupState.READY}:
                raise SetupError(
                    code="setup.not_ready",
                    message_key="error.setup.not_ready",
                    safe_details={"state": state.value},
                )
            try:
                status = await self._runtimes.status(profile_id)
                if status.state is not RuntimeState.READY:
                    await self._runtimes.start(profile_id)
                status = await self._runtimes.status(profile_id)
            except RuntimeManagerError as error:
                session.terminal_state = SetupState.FAILED
                session.revision += 1
                raise SetupError(
                    code="setup.runtime_validation_failed",
                    message_key="error.setup.runtime_validation_failed",
                    safe_details={"reason": error.code},
                ) from error
            if (
                status.state is not RuntimeState.READY
                or status.health is not RuntimeHealthClass.HEALTHY
            ):
                session.terminal_state = SetupState.FAILED
                session.revision += 1
                raise SetupError(
                    code="setup.runtime_validation_failed",
                    message_key="error.setup.runtime_validation_failed",
                )
            session.terminal_state = SetupState.READY
            session.revision += 1
            return await self._snapshot(session)

    async def cancel(
        self, profile_id: ProfileId, token: str, expected_revision: int
    ) -> dict[str, object]:
        async with self._lock:
            session = self._require(profile_id, token, expected_revision)
            self._require_live(session)
            session.terminal_state = SetupState.CANCELLED
            session.revision += 1
            return await self._snapshot(session)

    def _require(self, profile_id: ProfileId, token: str, revision: int) -> _Session:
        session = self._sessions.get(token)
        if session is None:
            raise SetupError(code="setup.core_restarted", message_key="error.setup.core_restarted")
        if session.profile_id != profile_id:
            raise SetupError(
                code="setup.invalid_session", message_key="error.setup.invalid_session"
            )
        if session.revision != revision:
            raise SetupError(
                code="setup.revision_conflict", message_key="error.setup.revision_conflict"
            )
        return session

    @staticmethod
    def _require_live(session: _Session) -> None:
        if session.terminal_state is None:
            return
        code = (
            "setup.cancelled"
            if session.terminal_state is SetupState.CANCELLED
            else "setup.completed"
            if session.terminal_state is SetupState.READY
            else "setup.failed"
        )
        raise SetupError(code=code, message_key=f"error.{code}")

    async def _snapshot(self, session: _Session) -> dict[str, object]:
        location = await asyncio.to_thread(self._models.runtime_location)
        models = await asyncio.to_thread(self._models.list)
        associations = await asyncio.to_thread(self._models.associations, session.profile_id)
        state = await self._state(session)
        return {
            "session_token": session.token,
            "revision": session.revision,
            "profile_id": str(session.profile_id),
            "state": state.value,
            "runtime_path": (
                None if location.llama_server_path is None else str(location.llama_server_path)
            ),
            "model_directories": [str(path) for path in location.model_directories],
            "models": [
                {
                    "model_id": str(record.model_id),
                    "path": str(record.canonical_path),
                    "size_bytes": record.size_bytes,
                    "availability": record.availability.value,
                }
                for record in models
            ],
            "associations": [_association_wire(item) for item in associations],
        }

    async def _state(self, session: _Session) -> SetupState:
        if session.terminal_state is not None:
            return session.terminal_state
        location = await asyncio.to_thread(self._models.runtime_location)
        if location.llama_server_path is None:
            return SetupState.NEEDS_RUNTIME_PATH
        if not location.model_directories:
            return SetupState.NEEDS_MODEL_DIRECTORY
        models = await asyncio.to_thread(self._models.list)
        available = [item for item in models if item.availability is ModelAvailability.AVAILABLE]
        if not session.discovery_attempted and not available:
            return SetupState.NEEDS_DISCOVERY
        associations = await asyncio.to_thread(self._models.associations, session.profile_id)
        selected = [
            item
            for item in associations
            if item.get("selected")
            and item.get("availability") == ModelAvailability.AVAILABLE.value
        ]
        if len(selected) != 1:
            return SetupState.NEEDS_MODEL_SELECTION
        if session.essential_settings_pending:
            return SetupState.NEEDS_ESSENTIAL_SETTINGS
        status = await self._runtimes.status(session.profile_id)
        if status.state is RuntimeState.READY and status.health is RuntimeHealthClass.HEALTHY:
            return SetupState.READY
        return SetupState.VALIDATING

    def _selected(self, profile_id: ProfileId) -> dict[str, object]:
        selected = [item for item in self._models.associations(profile_id) if item.get("selected")]
        if len(selected) != 1:
            raise SetupError(code="setup.missing_model", message_key="error.setup.missing_model")
        return selected[0]


def _invalid(field: str) -> SetupError:
    return SetupError(
        code="setup.invalid_input",
        message_key="error.setup.invalid_input",
        safe_details={"field": field},
    )


def _association_wire(item: dict[str, object]) -> dict[str, object]:
    config = item.get("config")
    return {
        "model_id": item["model_id"],
        "revision": item["revision"],
        "selected": item["selected"],
        "availability": item["availability"],
        "reasoning": config.get("reasoning") if isinstance(config, dict) else None,
        "context_window": config.get("context_window") if isinstance(config, dict) else None,
    }
