from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.config.defaults import DefaultsRegistry
from jarvis.foundation.bootstrap import DATABASE_FILENAME, initialize_foundation
from jarvis.llm.fake import FakeLLMProvider
from jarvis.models.service import ModelRegistryService
from jarvis.profiles.service import ProfileService
from jarvis.runtimes.artifacts import RuntimeArtifacts
from jarvis.runtimes.errors import RuntimeArtifactError, RuntimeManagerError
from jarvis.runtimes.manager import RuntimeManager
from jarvis.storage.xdg import resolve_xdg_paths

pytestmark = pytest.mark.security


def test_symlinked_or_nonprivate_metadata_is_rejected_without_unlink(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    artifacts = RuntimeArtifacts.acquire(root, str(uuid4()))
    target = tmp_path / "victim"
    target.write_text("private")
    metadata = artifacts.directory / "runtime.json"
    metadata.symlink_to(target)
    with pytest.raises(RuntimeArtifactError):
        artifacts.read_metadata()
    assert target.read_text() == "private"
    metadata.unlink()
    metadata.write_text("{}")
    metadata.chmod(0o644)
    with pytest.raises(RuntimeArtifactError):
        artifacts.read_metadata()
    artifacts.release_lock()


def test_runtime_container_links_and_profile_traversal_are_rejected(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    victim = tmp_path / "victim"
    victim.mkdir(mode=0o700)
    (root / "runtimes").symlink_to(victim, target_is_directory=True)
    with pytest.raises(RuntimeArtifactError):
        RuntimeArtifacts.acquire(root, str(uuid4()))
    assert tuple(victim.iterdir()) == ()
    with pytest.raises(RuntimeArtifactError):
        RuntimeArtifacts.acquire(root, "../escape")


def test_secret_descriptor_binds_the_created_file_and_never_unlinks_a_substitute(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    artifacts = RuntimeArtifacts.acquire(root, str(uuid4()))
    key_path = artifacts.write_secret("private-runtime-key")
    descriptor = artifacts.open_secret_descriptor()
    replacement = tmp_path / "replacement"
    replacement.write_text("attacker-value")
    key_path.unlink()
    key_path.symlink_to(replacement)
    try:
        assert os.read(descriptor, 128) == b"private-runtime-key"
        artifacts.remove_secret_if_owned()
        assert key_path.is_symlink()
        assert replacement.read_text() == "attacker-value"
    finally:
        os.close(descriptor)
        key_path.unlink()
        artifacts.release_lock()


def test_forged_pid_evidence_is_never_signalled_or_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialize_foundation()
    paths = resolve_xdg_paths()
    database = paths.data / DATABASE_FILENAME
    defaults = DefaultsRegistry.load_packaged()
    profile = ProfileService(database, defaults=defaults).ensure_jarvis().profile
    artifacts = RuntimeArtifacts.acquire(paths.runtime, str(profile.profile_id))
    artifacts.write_metadata(
        {
            "runtime_id": "00000000-0000-4000-8000-000000000001",
            "profile_id": str(profile.profile_id),
            "model_id": "00000000-0000-4000-8000-000000000002",
            "boot_id": "00000000-0000-4000-8000-000000000003",
            "pid": os.getpid(),
            "start_ticks": 1,
            "process_group_id": os.getpid(),
            "executable_device": 1,
            "executable_inode": 1,
            "model_device": 1,
            "model_inode": 1,
            "endpoint_host": "127.0.0.1",
            "endpoint_port": 12345,
            "state": "READY",
        }
    )
    artifacts.release_lock()
    signals: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "killpg", lambda group, signal: signals.append((group, signal)))
    manager = RuntimeManager(
        database_path=database,
        runtime_root=paths.runtime,
        models=ModelRegistryService(database),
        provider=FakeLLMProvider(),
        defaults=defaults,
    )
    with pytest.raises(RuntimeManagerError) as caught:
        asyncio.run(manager.recover_stale())
    assert caught.value.code == "runtime.ownership_ambiguous"
    assert signals == []
    assert (artifacts.directory / "runtime.json").exists()
