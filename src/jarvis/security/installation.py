"""Active-installation discovery and fail-closed target protection assessment."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from enum import StrEnum
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote, urlparse

import jarvis
from jarvis.security.filesystem_identity import (
    FileIdentity,
    FileType,
    PathSnapshot,
    SnapshotStatus,
    capture_path,
    has_symlinked_ancestor,
)

INSTALLATION_IDENTITY_VERSION = 1


class InstallationMode(StrEnum):
    WHEEL = "wheel"
    EDITABLE = "editable"
    SOURCE = "source"
    AMBIGUOUS = "ambiguous"


class ProtectionDecision(StrEnum):
    PROTECTED = "protected"
    UNPROTECTED = "unprotected"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class ProtectedRoot:
    path: Path
    snapshot: PathSnapshot
    ancestor_identities: tuple[tuple[Path, FileIdentity], ...]


@dataclass(frozen=True, slots=True)
class ProtectedFile:
    path: Path
    snapshot: PathSnapshot


@dataclass(frozen=True, slots=True)
class InstallationIdentity:
    identity_version: int
    distribution_name: str
    distribution_version: str
    active_import_anchor: Path
    mode: InstallationMode
    protected_roots: tuple[ProtectedRoot, ...]
    protected_files: tuple[ProtectedFile, ...]
    protected_regular_files: frozenset[tuple[int, int]]
    complete: bool

    @classmethod
    def capture(
        cls,
        roots: tuple[Path, ...],
        *,
        active_import_anchor: Path,
        distribution_version: str,
        mode: InstallationMode,
        additional_protected_files: tuple[Path, ...] = (),
    ) -> InstallationIdentity:
        protected_roots: list[ProtectedRoot] = []
        file_identities: set[tuple[int, int]] = set()
        complete = mode is not InstallationMode.AMBIGUOUS and bool(roots)
        canonical_anchor: Path | None
        anchor_snapshot = capture_path(active_import_anchor)
        if (
            anchor_snapshot.status is SnapshotStatus.COMPLETE
            and anchor_snapshot.target_identity is not None
            and anchor_snapshot.target_identity.file_type is FileType.REGULAR
        ):
            canonical_anchor = anchor_snapshot.canonical_path
        else:
            canonical_anchor = None
            complete = False
        canonical_roots: list[Path] = []
        for supplied_root in roots:
            supplied_snapshot = capture_path(supplied_root)
            root = supplied_snapshot.canonical_path
            if root is None:
                root = supplied_root.absolute()
                complete = False
            canonical_roots.append(root)
            snapshot = capture_path(root)
            if (
                snapshot.status is not SnapshotStatus.COMPLETE
                or snapshot.target_identity is None
                or snapshot.target_identity.file_type is not FileType.DIRECTORY
            ):
                complete = False
            ancestors: list[tuple[Path, FileIdentity]] = []
            for ancestor in (root, *root.parents):
                ancestor_snapshot = capture_path(ancestor)
                if ancestor_snapshot.link_identity is None:
                    complete = False
                    continue
                ancestors.append((ancestor, ancestor_snapshot.link_identity))
            protected_roots.append(ProtectedRoot(root, snapshot, tuple(ancestors)))
            if snapshot.status is SnapshotStatus.COMPLETE:
                walk_failed = False

                def record_walk_error(_error: OSError) -> None:
                    nonlocal walk_failed
                    walk_failed = True

                for directory, directory_names, file_names in os.walk(
                    root, followlinks=False, onerror=record_walk_error
                ):
                    directory_names[:] = [
                        name
                        for name in directory_names
                        if not (Path(directory) / name).is_symlink()
                    ]
                    for name in file_names:
                        child = capture_path(Path(directory) / name)
                        if (
                            child.link_identity is not None
                            and child.link_identity.file_type is FileType.REGULAR
                        ):
                            file_identities.add(child.link_identity.inode_key)
                        elif child.status is not SnapshotStatus.COMPLETE:
                            complete = False
                if walk_failed:
                    complete = False
        if canonical_anchor is None or not any(
            canonical_anchor == root or canonical_anchor.is_relative_to(root)
            for root in canonical_roots
        ):
            complete = False
        protected_files: list[ProtectedFile] = []
        for supplied_file in additional_protected_files:
            file_snapshot = capture_path(supplied_file)
            canonical_file = file_snapshot.canonical_path
            if (
                canonical_file is None
                or file_snapshot.target_identity is None
                or file_snapshot.target_identity.file_type is not FileType.REGULAR
            ):
                complete = False
                continue
            canonical_snapshot = capture_path(canonical_file)
            if canonical_snapshot.target_identity is None:
                complete = False
                continue
            protected_files.append(ProtectedFile(canonical_file, canonical_snapshot))
            file_identities.add(canonical_snapshot.target_identity.inode_key)
        return cls(
            INSTALLATION_IDENTITY_VERSION,
            "jarvis-cli",
            distribution_version,
            canonical_anchor or active_import_anchor.absolute(),
            mode,
            tuple(protected_roots),
            tuple(protected_files),
            frozenset(file_identities),
            complete,
        )


def _source_root(anchor: Path) -> Path | None:
    for candidate in anchor.parents:
        if (candidate / "pyproject.toml").is_file() and (candidate / "src" / "jarvis").is_dir():
            return candidate
    return None


def _direct_url_root(distribution: metadata.Distribution) -> tuple[Path | None, bool]:
    raw = distribution.read_text("direct_url.json")
    if raw is None:
        return None, False
    try:
        parsed = json.loads(raw)
        url = parsed.get("url", "")
        directory_info = parsed.get("dir_info", {})
        if not isinstance(url, str) or not isinstance(directory_info, dict):
            return None, False
        location = urlparse(url)
        if location.scheme != "file":
            return None, False
        return Path(unquote(location.path)), bool(directory_info.get("editable", False))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None, False


def _distribution_metadata_root(distribution: metadata.Distribution) -> Path | None:
    """Locate the active distribution's own metadata without protecting all site-packages."""

    for entry in distribution.files or ():
        if entry.name not in {"METADATA", "RECORD"} or not entry.parent.name.endswith(".dist-info"):
            continue
        candidate = Path(str(distribution.locate_file(entry))).parent
        if candidate.is_dir():
            return candidate
    return None


