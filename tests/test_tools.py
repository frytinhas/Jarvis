from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from jarvis.security.validator import PathValidationError, resolve_path, validate_write_path
from jarvis.security.audit import AuditLog
from jarvis.security.confirmation import ConfirmationManager
from jarvis.security.policy import Decision, PolicyEngine, Risk
from jarvis.tools.registry import build_registry
from jarvis.tools.registry import ToolRegistry


def test_read_executes_without_confirmation(registry: ToolRegistry, tmp_path: Path) -> None:
    source = tmp_path / "note.txt"
    source.write_text("olá", encoding="utf-8")
    result = registry.request("read_file", {"path": str(source)})
    assert result.status == "ok"
    assert result.result["content"] == "olá"
    assert result.result["security"].startswith("UNTRUSTED_DATA")


def test_create_executes_without_confirmation_by_default(registry: ToolRegistry, tmp_path: Path) -> None:
    target = tmp_path / "created.txt"
    result = registry.request("create_file", {"path": str(target)})
    assert result.status == "ok"
    assert target.is_file()


def test_create_with_content_uses_create_permission_not_modify(tmp_path: Path) -> None:
    target = tmp_path / "created.sh"
    registry = build_registry(
        PolicyEngine({Risk.CREATE: Decision.ALLOW, Risk.MODIFY: Decision.CONFIRM}),
        ConfirmationManager(),
        AuditLog(tmp_path / "create-content.db"),
    )

    result = registry.request(
        "create_file",
        {"path": str(target), "content": "#!/bin/sh\nprintf created\n"},
    )

    assert result.status == "ok"
    assert result.pending is None
    assert target.read_text(encoding="utf-8") == "#!/bin/sh\nprintf created\n"


@pytest.mark.parametrize(
    ("decision", "expected_status"),
    [(Decision.CONFIRM, "confirmation_required"), (Decision.DENY, "denied")],
)
def test_create_with_content_obeys_restrictive_create_permissions(
    tmp_path: Path, decision: Decision, expected_status: str
) -> None:
    target = tmp_path / f"{decision.value.lower()}.txt"
    registry = build_registry(
        PolicyEngine({Risk.CREATE: decision, Risk.MODIFY: Decision.ALLOW}),
        ConfirmationManager(),
        AuditLog(tmp_path / f"create-{decision.value.lower()}.db"),
    )

    result = registry.request("create_file", {"path": str(target), "content": "content"})

    assert result.status == expected_status
    assert not target.exists()


def test_create_with_content_never_overwrites_existing_file(
    registry: ToolRegistry, tmp_path: Path
) -> None:
    target = tmp_path / "existing.txt"
    target.write_text("original", encoding="utf-8")

    result = registry.request("create_file", {"path": str(target), "content": "replacement"})

    assert result.status == "error"
    assert target.read_text(encoding="utf-8") == "original"


@pytest.mark.parametrize("tool", ["write_file", "append_file"])
def test_modify_tools_do_not_create_missing_files(tmp_path: Path, tool: str) -> None:
    target = tmp_path / "missing.txt"
    registry = build_registry(
        PolicyEngine({Risk.MODIFY: Decision.ALLOW}),
        ConfirmationManager(),
        AuditLog(tmp_path / f"{tool}.db"),
    )

    result = registry.request(tool, {"path": str(target), "content": "content"})

    assert result.status == "error"
    assert not target.exists()


@pytest.mark.parametrize("tool", ["write_file", "delete_file"])
def test_mutation_never_executes_without_confirmation(
    registry: ToolRegistry, tmp_path: Path, tool: str
) -> None:
    target = tmp_path / "note.txt"
    target.write_text("original", encoding="utf-8")
    arguments = {"path": str(target)}
    if tool == "write_file":
        arguments["content"] = "alterado"
    result = registry.request(tool, arguments)
    assert result.status == "confirmation_required"
    assert target.read_text(encoding="utf-8") == "original"


