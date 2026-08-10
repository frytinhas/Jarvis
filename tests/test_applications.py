from pathlib import Path

import pytest

from jarvis.security.policy import Decision, Risk
from jarvis.tools import applications


def _desktop_entry(directory: Path, name: str = "Spotify") -> Path:
    executable = directory / "spotify-bin"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    entry = directory / "spotify.desktop"
    entry.write_text(
        f"[Desktop Entry]\nType=Application\nName={name}\nExec={executable}\nKeywords=music;streaming;\n",
        encoding="utf-8",
    )
    return entry


def test_resolver_ignores_case_and_small_typo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _desktop_entry(tmp_path)
    monkeypatch.setattr(applications, "application_directories", lambda: (tmp_path,))

    resolved = applications.resolve_application("sPtFy")

    assert resolved.name == "Spotify"
    assert resolved.desktop_id == "spotify"


def test_registry_binds_confirmed_launch_to_resolved_application(
    registry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _desktop_entry(tmp_path)
    monkeypatch.setattr(applications, "application_directories", lambda: (tmp_path,))
    registry.policy.set_decision(Risk.EXECUTE, Decision.CONFIRM)

    result = registry.request("launch_application", {"query": "sptfy"})

    assert result.status == "confirmation_required"
    assert result.pending is not None
    assert result.pending.arguments["desktop_id"] == "spotify"
