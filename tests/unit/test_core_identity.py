from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from jarvis.core.identity import CoreRuntimeIdentity
from jarvis.foundation.clock import format_utc
from jarvis.ipc.models import CoreInstanceId

pytestmark = pytest.mark.unit


def test_current_process_identity_matches_and_metadata_is_informational() -> None:
    identity = CoreRuntimeIdentity.capture(
        CoreInstanceId(uuid4()), started_at_utc=format_utc(datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert identity.matches_live_process()
    metadata = identity.to_metadata(state="STARTING", protocol_version=1, capabilities=[])
    assert metadata["pid"] == identity.pid
    assert "resume_token" not in metadata


def test_stale_start_ticks_do_not_match() -> None:
    identity = CoreRuntimeIdentity.capture(
        CoreInstanceId(uuid4()), started_at_utc="2026-01-01T00:00:00.000000Z"
    )
    forged = CoreRuntimeIdentity(
        core_instance_id=identity.core_instance_id,
        pid=identity.pid,
        boot_id=identity.boot_id,
        process_start_ticks=identity.process_start_ticks + 1,
        executable_device=identity.executable_device,
        executable_inode=identity.executable_inode,
        import_anchor_device=identity.import_anchor_device,
        import_anchor_inode=identity.import_anchor_inode,
        started_at_utc=identity.started_at_utc,
    )
    assert not forged.matches_live_process()
