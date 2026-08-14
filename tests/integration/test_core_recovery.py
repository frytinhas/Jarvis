from __future__ import annotations

import os

import pytest

from jarvis.core.lifecycle import CoreLifecycleState
from jarvis.core.runtime import CoreResources

pytestmark = pytest.mark.integration


def test_core_composition_reaches_ready_and_cleans_runtime_artifacts() -> None:
    resources = CoreResources.start()
    socket_path = resources.paths.runtime / "core.sock"
    metadata_path = resources.paths.runtime / "core-runtime.json"
    lock_path = resources.paths.runtime / "core.lock"
    try:
        assert resources.lifecycle.state is CoreLifecycleState.READY
        assert socket_path.is_socket()
        assert socket_path.stat().st_mode & 0o777 == 0o600
        assert metadata_path.stat().st_mode & 0o777 == 0o600
        assert resources.profiles.list_profiles()[0].profile.command_alias == "jarvis"
    finally:
        resources.close()
    assert resources.lifecycle.state.value == "STOPPED"
    assert not socket_path.exists()
    assert not metadata_path.exists()
    assert lock_path.is_file()
    assert lock_path.stat().st_uid == os.getuid()


def test_clean_restart_gets_a_new_core_instance() -> None:
    first = CoreResources.start()
    first_id = first.core_instance_id
    first.close()
    second = CoreResources.start()
    try:
        assert second.core_instance_id != first_id
    finally:
        second.close()
