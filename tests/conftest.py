from __future__ import annotations

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_xdg_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Replace every user/XDG root before any test may resolve application state."""

    roots = {
        name: tmp_path / f"isolated-{name}"
        for name in ("home", "config", "data", "state", "cache", "runtime")
    }
    for path in roots.values():
        path.mkdir(mode=0o700)
        path.chmod(0o700)
    monkeypatch.setenv("HOME", str(roots["home"]))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(roots["config"]))
    monkeypatch.setenv("XDG_DATA_HOME", str(roots["data"]))
    monkeypatch.setenv("XDG_STATE_HOME", str(roots["state"]))
    monkeypatch.setenv("XDG_CACHE_HOME", str(roots["cache"]))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(roots["runtime"]))
    return roots


@pytest.fixture(autouse=True)
def deny_external_network(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Iterator[None]:
    """Fail every test that attempts an IPv4/IPv6 connection."""

    if request.node.get_closest_marker("local_loopback") is not None:
        yield
        return

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_connect(instance: socket.socket, address: object) -> None:
        if instance.family in {socket.AF_INET, socket.AF_INET6}:
            raise AssertionError("foundation tests must not access the network")
        original_connect(instance, address)  # type: ignore[arg-type]

    def guarded_connect_ex(instance: socket.socket, address: object) -> int:
        if instance.family in {socket.AF_INET, socket.AF_INET6}:
            raise AssertionError("foundation tests must not access the network")
        return original_connect_ex(instance, address)  # type: ignore[arg-type]

    def guarded_create_connection(*_args: object, **_kwargs: object) -> socket.socket:
        raise AssertionError("foundation tests must not access the network")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    yield
