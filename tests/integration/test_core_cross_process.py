from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.ipc.models import CORE_CONTROL
from jarvis.storage.xdg import resolve_xdg_paths
from tests.support.core_process import start_core_process
from tests.support.ipc_client import RawTestClient

pytestmark = pytest.mark.integration


def _wait_ready(process: subprocess.Popen[str], socket_path: Path) -> None:
    for _ in range(400):
        if socket_path.exists():
            return
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"Core exited early: {stdout!r} {stderr!r}")
        time.sleep(0.005)
    raise AssertionError("Core did not become ready")


def test_exactly_one_cross_process_core_and_ready_owner_probe() -> None:
    repository = Path.cwd()
    socket_path = resolve_xdg_paths().runtime / "core.sock"
    first = start_core_process(repository)
    try:
        _wait_ready(first, socket_path)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repository / "src")
        second = subprocess.run(
            [sys.executable, "-m", "jarvis.core", "--foreground"],
            cwd=repository,
            env=env,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        assert second.returncode == 1
        assert "ipc.core_already_running" in second.stderr
        assert first.poll() is None

        async def shutdown() -> None:
            client = await RawTestClient.connect(socket_path, optional_capabilities=(CORE_CONTROL,))
            events = await client.request(request_id=str(uuid4()), operation="core.shutdown")
            assert events[-1]["terminal"] is True

        asyncio.run(shutdown())
        assert first.wait(timeout=5) == 0
        assert not socket_path.exists()
    finally:
        if first.poll() is None:
            first.terminate()
            first.wait(timeout=5)
