from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.security.filesystem_identity import FileType, capture_path
from jarvis.security.installation import (
    InstallationIdentity,
    InstallationMode,
    InstallationProtector,
    ProtectionDecision,
    discover_active_installation,
)

pytestmark = pytest.mark.security


def _protector(tmp_path: Path) -> tuple[Path, InstallationProtector]:
    root = tmp_path / "active-installation"
    package = root / "src" / "jarvis"
    package.mkdir(parents=True)
    anchor = package / "__init__.py"
    anchor.write_text("__version__ = 'test'\n", encoding="utf-8")
    identity = InstallationIdentity.capture(
        (root,),
        active_import_anchor=anchor,
        distribution_version="test",
        mode=InstallationMode.SOURCE,
    )
    assert identity.complete
    return root, InstallationProtector(identity)


def test_root_child_and_ancestor_are_protected_but_sibling_prefix_is_not(tmp_path: Path) -> None:
    root, protector = _protector(tmp_path)
    child = root / "src" / "jarvis" / "module.py"
    child.write_text("value = 1\n", encoding="utf-8")
    sibling = root.with_name(root.name + "-backup")
    sibling.mkdir()
    assert protector.assess(root) is ProtectionDecision.PROTECTED
    assert protector.assess(child) is ProtectionDecision.PROTECTED
    assert protector.assess(root.parent) is ProtectionDecision.PROTECTED
    assert protector.assess(sibling) is ProtectionDecision.UNPROTECTED


def test_genuinely_separate_clone_is_unprotected(tmp_path: Path) -> None:
    _root, protector = _protector(tmp_path)
    clone = tmp_path / "development-clone"
    (clone / "src" / "jarvis").mkdir(parents=True)
    candidate = clone / "src" / "jarvis" / "module.py"
    candidate.write_text("value = 2\n", encoding="utf-8")
    assert protector.assess(candidate) is ProtectionDecision.UNPROTECTED


def test_symlink_into_or_out_of_protected_tree_cannot_bypass_boundary(tmp_path: Path) -> None:
    root, protector = _protector(tmp_path)
    protected_file = root / "src" / "jarvis" / "__init__.py"
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    into = tmp_path / "link-into"
    into.symlink_to(protected_file)
    out = root / "link-out"
    out.symlink_to(outside)
    assert protector.assess(into) is ProtectionDecision.PROTECTED
    assert protector.assess(out) is ProtectionDecision.PROTECTED


def test_broken_symlink_and_special_file_are_ambiguous(tmp_path: Path) -> None:
    _root, protector = _protector(tmp_path)
    broken = tmp_path / "broken"
    broken.symlink_to(tmp_path / "missing")
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    assert protector.assess(broken) is ProtectionDecision.AMBIGUOUS
    assert protector.assess(fifo) is ProtectionDecision.AMBIGUOUS
    assert capture_path(fifo).link_identity.file_type is FileType.SPECIAL  # type: ignore[union-attr]


def test_hardlink_to_protected_file_is_protected(tmp_path: Path) -> None:
    root, protector = _protector(tmp_path)
    protected_file = root / "src" / "jarvis" / "__init__.py"
    outside_link = tmp_path / "hardlink"
    try:
        os.link(protected_file, outside_link)
    except OSError as error:
        pytest.skip(f"hardlinks unavailable: {error}")
    assert protector.assess(outside_link) is ProtectionDecision.PROTECTED


def test_changed_target_identity_is_ambiguous(tmp_path: Path) -> None:
    _root, protector = _protector(tmp_path)
    candidate = tmp_path / "candidate.txt"
    candidate.write_text("first", encoding="utf-8")
    expected = capture_path(candidate)
    replacement = tmp_path / "replacement.txt"
    replacement.write_text("second", encoding="utf-8")
    os.replace(replacement, candidate)
    assert protector.assess(candidate, expected_snapshot=expected) is ProtectionDecision.AMBIGUOUS


def test_in_place_target_change_is_ambiguous(tmp_path: Path) -> None:
    _root, protector = _protector(tmp_path)
    candidate = tmp_path / "candidate.txt"
    candidate.write_text("first", encoding="utf-8")
    expected = capture_path(candidate)
    candidate.write_text("changed-size", encoding="utf-8")
    assert protector.assess(candidate, expected_snapshot=expected) is ProtectionDecision.AMBIGUOUS


def test_link_swap_after_snapshot_is_ambiguous(tmp_path: Path) -> None:
    root, protector = _protector(tmp_path)
    candidate = tmp_path / "candidate.txt"
    candidate.write_text("outside", encoding="utf-8")
    expected = capture_path(candidate)
    candidate.unlink()
    candidate.symlink_to(root / "src" / "jarvis" / "__init__.py")
    assert protector.assess(candidate, expected_snapshot=expected) is ProtectionDecision.AMBIGUOUS


def test_changed_protected_root_identity_makes_all_results_ambiguous(tmp_path: Path) -> None:
    root, protector = _protector(tmp_path)
    moved = tmp_path / "old-root"
    root.rename(moved)
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    assert protector.assess(outside) is ProtectionDecision.AMBIGUOUS


