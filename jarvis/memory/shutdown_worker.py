"""Wait for Jarvis-owned memory workers, then stop the managed local server."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import time


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, action="append", default=[])
    parser.add_argument("--launcher", type=Path, required=True)
    parser.add_argument("--timeout", type=int, required=True)
    options = parser.parse_args(arguments)
    deadline = time.monotonic() + max(1, options.timeout)
    while any(_alive(pid) for pid in options.pid) and time.monotonic() < deadline:
        time.sleep(0.2)
    try:
        subprocess.run([str(options.launcher), "--full-stop"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except OSError:
        pass


if __name__ == "__main__":
    main()
