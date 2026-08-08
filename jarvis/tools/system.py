from __future__ import annotations

import platform
import os
from pathlib import Path
import re
from typing import Any


def get_current_directory() -> dict[str, Any]:
    return {"path": str(Path.cwd())}


def get_user_directories() -> dict[str, Any]:
    home = Path.home().resolve()
    candidates: dict[str, list[str]] = {
        "documents": [str(home / "Documents"), str(home / "Documentos")],
        "downloads": [str(home / "Downloads")],
        "desktop": [str(home / "Desktop"), str(home / "Área de Trabalho")],
        "music": [str(home / "Music"), str(home / "Música")],
        "pictures": [str(home / "Pictures"), str(home / "Imagens")],
        "videos": [str(home / "Videos"), str(home / "Vídeos")],
    }
    config_file = user_directories_config_path()
    try:
        for raw_line in config_file.read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r'XDG_([A-Z]+)_DIR="(.*)"', raw_line.strip())
            if not match:
                continue
            raw_key = match.group(1).lower()
            key = {
                "document": "documents",
                "download": "downloads",
                "picture": "pictures",
                "video": "videos",
                "template": "templates",
                "publicshare": "publicshare",
            }.get(raw_key, raw_key)
            value = match.group(2).replace("${HOME}", str(home)).replace("$HOME", str(home))
            path = Path(value).expanduser()
            if path.is_absolute():
                resolved = str(path.resolve(strict=False))
                candidates.setdefault(key, [])
                candidates[key] = [resolved, *[item for item in candidates[key] if item != resolved]]
    except (OSError, UnicodeError):
        pass
    return {"home": str(home), "directories": candidates}


def user_directories_config_path() -> Path:
    home = Path.home().resolve()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")).expanduser()
    return (config_home / "user-dirs.dirs").resolve(strict=False)


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
