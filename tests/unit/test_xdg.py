from __future__ import annotations

import os
from pathlib import Path

import pytest

from jarvis.foundation.errors import ConfigurationError, StorageError
from jarvis.storage.xdg import initialize_xdg_directories, resolve_xdg_paths

pytestmark = pytest.mark.unit


def _runtime(path: Path) -> Path:
    path.mkdir(mode=0o700)
    return path


def test_resolution_uses_five_independent_absolute_overrides(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path / "runtime")
    env = {
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_RUNTIME_DIR": str(runtime),
    }
    paths = resolve_xdg_paths(env)
    assert paths.config == tmp_path / "config" / "jarvis-cli"
    assert paths.data == tmp_path / "data" / "jarvis-cli"
    assert paths.state == tmp_path / "state" / "jarvis-cli"
    assert paths.cache == tmp_path / "cache" / "jarvis-cli"
    assert paths.runtime == runtime / "jarvis-cli"
    assert not any(path.exists() for path in paths.all())


def test_relative_persistent_values_fall_back_but_relative_runtime_fails(tmp_path: Path) -> None:
    home = tmp_path / "home"
    runtime = _runtime(tmp_path / "runtime")
    paths = resolve_xdg_paths(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": "relative-config",
            "XDG_DATA_HOME": "relative-data",
            "XDG_STATE_HOME": "relative-state",
            "XDG_CACHE_HOME": "relative-cache",
            "XDG_RUNTIME_DIR": str(runtime),
        }
    )
    assert paths.config == home / ".config" / "jarvis-cli"
    assert paths.data == home / ".local" / "share" / "jarvis-cli"
    assert paths.state == home / ".local" / "state" / "jarvis-cli"
    assert paths.cache == home / ".cache" / "jarvis-cli"

    with pytest.raises(ConfigurationError) as caught:
        resolve_xdg_paths({"HOME": str(home), "XDG_RUNTIME_DIR": "relative"})
    assert caught.value.code == "xdg.unsafe_runtime_directory"


def test_missing_home_uses_injected_passwd_home(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path / "runtime")
    home = tmp_path / "passwd-home"
    paths = resolve_xdg_paths(
        {"XDG_RUNTIME_DIR": str(runtime)},
        home_resolver=lambda _uid: home,
    )
    assert paths.config == home / ".config" / "jarvis-cli"


def test_missing_runtime_uses_only_injected_run_user_fallback(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path / "run-user")
    paths = resolve_xdg_paths(
        {"HOME": str(tmp_path / "home")},
        runtime_fallback_resolver=lambda _uid: runtime,
    )
    assert paths.runtime == runtime / "jarvis-cli"


def test_missing_runtime_fails_closed_without_tmp_fallback(tmp_path: Path) -> None:
    missing = tmp_path / "missing-run-user"
    with pytest.raises(ConfigurationError) as caught:
        resolve_xdg_paths(
            {"HOME": str(tmp_path / "home")},
            runtime_fallback_resolver=lambda _uid: missing,
        )
    assert caught.value.code == "xdg.runtime_directory_unavailable"
    assert not missing.exists()


@pytest.mark.parametrize("mode", [0o701, 0o710, 0o755])
def test_runtime_with_group_or_other_permissions_is_rejected(tmp_path: Path, mode: int) -> None:
    runtime = _runtime(tmp_path / "runtime")
    runtime.chmod(mode)
    with pytest.raises(ConfigurationError) as caught:
        resolve_xdg_paths({"HOME": str(tmp_path / "home"), "XDG_RUNTIME_DIR": str(runtime)})
    assert caught.value.code == "xdg.unsafe_runtime_directory"


def test_symlink_runtime_is_rejected(tmp_path: Path) -> None:
    target = _runtime(tmp_path / "target")
    link = tmp_path / "runtime-link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ConfigurationError) as caught:
        resolve_xdg_paths({"HOME": str(tmp_path / "home"), "XDG_RUNTIME_DIR": str(link)})
    assert caught.value.safe_details["reason"] == "symlink"


def test_wrong_runtime_owner_is_rejected_with_injected_metadata(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path / "runtime")
    real = runtime.lstat()
    values = list(real)
    values[4] = os.getuid() + 1
    wrong_owner = os.stat_result(values)
    with pytest.raises(ConfigurationError) as caught:
        resolve_xdg_paths(
            {"HOME": str(tmp_path / "home"), "XDG_RUNTIME_DIR": str(runtime)},
            stat_reader=lambda _path: wrong_owner,
        )
    assert caught.value.safe_details["reason"] == "wrong_owner"


def test_initialization_creates_private_application_directories(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path / "runtime")
    env = {
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "XDG_RUNTIME_DIR": str(runtime),
    }
    paths = resolve_xdg_paths(env)
    created = initialize_xdg_directories(paths)
    assert set(created) == set(paths.all())
    assert all(path.is_dir() and (path.stat().st_mode & 0o777) == 0o700 for path in paths.all())
    assert initialize_xdg_directories(paths) == ()


def test_existing_unsafe_or_symlinked_application_directory_is_rejected(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path / "runtime")
    paths = resolve_xdg_paths(
        {
            "HOME": str(tmp_path / "home"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "XDG_RUNTIME_DIR": str(runtime),
        }
    )
    paths.config.mkdir(parents=True, mode=0o755)
    paths.config.chmod(0o755)
    with pytest.raises(StorageError):
        initialize_xdg_directories(paths)

    paths.config.chmod(0o700)
    paths.data.parent.mkdir(parents=True)
    paths.data.symlink_to(paths.config, target_is_directory=True)
    with pytest.raises(StorageError):
        initialize_xdg_directories(paths)
