"""Strict Core lifecycle state machine."""

from __future__ import annotations

import threading
from enum import StrEnum

from jarvis.ipc.errors import ipc_error


class CoreLifecycleState(StrEnum):
    STARTING = "STARTING"
    READY = "READY"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


_TRANSITIONS = {
    CoreLifecycleState.STARTING: {CoreLifecycleState.READY, CoreLifecycleState.ERROR},
    CoreLifecycleState.READY: {CoreLifecycleState.STOPPING, CoreLifecycleState.ERROR},
    CoreLifecycleState.ERROR: {CoreLifecycleState.STOPPING},
    CoreLifecycleState.STOPPING: {CoreLifecycleState.STOPPED},
    CoreLifecycleState.STOPPED: set(),
}


class CoreLifecycle:
    def __init__(self) -> None:
        self._state = CoreLifecycleState.STARTING
        self._lock = threading.Lock()

    @property
    def state(self) -> CoreLifecycleState:
        with self._lock:
            return self._state

    def transition(self, target: CoreLifecycleState) -> None:
        with self._lock:
            if target not in _TRANSITIONS[self._state]:
                raise ipc_error(
                    "ipc.internal_error",
                    reason="illegal_lifecycle_transition",
                    source=self._state.value,
                    target=target.value,
                )
            self._state = target
