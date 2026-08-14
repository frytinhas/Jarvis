from __future__ import annotations

import pytest

from jarvis.core.lifecycle import CoreLifecycle, CoreLifecycleState
from jarvis.ipc.errors import IpcError

pytestmark = pytest.mark.unit


def test_lifecycle_accepts_only_documented_transitions() -> None:
    lifecycle = CoreLifecycle()
    assert lifecycle.state is CoreLifecycleState.STARTING
    lifecycle.transition(CoreLifecycleState.READY)
    lifecycle.transition(CoreLifecycleState.STOPPING)
    lifecycle.transition(CoreLifecycleState.STOPPED)
    with pytest.raises(IpcError):
        lifecycle.transition(CoreLifecycleState.READY)


def test_error_path_can_stop_cleanly() -> None:
    lifecycle = CoreLifecycle()
    lifecycle.transition(CoreLifecycleState.ERROR)
    lifecycle.transition(CoreLifecycleState.STOPPING)
    lifecycle.transition(CoreLifecycleState.STOPPED)