def test_changed_protected_ancestor_identity_makes_results_ambiguous(tmp_path: Path) -> None:
    original_parent = tmp_path / "original-parent"
    root = original_parent / "active-installation"
    package = root / "src" / "jarvis"
    package.mkdir(parents=True)
    anchor = package / "__init__.py"
    anchor.write_text("__version__ = 'test'\n", encoding="utf-8")
    protector = InstallationProtector(
        InstallationIdentity.capture(
            (root,),
            active_import_anchor=anchor,
            distribution_version="test",
            mode=InstallationMode.SOURCE,
        )
    )
    moved_parent = tmp_path / "moved-parent"
    original_parent.rename(moved_parent)
    original_parent.symlink_to(moved_parent, target_is_directory=True)
    outside = moved_parent / "outside"
    outside.mkdir()
    assert protector.assess(outside) is ProtectionDecision.AMBIGUOUS


def test_incomplete_installation_identity_fails_closed(tmp_path: Path) -> None:
    identity = InstallationIdentity.capture(
        (),
        active_import_anchor=tmp_path / "unknown.py",
        distribution_version="unknown",
        mode=InstallationMode.AMBIGUOUS,
    )
    assert InstallationProtector(identity).assess(tmp_path) is ProtectionDecision.AMBIGUOUS


def test_current_source_checkout_is_discovered_as_active_and_protected() -> None:
    identity = discover_active_installation()
    assert identity.complete
    assert identity.mode in {InstallationMode.SOURCE, InstallationMode.EDITABLE}
    decision = InstallationProtector(identity).assess(identity.active_import_anchor)
    assert decision is ProtectionDecision.PROTECTED


def test_wheel_discovery_protects_package_and_distribution_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site-packages"
    package = site / "jarvis"
    metadata_root = site / "jarvis_cli-0.0.0.dist-info"
    package.mkdir(parents=True)
    metadata_root.mkdir()
    anchor = package / "__init__.py"
    anchor.write_text("__version__ = '0.0.0'\n", encoding="utf-8")
    metadata_file = metadata_root / "METADATA"
    metadata_file.write_text("Name: jarvis-cli\n", encoding="utf-8")
    fake_distribution = SimpleNamespace(
        version="0.0.0",
        files=(Path("jarvis_cli-0.0.0.dist-info/METADATA"),),
        read_text=lambda _name: None,
        locate_file=lambda entry: site / entry,
    )
    monkeypatch.setattr("jarvis.security.installation.jarvis.__file__", str(anchor))
    monkeypatch.setattr(
        "jarvis.security.installation.metadata.distribution", lambda _name: fake_distribution
    )
    identity = discover_active_installation()
    assert identity.mode is InstallationMode.WHEEL
    assert identity.complete
    roots = {root.path for root in identity.protected_roots}
    assert roots == {package, metadata_root}
    protector = InstallationProtector(identity)
    assert protector.assess(anchor) is ProtectionDecision.PROTECTED
    assert protector.assess(metadata_file) is ProtectionDecision.PROTECTED


def test_editable_discovery_protects_support_files_without_blocking_siblings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    package = source / "src" / "jarvis"
    site = tmp_path / "site-packages"
    metadata_root = site / "jarvis_cli-0.0.0.dist-info"
    package.mkdir(parents=True)
    metadata_root.mkdir(parents=True)
    anchor = package / "__init__.py"
    anchor.write_text("__version__ = '0.0.0'\n", encoding="utf-8")
    metadata_file = metadata_root / "METADATA"
    metadata_file.write_text("Name: jarvis-cli\n", encoding="utf-8")
    support = site / "__editable__.jarvis_cli-0.0.0.pth"
    support.write_text(str(source), encoding="utf-8")
    sibling = site / "unrelated.py"
    sibling.write_text("value = 1\n", encoding="utf-8")
    entries = (
        Path("jarvis_cli-0.0.0.dist-info/METADATA"),
        Path("__editable__.jarvis_cli-0.0.0.pth"),
    )
    direct_url = f'{{"url":"{source.as_uri()}","dir_info":{{"editable":true}}}}'
    fake_distribution = SimpleNamespace(
        version="0.0.0",
        files=entries,
        read_text=lambda name: direct_url if name == "direct_url.json" else None,
        locate_file=lambda entry: site / entry,
    )
    monkeypatch.setattr("jarvis.security.installation.jarvis.__file__", str(anchor))
    monkeypatch.setattr(
        "jarvis.security.installation.metadata.distribution", lambda _name: fake_distribution
    )
    identity = discover_active_installation()
    assert identity.mode is InstallationMode.EDITABLE
    assert identity.complete
    assert {item.path for item in identity.protected_files} == {support}
    protector = InstallationProtector(identity)
    assert protector.assess(support) is ProtectionDecision.PROTECTED
    assert protector.assess(sibling) is ProtectionDecision.UNPROTECTED