def _distribution_support_files(
    distribution: metadata.Distribution, protected_roots: tuple[Path, ...]
) -> tuple[Path, ...]:
    """Return distribution-owned regular files outside already protected roots."""

    try:
        canonical_roots = tuple(root.resolve(strict=True) for root in protected_roots)
    except OSError:
        return ()
    support: list[Path] = []
    for entry in distribution.files or ():
        candidate = Path(str(distribution.locate_file(entry)))
        try:
            canonical = candidate.resolve(strict=True)
        except OSError:
            continue
        if not canonical.is_file():
            continue
        if any(canonical == root or canonical.is_relative_to(root) for root in canonical_roots):
            continue
        support.append(canonical)
    return tuple(sorted(set(support)))


def discover_active_installation() -> InstallationIdentity:
    """Discover the code actually imported by this process without network or mutation."""

    module_file = getattr(jarvis, "__file__", None)
    if module_file is None:
        return InstallationIdentity.capture(
            (),
            active_import_anchor=Path.cwd(),
            distribution_version="unknown",
            mode=InstallationMode.AMBIGUOUS,
        )
    anchor = Path(module_file).absolute()
    installed = _managed_installation_identity(anchor)
    if installed is not None:
        return installed
    source_root = _source_root(anchor)
    try:
        distribution = metadata.distribution("jarvis-cli")
        version = distribution.version
    except metadata.PackageNotFoundError:
        distribution = None
        version = getattr(jarvis, "__version__", "unknown")

    if distribution is not None:
        direct_root, editable = _direct_url_root(distribution)
        if editable and direct_root is not None:
            distribution_root = _distribution_metadata_root(distribution)
            editable_roots = (
                (direct_root,) if distribution_root is None else (direct_root, distribution_root)
            )
            support_files = _distribution_support_files(distribution, editable_roots)
            evidence_complete = distribution_root is not None and distribution.files is not None
            return InstallationIdentity.capture(
                editable_roots,
                active_import_anchor=anchor,
                distribution_version=version,
                mode=(
                    InstallationMode.EDITABLE if evidence_complete else InstallationMode.AMBIGUOUS
                ),
                additional_protected_files=support_files,
            )
    if source_root is not None:
        return InstallationIdentity.capture(
            (source_root,),
            active_import_anchor=anchor,
            distribution_version=version,
            mode=InstallationMode.SOURCE,
        )
    if distribution is not None:
        package_root = anchor.parent
        distribution_root = _distribution_metadata_root(distribution)
        roots: tuple[Path, ...] = (package_root,)
        if distribution_root is not None and distribution_root != package_root:
            roots += (distribution_root,)
        else:
            return InstallationIdentity.capture(
                roots,
                active_import_anchor=anchor,
                distribution_version=version,
                mode=InstallationMode.AMBIGUOUS,
            )
        return InstallationIdentity.capture(
            roots,
            active_import_anchor=anchor,
            distribution_version=version,
            mode=InstallationMode.WHEEL,
        )
    return InstallationIdentity.capture(
        (anchor.parent,),
        active_import_anchor=anchor,
        distribution_version=version,
        mode=InstallationMode.AMBIGUOUS,
    )


def _managed_installation_identity(anchor: Path) -> InstallationIdentity | None:
    """Consume M006C's manifest only when this exact private interpreter owns it."""

    try:
        from jarvis.installation.manifest import load_manifest, verify_manifest
        from jarvis.installation.paths import resolve_installation_paths

        paths = resolve_installation_paths()
        if not paths.manifest.exists():
            return None
        manifest = load_manifest(paths.manifest)
        if (
            Path(sys.executable).absolute() != Path(manifest.interpreter.path).absolute()
            or manifest.installation_root != str(paths.installation_root)
            or not anchor.resolve(strict=True).is_relative_to(
                paths.installation_root.resolve(strict=True)
            )
        ):
            return None
        verify_manifest(manifest)
        return InstallationIdentity.capture(
            (paths.installation_root,),
            active_import_anchor=anchor,
            distribution_version=manifest.distribution_version,
            mode=InstallationMode.WHEEL,
            additional_protected_files=(
                *(Path(asset.path) for asset in manifest.assets),
                paths.manifest,
            ),
        )
    except BaseException:
        return InstallationIdentity.capture(
            (),
            active_import_anchor=anchor,
            distribution_version="unknown",
            mode=InstallationMode.AMBIGUOUS,
        )


