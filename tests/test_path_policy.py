from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from jarvis.security.audit import AuditLog
from jarvis.security.confirmation import ConfirmationManager
from jarvis.security.path_policy import PathPolicy, PathPolicyError, parse_path_rules
from jarvis.security.policy import Decision, PolicyEngine, Risk
from jarvis.tools.registry import ToolRegistry, build_registry


def _policy(text: str, project: Path) -> PathPolicy:
    return PathPolicy(parse_path_rules(text), project_directory=project)


def _registry(tmp_path: Path, policy: PathPolicy, decisions: dict[Risk, Decision] | None = None) -> ToolRegistry:
    return build_registry(
        PolicyEngine(decisions),
        ConfirmationManager(),
        AuditLog(tmp_path / "path-policy-audit.db"),
        policy,
    )


def test_short_codes_default_to_deny_and_hyphens_inherit(tmp_path: Path) -> None:
    parent = tmp_path / "tree"
    child = parent / "child"
    policy = _policy(f"{parent} 21\n{child} --2--\n", tmp_path / "project")

    assert policy.decide(Decision.ALLOW, Risk.READ, [child]) is Decision.ALLOW
    assert policy.decide(Decision.ALLOW, Risk.MODIFY, [child]) is Decision.CONFIRM
    assert policy.decide(Decision.ALLOW, Risk.CREATE, [child]) is Decision.ALLOW
    assert policy.decide(Decision.ALLOW, Risk.DELETE, [child]) is Decision.DENY
    assert policy.decide(Decision.ALLOW, Risk.EXECUTE, [child]) is Decision.DENY


def test_later_matching_line_has_priority_even_when_it_is_parent(tmp_path: Path) -> None:
    parent = tmp_path / "tree"
    child = parent / "child"
    policy = _policy(f"{child} 0----\n{parent} 2----\n", tmp_path / "project")

    assert policy.decide(Decision.ALLOW, Risk.READ, [child]) is Decision.ALLOW


def test_path_rule_never_broadens_global_policy(tmp_path: Path) -> None:
    target = tmp_path / "allowed-locally"
    policy = _policy(f"{target} 22222\n", tmp_path / "project")

    assert policy.decide(Decision.CONFIRM, Risk.MODIFY, [target]) is Decision.CONFIRM
    assert policy.decide(Decision.DENY, Risk.READ, [target]) is Decision.DENY


def test_paths_with_spaces_are_supported(tmp_path: Path) -> None:
    target = tmp_path / "folder with spaces"
    rules = parse_path_rules(f"{target} 20000\n")

    assert rules[0].path == target.resolve()


@pytest.mark.parametrize("line", ["relative/path 20000", "/tmp/path 3", "/tmp/path -----"])
def test_invalid_rule_is_rejected(line: str) -> None:
    with pytest.raises(PathPolicyError, match="linha 1"):
        parse_path_rules(line)


def test_missing_blacklist_fails_closed_for_path_tools(tmp_path: Path) -> None:
    policy = PathPolicy.load(tmp_path / "missing.txt", project_directory=tmp_path / "project")
    registry = _registry(tmp_path, policy)

    schema_names = {schema["function"]["name"] for schema in registry.schemas()}
    assert "read_file" not in schema_names
    assert "get_current_directory" in schema_names
    result = registry.request("read_file", {"path": str(tmp_path / "anything")})
    assert result.status == "denied"
    assert "Política de paths inválida" in result.result["error"]


def test_project_directory_is_hardcoded_read_only(tmp_path: Path) -> None:
    project = tmp_path / "jarvis-project"
    project.mkdir()
    target = project / "new.txt"
    registry = _registry(
        tmp_path,
        PathPolicy.empty(project_directory=project),
        {Risk.CREATE: Decision.ALLOW},
    )

    result = registry.request("create_file", {"path": str(target)})

    assert result.status == "denied"
    assert not target.exists()


