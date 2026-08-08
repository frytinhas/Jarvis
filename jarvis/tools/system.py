from __future__ import annotations

import platform
import os
from pathlib import Path
import re
import shutil
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
    cpuinfo = _read_text(Path("/proc/cpuinfo"))
    cpu_model = _first_cpu_value(cpuinfo, ("model name", "Hardware", "Processor"))
    logical_cpus = _processor_count(cpuinfo)
    physical_cores = _physical_core_count(cpuinfo)
    os_release = _parse_os_release(_read_text(Path("/etc/os-release")))
    total_bytes = memory.get("MemTotal")
    available_bytes = memory.get("MemAvailable")
    root_usage = shutil.disk_usage("/")
    gpus = _gpu_devices()
    result = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": logical_cpus,
        "memory_bytes": memory,
        "os": {
            "name": os_release.get("NAME", platform.system()),
            "version": os_release.get("VERSION_ID", ""),
            "pretty_name": os_release.get("PRETTY_NAME", platform.system()),
            "kernel": platform.release(),
            "architecture": platform.machine(),
        },
        "cpu": {
            "model": cpu_model or "não identificado",
            "physical_cores": physical_cores,
            "logical_cpus": logical_cpus,
        },
        "memory": {
            "total_bytes": total_bytes,
            "available_bytes": available_bytes,
            "total_gib": round(total_bytes / (1024**3), 2) if total_bytes else None,
            "available_gib": round(available_bytes / (1024**3), 2) if available_bytes else None,
        },
        "gpus": gpus,
        "storage": {
            "root": {
                "total_bytes": root_usage.total,
                "used_bytes": root_usage.used,
                "free_bytes": root_usage.free,
            }
        },
    }
    if any(gpu.get("ambiguous_model") for gpu in gpus):
        result["hardware_note"] = (
            "Um ou mais IDs PCI representam uma família de GPUs; não escolha um SKU exato sem outra fonte."
        )
    return result


def _cpu_count() -> int:
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text(encoding="utf-8")
        count = sum(1 for line in cpuinfo.splitlines() if line.startswith("processor"))
        return max(count, 1)
    except FileNotFoundError:
        return 1


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _parse_os_release(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"').strip("'")
    return values


def _first_cpu_value(text: str, keys: tuple[str, ...]) -> str | None:
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip() in keys and value.strip():
            return value.strip()
    return None


def _processor_count(text: str) -> int:
    count = sum(1 for line in text.splitlines() if line.split(":", 1)[0].strip() == "processor")
    return count or _cpu_count()


def _physical_core_count(text: str) -> int | None:
    cores: set[tuple[str, str]] = set()
    block: dict[str, str] = {}
    for line in [*text.splitlines(), ""]:
        if line.strip() and ":" in line:
            key, value = line.split(":", 1)
            block[key.strip()] = value.strip()
            continue
        if "physical id" in block and "core id" in block:
            cores.add((block["physical id"], block["core id"]))
        block = {}
    return len(cores) or None


def _gpu_devices() -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    pci_text = ""
    for candidate in (Path("/usr/share/hwdata/pci.ids"), Path("/usr/share/misc/pci.ids")):
        pci_text = _read_text(candidate)
        if pci_text:
            break
    for device_path in sorted(Path("/sys/bus/pci/devices").glob("*")):
        class_id = _read_text(device_path / "class").strip().lower()
        if not class_id.startswith("0x03"):
            continue
        vendor_id = _read_text(device_path / "vendor").strip().lower().removeprefix("0x")
        device_id = _read_text(device_path / "device").strip().lower().removeprefix("0x")
        subsystem_vendor = _read_text(device_path / "subsystem_vendor").strip().lower().removeprefix("0x")
        subsystem_device = _read_text(device_path / "subsystem_device").strip().lower().removeprefix("0x")
        vendor_name, model_name, exact_subsystem = _parse_pci_ids(
            pci_text,
            vendor_id,
            device_id,
            subsystem_vendor,
            subsystem_device,
        )
        try:
            driver = (device_path / "driver").resolve(strict=True).name
        except OSError:
            driver = ""
        ambiguous = not exact_subsystem and bool(re.search(r"[/]|\bor\b", model_name, re.IGNORECASE))
        devices.append({
            "name": model_name or "GPU não identificada",
            "vendor": vendor_name or vendor_id,
            "driver": driver,
            "pci_address": device_path.name,
            "pci_id": f"{vendor_id}:{device_id}",
            "subsystem_id": f"{subsystem_vendor}:{subsystem_device}",
            "ambiguous_model": ambiguous,
        })
    return devices


def _parse_pci_ids(
    text: str,
    vendor_id: str,
    device_id: str,
    subsystem_vendor: str = "",
    subsystem_device: str = "",
) -> tuple[str, str, bool]:
    current_vendor = ""
    current_device = ""
    vendor_name = ""
    device_name = ""
    subsystem_name = ""
    for line in text.splitlines():
        vendor_match = re.fullmatch(r"([0-9a-fA-F]{4})  (.+)", line)
        if vendor_match:
            current_vendor = vendor_match.group(1).lower()
            current_device = ""
            if current_vendor == vendor_id:
                vendor_name = vendor_match.group(2).strip()
            elif vendor_name:
                break
            continue
        if current_vendor != vendor_id:
            continue
        device_match = re.fullmatch(r"\t([0-9a-fA-F]{4})  (.+)", line)
        if device_match:
            current_device = device_match.group(1).lower()
            if current_device == device_id:
                device_name = device_match.group(2).strip()
            elif device_name:
                break
            continue
        if current_device == device_id:
            subsystem_match = re.fullmatch(
                r"\t\t([0-9a-fA-F]{4}) ([0-9a-fA-F]{4})  (.+)", line
            )
            if (
                subsystem_match
                and subsystem_match.group(1).lower() == subsystem_vendor
                and subsystem_match.group(2).lower() == subsystem_device
            ):
                subsystem_name = subsystem_match.group(3).strip()
                break
    return vendor_name, subsystem_name or device_name, bool(subsystem_name)