def test_exact_pending_action_executes_after_confirmation(registry: ToolRegistry, tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("original", encoding="utf-8")
    pending = registry.request("write_file", {"path": str(target), "content": "novo"})
    assert pending.pending is not None
    result = registry.confirm(pending.pending.id)
    assert result.status == "ok"
    assert target.read_text(encoding="utf-8") == "novo"


def test_dot_dot_is_normalized(tmp_path: Path) -> None:
    nested = tmp_path / "one" / "two"
    nested.mkdir(parents=True)
    assert resolve_path(str(nested / ".." / "file.txt")) == tmp_path / "one" / "file.txt"


def test_symlink_to_protected_directory_is_blocked(tmp_path: Path) -> None:
    link = tmp_path / "system"
    link.symlink_to("/etc", target_is_directory=True)
    with pytest.raises(PathValidationError, match="protegida"):
        validate_write_path(str(link / "jarvis-test"))


def test_unknown_tool_is_rejected(registry: ToolRegistry) -> None:
    result = registry.request("shell", {})
    assert result.status == "error"
    assert "inexistente" in result.result["error"]


def test_arguments_outside_schema_are_rejected(registry: ToolRegistry, tmp_path: Path) -> None:
    result = registry.request("read_file", {"path": str(tmp_path), "sudo": True})
    assert result.status == "error"
    assert "Argumentos inválidos" in result.result["error"]


def test_protected_path_is_rejected_before_pending_action(registry: ToolRegistry) -> None:
    result = registry.request("write_file", {"path": "/etc/jarvis", "content": "x"})
    assert result.status == "error"
    assert "protegida" in result.result["error"]


def test_tool_calls_are_audited(registry: ToolRegistry, tmp_path: Path) -> None:
    source = tmp_path / "audit-me.txt"
    source.write_text("data", encoding="utf-8")
    assert registry.request("read_file", {"path": str(source)}).status == "ok"

    with sqlite3.connect(registry.audit.path) as connection:
        row = connection.execute(
            "SELECT tool, policy_result, confirmed, executed FROM tool_audit ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row == ("read_file", "ALLOW", 0, 1)


def test_activity_observer_cannot_break_tool_execution(registry: ToolRegistry, tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("ok", encoding="utf-8")

    def broken_observer(event) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("painel falhou")

    registry.activity_observer = broken_observer
    result = registry.request("read_file", {"path": str(source)})

    assert result.status == "ok"


def test_denied_category_is_hidden_and_rejected(tmp_path: Path) -> None:
    restricted = build_registry(
        PolicyEngine({Risk.READ: Decision.DENY}),
        ConfirmationManager(),
        AuditLog(tmp_path / "restricted.db"),
    )
    schema_names = {schema["function"]["name"] for schema in restricted.schemas()}
    assert "read_file" not in schema_names
    result = restricted.request("read_file", {"path": str(tmp_path)})
    assert result.status == "denied"


def test_search_files_is_case_insensitive_by_default(registry: ToolRegistry, tmp_path: Path) -> None:
    vault = tmp_path / "Brain"
    vault.mkdir()

    result = registry.request(
        "search_files",
        {"path": str(tmp_path), "pattern": "*brain*"},
    )

    assert str(vault) in result.result["matches"]


def test_large_file_can_be_read_in_bounded_chunks(registry: ToolRegistry, tmp_path: Path) -> None:
    source = tmp_path / "large.txt"
    source.write_text("abcdefghij", encoding="utf-8")

    first = registry.request("read_file", {"path": str(source), "max_bytes": 4})
    second = registry.request(
        "read_file",
        {"path": str(source), "offset_bytes": first.result["next_offset_bytes"], "max_bytes": 4},
    )

    assert first.result["content"] == "abcd"
    assert first.result["truncated"] is True
    assert second.result["content"] == "efgh"


def test_execute_file_requires_exact_confirmation_when_configured(
    registry: ToolRegistry, tmp_path: Path
) -> None:
    registry.policy.set_decision(Risk.EXECUTE, Decision.CONFIRM)
    script = tmp_path / "hello.sh"
    script.write_text("#!/bin/sh\nprintf 'hello %s' \"$1\"\n", encoding="utf-8")

    requested = registry.request(
        "execute_file",
        {"path": str(script), "arguments": ["Jarvis"]},
    )

    assert requested.status == "confirmation_required"
    assert requested.pending is not None
    completed = registry.confirm(requested.pending.id)
    assert completed.status == "ok"
    assert completed.result["stdout"] == "hello Jarvis"
    assert completed.result["exit_code"] == 0


def test_execute_allow_runs_without_model_authored_confirmation(tmp_path: Path) -> None:
    script = tmp_path / "allowed.sh"
    script.write_text("#!/bin/sh\nprintf allowed\n", encoding="utf-8")
    allowed = build_registry(
        PolicyEngine({Risk.EXECUTE: Decision.ALLOW}),
        ConfirmationManager(),
        AuditLog(tmp_path / "execute-allow.db"),
    )

    result = allowed.request("execute_file", {"path": str(script)})

    assert result.status == "ok"
    assert result.pending is None
    assert result.result["stdout"] == "allowed"


def test_execute_file_blocks_inline_shell_code(tmp_path: Path) -> None:
    allowed = build_registry(
        PolicyEngine({Risk.EXECUTE: Decision.ALLOW}),
        ConfirmationManager(),
        AuditLog(tmp_path / "execute-block.db"),
    )

    result = allowed.request(
        "execute_file",
        {"path": "/bin/bash", "arguments": ["-c", "touch /tmp/should-not-run"]},
    )

    assert result.status == "error"
    assert "inline" in result.result["error"]
