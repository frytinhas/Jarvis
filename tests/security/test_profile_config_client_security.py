from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.core.runtime import JarvisCore
from jarvis.ipc.models import PROFILE_MANAGEMENT
from jarvis.storage.xdg import resolve_xdg_paths
from tests.support.ipc_client import RawTestClient

pytestmark = pytest.mark.security

CLIENT_ROOT = Path("src/jarvis/cli")
MANAGEMENT_CLIENT_ROOT = Path("src/jarvis/manage")


def test_configuration_client_has_no_persistence_host_or_later_milestone_imports() -> None:
    forbidden = {
        "sqlite3",
        "subprocess",
        "socket",
        "jarvis.storage.database",
        "jarvis.profiles.repository",
        "jarvis.profiles.service",
        "jarvis.models",
        "jarvis.tools",
        "jarvis.policy",
        "jarvis.chat",
        "jarvis.runtime",
    }
    imported: set[str] = set()
    for path in CLIENT_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
    assert not any(
        name == blocked or name.startswith(f"{blocked}.")
        for name in imported
        for blocked in forbidden
    )


def test_management_client_has_no_repository_database_or_model_service_imports() -> None:
    forbidden = {
        "sqlite3",
        "jarvis.storage.database",
        "jarvis.models",
        "jarvis.profiles.repository",
        "jarvis.profiles.service",
    }
    imported: set[str] = set()
    for path in MANAGEMENT_CLIENT_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
    assert not any(
        name == blocked or name.startswith(f"{blocked}.")
        for name in imported
        for blocked in forbidden
    )


def test_m006b_contains_no_launcher_path_or_physical_alias_implementation() -> None:
    project = Path("src/jarvis")
    names = {path.name for path in project.rglob("*")}
    assert not names.intersection(
        {"launchers", "launcher_registry.py", "profile_commands.py", "aliases.json"}
    )
    client_source = "\n".join(path.read_text(encoding="utf-8") for path in CLIENT_ROOT.glob("*.py"))
    assert "PATH" not in client_source
    assert "symlink" not in client_source
    assert "chmod" not in client_source
    assert "~/.local/bin" not in client_source
    assert "installation.runtime" not in client_source
    assert "models.refresh" not in client_source


def test_only_approved_m006b_console_scripts_exist() -> None:
    import tomllib

    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["scripts"] == {
        "jarvisd": "jarvis.core.__main__:main",
        "jarvis-config": "jarvis.cli.__main__:config_main",
        "jarvis-help": "jarvis.cli.__main__:help_main",
        "jarvis-manage": "jarvis.manage.__main__:main",
    }


def test_configuration_values_and_confirmation_tokens_never_enter_diagnostics() -> None:
    async def run() -> None:
        core = JarvisCore()
        task = asyncio.create_task(core.run())
        paths = resolve_xdg_paths()
        for _ in range(200):
            if (paths.runtime / "core.sock").exists():
                break
            await asyncio.sleep(0.005)
        client = await RawTestClient.connect(
            paths.runtime / "core.sock", optional_capabilities=(PROFILE_MANAGEMENT,)
        )
        private_value = "PRIVATE-PERSONA-M003-DO-NOT-LOG"
        try:
            created = await client.request(
                request_id=str(uuid4()),
                operation="profiles.create",
                payload={"display_name": "Private"},
            )
            profile = created[-1]["payload"]["profile"]
            snapshot = await client.request(
                request_id=str(uuid4()),
                operation="profiles.configuration.section.get",
                profile_id=profile["profile_id"],
                payload={"section": "persona"},
            )
            revisions = snapshot[-1]["payload"]
            await client.request(
                request_id=str(uuid4()),
                operation="profiles.configuration.section.update",
                profile_id=profile["profile_id"],
                payload={
                    "section": "persona",
                    "value": private_value,
                    "expected_identity_revision": revisions["identity_revision"],
                    "expected_configuration_revision": revisions["configuration_revision"],
                },
            )
            preview = await client.request(
                request_id=str(uuid4()),
                operation="profiles.reset.preview",
                profile_id=profile["profile_id"],
                payload={"scope": "persona"},
            )
            token = preview[-1]["payload"]["preview"]["confirmation_token"]
        finally:
            await client.close()
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)
        persisted = b"".join(
            path.read_bytes() for path in (paths.state / "diagnostics").iterdir()
        ).decode("utf-8")
        assert private_value not in persisted
        assert token not in persisted
        assert "Private" not in persisted

    asyncio.run(run())
