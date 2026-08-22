"""Controlled systemd-style inherited-listener M006C acceptance helper."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

from jarvis.ipc.client import JarvisIpcClient
from jarvis.ipc.models import CORE_CONTROL, REQUEST_STREAM

_WRAPPER = """import os
source_fd = int(os.environ.pop('JARVIS_ACTIVATION_FD'))
if source_fd != 3:
    os.dup2(source_fd, 3)
    os.close(source_fd)
os.environ['LISTEN_PID'] = str(os.getpid())
from jarvis.core.__main__ import main
raise SystemExit(main(['--socket-activation']))
"""


async def _run(root: Path) -> None:
    values = {
        "HOME": root / "home",
        "XDG_CONFIG_HOME": root / "config",
        "XDG_DATA_HOME": root / "data",
        "XDG_STATE_HOME": root / "state",
        "XDG_CACHE_HOME": root / "cache",
        "XDG_RUNTIME_DIR": root / "runtime",
    }
    for path in values.values():
        path.mkdir(mode=0o700, parents=True)
    runtime = values["XDG_RUNTIME_DIR"] / "jarvis-cli"
    runtime.mkdir(mode=0o700)
    path = runtime / "core.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    os.chmod(path, 0o600)
    listener.listen(32)
    environment = dict(os.environ)
    environment.update({key: str(value) for key, value in values.items()})
    environment.update(
        {
            "LISTEN_FDS": "1",
            "LISTEN_FDNAMES": "jarvis-core",
            "JARVIS_ACTIVATION_FD": str(listener.fileno()),
        }
    )

    def start() -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [sys.executable, "-c", _WRAPPER],
            env=environment,
            pass_fds=(listener.fileno(),),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    first = start()
    client = await JarvisIpcClient.connect_ready(
        path,
        required_capabilities=(REQUEST_STREAM,),
        optional_capabilities=(CORE_CONTROL,),
    )
    second = start()
    try:
        assert second.wait(timeout=5) == 1
        events = [event async for event in client.request("core.shutdown")]
        assert events[-1]["terminal"] is True
    finally:
        await client.close()
    assert first.wait(timeout=5) == 0
    assert path.exists(), "Core unlinked the systemd-owned listener"
    print("activation=ready duplicate_core=refused inherited_path=preserved")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: manual_m006c_activation.py ROOT")
    asyncio.run(_run(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
