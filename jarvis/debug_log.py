"""Private, per-profile diagnostic session logs.

This logger is deliberately independent from the interactive display log level.
It records enough context to reproduce a local-model interaction, while removing
credentials and tool/file payloads that could expose private data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import atexit
import hashlib
import json
from pathlib import Path
import re
import uuid
from typing import Any

from jarvis.ui.activity import maintain_runtime_logs


_SECRET_KEY = re.compile(r"(?i)(api[_-]?key|password|senha|token|secret|credential|authorization)")
_SECRET_VALUE = re.compile(
    r"(?i)\b(api[_ -]?key|password|senha|token|secret|credential|authorization)\b(?:\s*[:=]\s*|\s+is\s+|\s+)[^\s,;]+"
)


def sanitize_debug_value(value: Any, *, field: str = "") -> Any:
    """Return a JSON-safe value without diagnostic copies of secrets/content."""
    if _SECRET_KEY.search(field):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(key): sanitize_debug_value(item, field=str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_debug_value(item, field=field) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE.sub(lambda match: f"{match.group(1)}=[redacted]", value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


class SessionDebugLog:
    def __init__(self, directory: Path, max_size_mb: int, retention_days: int) -> None:
        self.directory = directory
        maintain_runtime_logs(directory, max_size_mb, retention_days)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        self.path = directory / f"session-{stamp}-{uuid.uuid4().hex}.jsonl"
        self.path.touch(mode=0o600, exist_ok=False)
        self.path.chmod(0o600)
        self.closed = False
        atexit.register(self.close, "process_exit")

    def record(self, event: str, **payload: Any) -> None:
        if self.closed:
            return
        item = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event}
        item.update(sanitize_debug_value(payload))
        try:
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(item, ensure_ascii=False, default=str, separators=(",", ":")) + "\n")
        except OSError:
            # Diagnostics must never interrupt the assistant.
            return

    def tool_activity(self, activity: Any) -> None:
        arguments = dict(activity.arguments)
        if "content" in arguments:
            content = str(arguments.pop("content"))
            arguments["content_redacted"] = {"bytes": len(content.encode("utf-8")), "sha256": hashlib.sha256(content.encode()).hexdigest()}
        result = activity.result
        # Raw tool output may contain arbitrary local file content. Preserve the
        # result shape and a stable fingerprint without storing that content.
        if isinstance(result, dict) and "content" in result:
            result = dict(result)
            content = str(result.pop("content"))
            result["content_redacted"] = {"bytes": len(content.encode("utf-8")), "sha256": hashlib.sha256(content.encode()).hexdigest()}
        self.record("tool_activity", phase=activity.phase, tool=activity.tool,
                    risk=str(activity.risk) if activity.risk else None,
                    arguments=arguments, status=activity.status, result=result)

    def close(self, outcome: str = "completed") -> None:
        if not self.closed:
            self.record("session_end", outcome=outcome)
            self.closed = True