def test_project_cap_denies_every_non_read_path_risk(tmp_path: Path) -> None:
    project = tmp_path / "jarvis-project"
    target = project / "nested/file.txt"
    policy = _policy(f"{project} 22222\n", project)

    assert policy.decide(Decision.ALLOW, Risk.READ, [target]) is Decision.ALLOW
    for risk in (Risk.MODIFY, Risk.CREATE, Risk.DELETE, Risk.EXECUTE):
        assert policy.decide(Decision.ALLOW, risk, [target]) is Decision.DENY


def test_blacklist_is_a_snapshot_for_the_current_chat(tmp_path: Path) -> None:
    blacklist = tmp_path / "Blacklist.txt"
    target = tmp_path / "files"
    blacklist.write_text(f"{target} 2\n", encoding="utf-8")
    current_chat = PathPolicy.load(blacklist, project_directory=tmp_path / "project")

    blacklist.write_text(f"{target} 0\n", encoding="utf-8")
    next_chat = PathPolicy.load(blacklist, project_directory=tmp_path / "project")

    assert current_chat.decide(Decision.ALLOW, Risk.READ, [target]) is Decision.ALLOW
    assert next_chat.decide(Decision.ALLOW, Risk.READ, [target]) is Decision.DENY


def test_path_rule_can_require_confirmation_but_not_auto_allow(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("old", encoding="utf-8")
    policy = _policy(f"{target} 21\n", tmp_path / "project")
    registry = _registry(tmp_path, policy, {Risk.MODIFY: Decision.ALLOW})

    pending = registry.request("write_file", {"path": str(target), "content": "new"})

    assert pending.status == "confirmation_required"
    assert target.read_text(encoding="utf-8") == "old"
    assert pending.pending is not None
    assert registry.confirm(pending.pending.id).status == "ok"
    assert target.read_text(encoding="utf-8") == "new"


def test_move_uses_most_restrictive_source_or_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "blocked"
    source.mkdir()
    destination.mkdir()
    file = source / "note.txt"
    file.write_text("data", encoding="utf-8")
    policy = _policy(
        f"{source} 22\n{destination} 20\n",
        tmp_path / "project",
    )
    registry = _registry(tmp_path, policy, {Risk.MODIFY: Decision.ALLOW})

    result = registry.request(
        "move_file",
        {"source": str(file), "destination": str(destination)},
    )

    assert result.status == "denied"
    assert file.exists()


def test_recursive_reads_prune_denied_subtrees(tmp_path: Path) -> None:
    root = tmp_path / "files"
    public = root / "public"
    secret = root / "secret"
    public.mkdir(parents=True)
    secret.mkdir()
    (public / "visible.txt").write_text("ok", encoding="utf-8")
    (secret / "hidden.txt").write_text("secret", encoding="utf-8")
    policy = _policy(f"{secret} 0\n", tmp_path / "project")
    registry = _registry(tmp_path, policy)

    listing = registry.request("list_directory", {"path": str(root), "recursive": True})
    search = registry.request("search_files", {"path": str(root), "pattern": "*.txt"})

    listed_paths = {entry["path"] for entry in listing.result["entries"]}
    assert str(public / "visible.txt") in listed_paths
    assert str(secret) not in listed_paths
    assert str(secret / "hidden.txt") not in listed_paths
    assert search.result["matches"] == [str(public / "visible.txt")]


def test_symlink_cannot_bypass_path_rule(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    protected.mkdir()
    secret = protected / "secret.txt"
    secret.write_text("secret", encoding="utf-8")
    link = tmp_path / "shortcut"
    link.symlink_to(protected, target_is_directory=True)
    policy = _policy(f"{protected} 0\n", tmp_path / "project")
    registry = _registry(tmp_path, policy)

    result = registry.request("read_file", {"path": str(link / "secret.txt")})

    assert result.status == "denied"


def test_audit_records_effective_path_decision(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    target.write_text("old", encoding="utf-8")
    policy = _policy(f"{target} 21\n", tmp_path / "project")
    registry = _registry(tmp_path, policy, {Risk.MODIFY: Decision.ALLOW})

    registry.request("write_file", {"path": str(target), "content": "new"})

    with sqlite3.connect(registry.audit.path) as connection:
        policy_result = connection.execute(
            "SELECT policy_result FROM tool_audit ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    assert policy_result == "CONFIRM"
