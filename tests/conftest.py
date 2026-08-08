from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.security.audit import AuditLog
from jarvis.security.confirmation import ConfirmationManager
from jarvis.security.policy import PolicyEngine
from jarvis.tools.registry import ToolRegistry, build_registry


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    return build_registry(
        PolicyEngine(),
        ConfirmationManager(timeout_seconds=30),
        AuditLog(tmp_path / "audit.db"),
    )

