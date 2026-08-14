"""Linux Core process evidence used for diagnosis, never ownership authority."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import jarvis
from jarvis.ipc.models import CoreInstanceId


def _read_boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()


def _read_start_ticks(pid: int) -> int:
    raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    closing = raw.rfind(")")
    if closing < 0:
        raise ValueError("malformed process stat")
    fields_after_name = raw[closing + 2 :].split()
    return int(fields_after_name[19])


def _identity(path: Path) -> tuple[int, int]:
    metadata = path.stat()
    return metadata.st_dev, metadata.st_ino


@dataclass(frozen=True, slots=True)
class CoreRuntimeIdentity:
    core_instance_id: CoreInstanceId
    pid: int
    boot_id: str
    process_start_ticks: int
    executable_device: int
    executable_inode: int
    import_anchor_device: int
    import_anchor_inode: int
    started_at_utc: str

    @classmethod
    def capture(
        cls,
        core_instance_id: CoreInstanceId,
        *,
        started_at_utc: str,
    ) -> CoreRuntimeIdentity:
        pid = os.getpid()
        executable = _identity(Path("/proc/self/exe"))
        anchor = _identity(Path(jarvis.__file__).resolve(strict=True))
        return cls(
            core_instance_id=core_instance_id,
            pid=pid,
            boot_id=_read_boot_id(),
            process_start_ticks=_read_start_ticks(pid),
            executable_device=executable[0],
            executable_inode=executable[1],
            import_anchor_device=anchor[0],
            import_anchor_inode=anchor[1],
            started_at_utc=started_at_utc,
        )

    def matches_live_process(self) -> bool:
        try:
            if _read_boot_id() != self.boot_id:
                return False
            if _read_start_ticks(self.pid) != self.process_start_ticks:
                return False
            executable = _identity(Path(f"/proc/{self.pid}/exe"))
            return executable == (self.executable_device, self.executable_inode)
        except (OSError, ValueError):
            return False

    def to_metadata(
        self, *, state: str, protocol_version: int, capabilities: list[str]
    ) -> dict[str, object]:
        return {
            "metadata_schema_version": 1,
            "core_instance_id": str(self.core_instance_id),
            "pid": self.pid,
            "boot_id": self.boot_id,
            "process_start_ticks": self.process_start_ticks,
            "executable_device": self.executable_device,
            "executable_inode": self.executable_inode,
            "import_anchor_device": self.import_anchor_device,
            "import_anchor_inode": self.import_anchor_inode,
            "started_at_utc": self.started_at_utc,
            "state": state,
            "socket_filename": "core.sock",
            "protocol_version": protocol_version,
            "capabilities": capabilities,
        }
