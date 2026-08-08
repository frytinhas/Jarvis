from __future__ import annotations

import platform
from pathlib import Path
from typing import Any


def get_current_directory() -> dict[str, Any]:
    return {"path": str(Path.cwd())}


def get_system_info() -> dict[str, Any]:
    memory: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw_value = line.split(":", 1)
            if key in {"MemTotal", "MemAvailable"}:
                memory[key] = int(raw_value.strip().split()[0]) * 1024
    except (FileNotFoundError, ValueError):
        pass
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": _cpu_count(),
        "memory_bytes": memory,
    }


def _cpu_count() -> int:
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8")
        count = sum(1 for line in cpuinfo.splitlines() if line.startswith("processor"))
        return max(count, 1)
    except FileNotFoundError:
        return 1

