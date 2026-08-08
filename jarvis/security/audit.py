from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


class AuditLog:
    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    arguments TEXT NOT NULL,
                    policy_result TEXT NOT NULL,
                    confirmed INTEGER NOT NULL,
                    executed INTEGER NOT NULL,
                    result TEXT NOT NULL
                )
                """
            )

    def record(
        self,
        *,
        tool: str,
        arguments: dict[str, Any],
        policy_result: str,
        confirmed: bool,
        executed: bool,
        result: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tool_audit
                    (timestamp, tool, arguments, policy_result, confirmed, executed, result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    tool,
                    json.dumps(arguments, ensure_ascii=False, sort_keys=True),
                    policy_result,
                    int(confirmed),
                    int(executed),
                    json.dumps(result, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )

