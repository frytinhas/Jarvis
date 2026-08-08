from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
from typing import Any, Callable


class ConfirmationError(ValueError):
    pass


@dataclass(frozen=True)
class PendingAction:
    id: str
    tool_name: str
    arguments: dict[str, Any]
    created_at: datetime
    expires_at: datetime


class ConfirmationManager:
    def __init__(self, timeout_seconds: int = 30, clock: Callable[[], datetime] | None = None) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser positivo")
        self.timeout_seconds = timeout_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._pending: dict[str, PendingAction] = {}

    def create(self, tool_name: str, arguments: dict[str, Any]) -> PendingAction:
        now = self._clock()
        action = PendingAction(
            id=secrets.token_hex(8),
            tool_name=tool_name,
            arguments=deepcopy(arguments),
            created_at=now,
            expires_at=now + timedelta(seconds=self.timeout_seconds),
        )
        self._pending[action.id] = action
        return action

    def consume(
        self,
        action_id: str,
        expected_tool: str | None = None,
        expected_arguments: dict[str, Any] | None = None,
    ) -> PendingAction:
        action = self._pending.get(action_id)
        if action is None:
            raise ConfirmationError("Ação pendente inexistente")
        if self._clock() >= action.expires_at:
            del self._pending[action_id]
            raise ConfirmationError("Confirmação expirada")
        if expected_tool is not None and expected_tool != action.tool_name:
            del self._pending[action_id]
            raise ConfirmationError("A tool foi alterada; confirmação invalidada")
        if expected_arguments is not None and expected_arguments != action.arguments:
            del self._pending[action_id]
            raise ConfirmationError("Os argumentos foram alterados; confirmação invalidada")
        del self._pending[action_id]
        return action

    def cancel(self, action_id: str) -> PendingAction | None:
        return self._pending.pop(action_id, None)

