from __future__ import annotations

from pathlib import Path
from typing import Any


def get_processes() -> dict[str, Any]:
    processes: list[dict[str, Any]] = []
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            name = (entry / "comm").read_text(encoding="utf-8").strip()
            status = (entry / "status").read_text(encoding="utf-8")
            uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
            processes.append({"pid": int(entry.name), "name": name, "uid": int(uid_line.split()[1])})
        except (FileNotFoundError, PermissionError, StopIteration, ValueError):
            continue
    processes.sort(key=lambda process: process["pid"])
    return {"processes": processes}

