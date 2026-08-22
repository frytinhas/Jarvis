from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.security


def test_simple_cli_has_no_direct_core_storage_runtime_or_provider_access() -> None:
    root = Path(__file__).parents[2] / "src" / "jarvis" / "cli"
    forbidden = (
        "jarvis.storage.database",
        "jarvis.chat.repository",
        "jarvis.models.repository",
        "jarvis.profiles.repository",
        "jarvis.runtimes.manager",
        "jarvis.llm",
        "sqlite3",
    )
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.append(node.module)
        assert not any(
            imported == blocked or imported.startswith(f"{blocked}.")
            for imported in imports
            for blocked in forbidden
        ), path


def test_diagnostic_summary_objects_cannot_be_submitted_by_cli_api() -> None:
    source = (
        Path(__file__).parents[2] / "src" / "jarvis" / "cli" / "chat_application.py"
    ).read_text(encoding="utf-8")
    assert '"chat.diagnostics.summary"' in source
    assert (
        "diagnostics"
        not in source[source.index("async def submit") : source.index("async def _consume_events")]
    )
