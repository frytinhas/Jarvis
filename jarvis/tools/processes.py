from __future__ import annotations

from pathlib import Path
import os
import signal
import subprocess
import tempfile
from typing import Any

from jarvis.security.validator import PathValidationError, resolve_path, validate_execute_path


MAX_PROCESS_OUTPUT_BYTES = 65_536
_BLOCKED_EXECUTABLES = {"sudo", "su", "pkexec", "doas", "dd", "mount", "umount"}
_INTERPRETERS = {
    "bash", "sh", "dash", "zsh", "fish", "python", "python3", "perl", "ruby", "node",
}


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


def execute_file(
    path: str,
    arguments: list[str] | None = None,
    working_directory: str | None = None,
    background: bool = False,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    target = validate_execute_path(path)
    args = list(arguments or [])
    _validate_execution_arguments(target, args)
    cwd = resolve_path(working_directory) if working_directory else Path.cwd().resolve()
    if not cwd.is_dir():
        raise NotADirectoryError(str(cwd))
    command = (["/bin/bash", "--", str(target), *args]
               if target.suffix.lower() == ".sh" else [str(target), *args])
    if background:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            start_new_session=True,
        )
        return {"path": str(target), "pid": process.pid, "background": True}

    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            shell=False,
            start_new_session=True,
        )
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            _terminate_process_group(process)
            return {
                "path": str(target),
                "background": False,
                "timed_out": True,
                "timeout_seconds": timeout_seconds,
                "stdout": _read_limited(stdout),
                "stderr": _read_limited(stderr),
            }
        except KeyboardInterrupt:
            _terminate_process_group(process)
            raise
        return {
            "path": str(target),
            "background": False,
            "timed_out": False,
            "exit_code": process.returncode,
            "stdout": _read_limited(stdout),
            "stderr": _read_limited(stderr),
        }


def _read_limited(stream: Any) -> str:
    stream.seek(0)
    payload = stream.read(MAX_PROCESS_OUTPUT_BYTES + 1)
    text = payload[:MAX_PROCESS_OUTPUT_BYTES].decode("utf-8", errors="replace")
    return text + ("\n[saída truncada]" if len(payload) > MAX_PROCESS_OUTPUT_BYTES else "")


def _terminate_process_group(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=1)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def _validate_execution_arguments(target: Path, arguments: list[str]) -> None:
    name = target.name.lower()
    if name in _BLOCKED_EXECUTABLES or name.startswith("mkfs"):
        raise PathValidationError(f"Executável bloqueado: {name}")
    if name in _INTERPRETERS and any(argument in {"-c", "-e", "--eval"} for argument in arguments):
        raise PathValidationError("Código inline em interpretadores é bloqueado")
    if name == "rm":
        recursive = any(argument in {"-r", "-R", "--recursive", "-rf", "-fr"} for argument in arguments)
        targets_root = any(argument == "/" or argument.startswith("--no-preserve-root") for argument in arguments)
        if recursive and targets_root:
            raise PathValidationError("Remoção recursiva da raiz é bloqueada")
    if name in {"chmod", "chown"} and any(argument in {"-R", "--recursive"} for argument in arguments):
        protected = {"/", "/boot", "/dev", "/etc", "/proc", "/sys", "/usr", "/var/lib"}
        if any(argument in protected for argument in arguments):
            raise PathValidationError("Alteração recursiva em área crítica é bloqueada")
