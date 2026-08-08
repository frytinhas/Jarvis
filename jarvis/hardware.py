from __future__ import annotations

from pathlib import Path
import subprocess


DEFAULT_CONTEXT_SIZE = 4096
CONTEXT_SIZE_STEP = 1024


def detect_vram_mib() -> int | None:
    """Return the largest locally detectable GPU VRAM capacity in MiB."""
    capacities = [*_nvidia_vram_mib(), *_drm_vram_mib()]
    return max(capacities, default=None)


def recommended_context_size(vram_mib: int | None = None) -> int:
    """Reserve half of one GPU's VRAM capacity for the llama.cpp context."""
    if vram_mib is None:
        vram_mib = detect_vram_mib()
    if vram_mib is None or vram_mib <= 0:
        return DEFAULT_CONTEXT_SIZE
    half_vram = vram_mib / 2
    rounded = int((half_vram + (CONTEXT_SIZE_STEP / 2)) // CONTEXT_SIZE_STEP)
    return max(CONTEXT_SIZE_STEP, rounded * CONTEXT_SIZE_STEP)


def _nvidia_vram_mib() -> list[int]:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    capacities: list[int] = []
    for line in completed.stdout.splitlines():
        try:
            capacity = int(line.strip())
        except ValueError:
            continue
        if capacity > 0:
            capacities.append(capacity)
    return capacities


def _drm_vram_mib() -> list[int]:
    capacities: list[int] = []
    for path in Path("/sys/class/drm").glob("card*/device/mem_info_vram_total"):
        try:
            capacity_bytes = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        capacity_mib = capacity_bytes // (1024 * 1024)
        if capacity_mib > 0:
            capacities.append(capacity_mib)
    return capacities
