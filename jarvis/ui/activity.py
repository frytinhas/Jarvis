from __future__ import annotations

from dataclasses import dataclass, field
import difflib
import json
import os
from pathlib import Path
import sys
import time
from collections.abc import Callable
from typing import Any, TextIO

from jarvis.settings import DisplayLogLevel
from jarvis.tools.registry import ToolActivity
from jarvis.ui.theme import PLAIN_THEME, Theme


_CONTENT_TOOLS = {"write_file", "append_file"}


def maintain_runtime_logs(directory: Path, max_size_mb: int, retention_days: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    files = [path for path in directory.iterdir() if path.is_file() and not path.is_symlink()]
    if retention_days > 0:
        cutoff = time.time() - retention_days * 86400
        for path in files:
            if path.name.startswith("session-") and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        files = [path for path in directory.iterdir() if path.is_file() and not path.is_symlink()]
    if max_size_mb <= 0:
        return
    maximum = max_size_mb * 1024 * 1024
    sessions = sorted(
        (path for path in files if path.name.startswith("session-")),
        key=lambda path: path.stat().st_mtime,
    )
    total = sum(path.stat().st_size for path in files)
    while total > maximum and sessions:
        oldest = sessions.pop(0)
        size = oldest.stat().st_size
        oldest.unlink(missing_ok=True)
        total -= size
    server_log = directory / "llama-server.log"
    if total > maximum and server_log.is_file():
        server_log.write_text("", encoding="utf-8")
        server_log.chmod(0o600)


@dataclass
class ActivityPanel:
    level: DisplayLogLevel
    stream: TextIO = sys.stdout
    log_path: Path | None = None
    theme: Theme = PLAIN_THEME
    interaction_timeout_seconds: float = 600.0
    clock: Callable[[], float] = time.monotonic
    total_seconds: Callable[[], float] = lambda: 0.0
    _before: dict[tuple[str, str], str] = field(default_factory=dict)
    _metadata: dict[tuple[str, str], str] = field(default_factory=dict)
    _started: dict[tuple[str, str], float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.log_path is None:
            configured = os.environ.get("JARVIS_SESSION_LOG_PATH", "").strip()
            self.log_path = Path(configured) if configured else None
        if self.log_path is not None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_path.touch(mode=0o600, exist_ok=True)
            self.log_path.chmod(0o600)

    def __call__(self, event: ToolActivity) -> None:
        if self.level is DisplayLogLevel.NONE:
            return
        if event.phase == "running":
            self._capture_before(event)
            self._started[self._event_key(event)] = self.clock()
        lines = self._format(event)
        if not lines:
            return
        payload = "\n".join(lines)
        self._write_file(payload)
        print(f"\n{self._styled(lines)}", file=self.stream, flush=True)

    def technical(self, message: str) -> None:
        if self.level is not DisplayLogLevel.FULL:
            return
        self._write_file(message)
        print(message, file=self.stream, flush=True)

    def _format(self, event: ToolActivity) -> list[str]:
        icon = {
            "running": "▶",
            "pending": "?",
            "finished": "✓" if event.status == "ok" else "!",
        }.get(event.phase, "•")
        target = self._target(event.arguments)
        headline = f"{icon} {event.tool}{f' — {target}' if target else ''}"
        timing = self._timing(event)
        if timing is not None and self.level is not DisplayLogLevel.MINIMAL_ESSENTIAL:
            headline += f" ({self._seconds(timing)}/{self._seconds(self.interaction_timeout_seconds)})"
        if event.phase == "finished" and event.status:
            headline += f" [{event.status}]"
        if self.level is DisplayLogLevel.MINIMAL_ESSENTIAL:
            return [headline]
        if self.level in {DisplayLogLevel.ESSENTIAL, DisplayLogLevel.SERVER_ESSENTIAL}:
            return [headline, *self._total_line(event, timing), *self._essential_details(event)]
        details = json.dumps(
            {"arguments": event.arguments, "result": event.result},
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        return [headline, *self._total_line(event, timing), details]

    def _timing(self, event: ToolActivity) -> float | None:
        if event.phase != "finished":
            return None
        started = self._started.pop(self._event_key(event), None)
        return max(0.0, self.clock() - started) if started is not None else None

    def _total_line(self, event: ToolActivity, duration: float | None) -> list[str]:
        if duration is None or self.level is DisplayLogLevel.MINIMAL_ESSENTIAL:
            return []
        total = max(0.0, self.total_seconds()) + duration
        return [f"  total — {self._seconds(total)}/{self._seconds(self.interaction_timeout_seconds)}"]

    @staticmethod
    def _seconds(value: float) -> str:
        if value < 1:
            return "<1s"
        return f"{round(value):d}s"

    @classmethod
    def _event_key(cls, event: ToolActivity) -> tuple[str, str]:
        return event.tool, cls._target(event.arguments)

    def _styled(self, lines: list[str]) -> str:
        styled: list[str] = []
        for line in lines:
            if line.lstrip().startswith("total —") or "s/" in line and line.rstrip().endswith(")"):
                styled.append(self.theme.paint(line, "timer"))
            elif line.startswith("✓"):
                styled.append(self.theme.paint(line, "success"))
            elif line.startswith("!"):
                styled.append(self.theme.paint(line, "error"))
            elif line.startswith("?"):
                styled.append(self.theme.paint(line, "warning"))
            elif line.startswith("▶"):
                styled.append(self.theme.paint(line, "tool"))
            else:
                styled.append(line)
        return "\n".join(styled)

    def _essential_details(self, event: ToolActivity) -> list[str]:
        if event.phase != "running":
            if event.status == "error" and event.result:
                return [f"  erro: {event.result.get('error', 'falha na tool')}"]
            if event.status == "ok" and event.result:
                if event.tool == "read_file":
                    size = len(str(event.result.get("content", "")).encode("utf-8"))
                    return [f"  leitura concluída: {size} bytes"]
                if event.tool == "list_directory":
                    return [f"  itens encontrados: {len(event.result.get('entries', []))}"]
                if event.tool == "search_files":
                    return [f"  resultados encontrados: {len(event.result.get('matches', []))}"]
                if event.tool == "file_info" and "size" in event.result:
                    return [f"  tamanho: {event.result['size']} bytes"]
            return []
        arguments = event.arguments
        if event.tool == "write_file":
            path = str(arguments.get("path", ""))
            before = self._before.get((event.tool, path), "")
            after = str(arguments.get("content", ""))
            diff = difflib.unified_diff(
                before.splitlines(), after.splitlines(),
                fromfile=f"{path} (antes)", tofile=f"{path} (depois)", lineterm="",
            )
            return [f"  {line}" for line in diff]
        if event.tool == "append_file":
            content = str(arguments.get("content", ""))
            return ["  conteúdo acrescentado:", *[f"  + {line}" for line in content.splitlines()]]
        if event.tool == "create_file":
            content = str(arguments.get("content", ""))
            if not content:
                return ["  conteúdo criado: arquivo vazio"]
            return ["  conteúdo criado:", *[f"  + {line}" for line in content.splitlines()]]
        if event.tool in {"move_file", "rename_file"}:
            return [f"  origem: {arguments.get('source', arguments.get('path', ''))}",
                    f"  destino: {arguments.get('destination', arguments.get('new_name', ''))}"]
        if event.tool in {"delete_file", "delete_directory"}:
            metadata = self._metadata.get((event.tool, str(arguments.get("path", ""))))
            return [f"  alvo: {metadata}"] if metadata else []
        visible = {
            key: value for key, value in arguments.items()
            if key not in {"content", "path", "source", "destination"}
        }
        return [f"  parâmetros: {json.dumps(visible, ensure_ascii=False, default=str)}"] if visible else []

    def _capture_before(self, event: ToolActivity) -> None:
        if event.tool in {"delete_file", "delete_directory"}:
            path = Path(str(event.arguments.get("path", "")))
            try:
                stat = path.stat()
                kind = "diretório" if path.is_dir() else "arquivo"
                self._metadata[(event.tool, str(path))] = f"{path} ({kind}, {stat.st_size} bytes)"
            except OSError:
                pass
        if event.tool not in _CONTENT_TOOLS:
            return
        path = str(event.arguments.get("path", ""))
        if not path:
            return
        try:
            self._before[(event.tool, path)] = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            self._before[(event.tool, path)] = ""

    @staticmethod
    def _target(arguments: dict[str, Any]) -> str:
        if "path" in arguments:
            return str(arguments["path"])
        if "source" in arguments and "destination" in arguments:
            return f"{arguments['source']} → {arguments['destination']}"
        return ""

    def _write_file(self, payload: str) -> None:
        if self.log_path is None:
            return
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(payload + "\n")
