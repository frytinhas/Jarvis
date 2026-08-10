from __future__ import annotations

import json
from pathlib import Path

from jarvis.debug_log import SessionDebugLog
from jarvis.settings import UserSettings


def test_debug_log_is_private_redacts_secrets_and_uses_jsonl(tmp_path: Path) -> None:
    log = SessionDebugLog(tmp_path / "logs/debug", 200, 30)
    log.record("llm_request", payload={"api_key": "do-not-store", "messages": [{"content": "password=hidden"}]})
    log.close("completed")

    assert log.path.stat().st_mode & 0o777 == 0o600
    rows = [json.loads(line) for line in log.path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["payload"]["api_key"] == "[redacted]"
    assert "hidden" not in json.dumps(rows)
    assert rows[-1]["event"] == "session_end"


def test_default_log_size_is_200_mb() -> None:
    assert UserSettings().log_max_size_mb == 200
