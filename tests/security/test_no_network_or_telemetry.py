from __future__ import annotations

import ast
import importlib
import pkgutil
import socket
import tomllib
from pathlib import Path

import pytest

import jarvis

pytestmark = pytest.mark.security

_BANNED_IMPORTS = {
    "httpx",
    "requests",
    "urllib.request",
    "aiohttp",
    "sentry_sdk",
    "opentelemetry",
    "posthog",
    "segment",
}
_BANNED_INTEGRATION_WORDS = {
    "sentry_sdk",
    "crash-report upload",
    "remote configuration client",
    "analytics sdk",
}


def test_project_has_zero_runtime_dependencies() -> None:
    document = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert document["project"]["dependencies"] == []
    assert document["project"]["scripts"] == {
        "jarvisd": "jarvis.core.__main__:main",
        "jarvis-config": "jarvis.cli.__main__:main",
        "jarvis-help": "jarvis.cli.__main__:help_main",
        "jarvis-manage": "jarvis.manage.__main__:main",
    }


def test_source_has_no_network_telemetry_or_remote_configuration_integration() -> None:
    for path in Path("src").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module)
        assert not imports.intersection(_BANNED_IMPORTS), path
        lowered = source.casefold()
        assert not any(word in lowered for word in _BANNED_INTEGRATION_WORDS), path


def test_all_foundation_modules_import_while_ipv4_and_ipv6_are_denied() -> None:
    imported = []
    for module in pkgutil.walk_packages(jarvis.__path__, prefix="jarvis."):
        imported.append(importlib.import_module(module.name).__name__)
    assert "jarvis.foundation.bootstrap" in imported

    with pytest.raises(AssertionError, match="must not access"):
        socket.create_connection(("127.0.0.1", 9))