class InstallationProtector:
    """Evaluates a current candidate against captured active-installation evidence."""

    def __init__(self, identity: InstallationIdentity) -> None:
        self.identity = identity

    def assess(
        self,
        candidate: Path,
        *,
        expected_snapshot: PathSnapshot | None = None,
    ) -> ProtectionDecision:
        if not candidate.is_absolute() or not self.identity.complete:
            return ProtectionDecision.AMBIGUOUS
        if not self._roots_unchanged():
            return ProtectionDecision.AMBIGUOUS
        absolute = candidate.absolute()
        lexical = self._lexical_relation(absolute)
        if lexical is ProtectionDecision.PROTECTED:
            return lexical

        snapshot = capture_path(absolute)
        if expected_snapshot is not None and not self._same_snapshot(expected_snapshot, snapshot):
            return ProtectionDecision.AMBIGUOUS
        if snapshot.status in {SnapshotStatus.BROKEN_LINK, SnapshotStatus.INACCESSIBLE}:
            return ProtectionDecision.AMBIGUOUS
        if snapshot.status is SnapshotStatus.MISSING:
            return self._assess_missing(absolute)
        link = snapshot.link_identity
        target = snapshot.target_identity
        if link is None or target is None:
            return ProtectionDecision.AMBIGUOUS
        if link.file_type is FileType.SPECIAL or target.file_type is FileType.SPECIAL:
            return ProtectionDecision.AMBIGUOUS
        if link.file_type is FileType.SYMLINK:
            if snapshot.canonical_path is None:
                return ProtectionDecision.AMBIGUOUS
            relation = self._lexical_relation(snapshot.canonical_path)
            return (
                relation
                if relation is ProtectionDecision.PROTECTED
                else ProtectionDecision.AMBIGUOUS
            )
        ancestor_links = has_symlinked_ancestor(absolute)
        if ancestor_links is None:
            return ProtectionDecision.AMBIGUOUS
        if ancestor_links:
            if (
                snapshot.canonical_path is not None
                and self._lexical_relation(snapshot.canonical_path) is ProtectionDecision.PROTECTED
            ):
                return ProtectionDecision.PROTECTED
            return ProtectionDecision.AMBIGUOUS
        if (
            target.file_type is FileType.REGULAR
            and target.inode_key in self.identity.protected_regular_files
        ):
            return ProtectionDecision.PROTECTED
        return ProtectionDecision.UNPROTECTED

    def _roots_unchanged(self) -> bool:
        for root in self.identity.protected_roots:
            current = capture_path(root.path)
            expected = root.snapshot.target_identity
            if current.target_identity is None or expected is None:
                return False
            if not expected.same_object(current.target_identity):
                return False
            for ancestor_path, ancestor_identity in root.ancestor_identities:
                ancestor = capture_path(ancestor_path)
                if ancestor.link_identity is None or not ancestor_identity.same_object(
                    ancestor.link_identity
                ):
                    return False
        for protected_file in self.identity.protected_files:
            current = capture_path(protected_file.path)
            expected = protected_file.snapshot.target_identity
            if current.target_identity is None or expected is None:
                return False
            if not expected.same_object(current.target_identity):
                return False
        return True

    def _lexical_relation(self, candidate: Path) -> ProtectionDecision:
        for root in self.identity.protected_roots:
            if candidate == root.path:
                return ProtectionDecision.PROTECTED
            if candidate.is_relative_to(root.path):
                return ProtectionDecision.PROTECTED
            if root.path.is_relative_to(candidate):
                return ProtectionDecision.PROTECTED
        for protected_file in self.identity.protected_files:
            if candidate == protected_file.path or protected_file.path.is_relative_to(candidate):
                return ProtectionDecision.PROTECTED
        return ProtectionDecision.UNPROTECTED

    def _assess_missing(self, candidate: Path) -> ProtectionDecision:
        parent = candidate.parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        parent_snapshot = capture_path(parent)
        if parent_snapshot.status is not SnapshotStatus.COMPLETE:
            return ProtectionDecision.AMBIGUOUS
        ancestor_links = has_symlinked_ancestor(parent / "placeholder")
        if ancestor_links is not False:
            return ProtectionDecision.AMBIGUOUS
        return ProtectionDecision.UNPROTECTED

    @staticmethod
    def _same_snapshot(expected: PathSnapshot, current: PathSnapshot) -> bool:
        if expected.status is not current.status:
            return False
        if expected.link_identity is None or current.link_identity is None:
            return expected.link_identity is current.link_identity
        return expected.link_identity == current.link_identity
