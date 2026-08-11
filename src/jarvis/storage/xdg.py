"""Side-effect-free XDG resolution and secure application-directory creation."""

from __future__ import annotations

import os
import pwd
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from jarvis.foundation.errors import ConfigurationError, StorageError

APP_DIRECTORY_NAME = "jarvis-cli"
PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600

StatReader = Callable[[Path], os.stat_result]
HomeResolver = Callable[[int], Path]
RuntimeFallbackResolver = Callable[[int], Path]


@dataclass(frozen=True, slots=True)
class XdgPaths:
    """Absolute, application-specific XDG paths."""

    config: Path
    data: Path
    state: Path
    cache: Path
    runtime: Path

    def all(self) -> tuple[Path, ...]:
        return (self.config, self.data, self.state, self.cache, self.runtime)


def _default_home(uid: int) -> Path:
    try:
        return Path(pwd.getpwuid(uid).pw_dir)
    except KeyError as error:
        raise ConfigurationError(
            code="xdg.invalid_path",
            message_key="error.xdg.home_unavailable",
            internal_message=f"no passwd home for uid {uid}",
        ) from error


def _default_runtime_fallback(uid: int) -> Path:
    return Path("/run/user") / str(uid)


def _lstat(path: Path) -> os.stat_result:
    return path.lstat()


def _absolute_home(env: Mapping[str, str], uid: int, resolver: HomeResolver) -> Path:
    configured = env.get("HOME", "")
    if configured:
        candidate = Path(configured)
        if candidate.is_absolute():
            return candidate
    fallback = resolver(uid)
    if not fallback.is_absolute():
        raise ConfigurationError(
            code="xdg.invalid_path",
            message_key="error.xdg.home_unavailable",
            internal_message="home resolver returned a relative path",
        )
    return fallback


def _persistent_base(env: Mapping[str, str], variable: str, fallback: Path) -> Path:
    configured = env.get(variable, "")
    if configured:
        candidate = Path(configured)
        if candidate.is_absolute():
            return candidate
    return fallback


def _validate_runtime_base(
    path: Path,
    *,
    uid: int,
    stat_reader: StatReader,
    unavailable: bool,
) -> None:
    code = "xdg.runtime_directory_unavailable" if unavailable else "xdg.unsafe_runtime_directory"
    message_key = f"error.{code}"
    if not path.is_absolute():
        raise ConfigurationError(
            code=code,
            message_key=message_key,
            safe_details={"reason": "not_absolute"},
        )
    try:
        metadata = stat_reader(path)
    except OSError as error:
        raise ConfigurationError(
            code=code,
            message_key=message_key,
            safe_details={"reason": "unavailable"},
            internal_message=str(error),
        ) from error
    if not stat.S_ISDIR(metadata.st_mode):
        reason = "symlink" if stat.S_ISLNK(metadata.st_mode) else "not_directory"
        raise ConfigurationError(
            code=code,
            message_key=message_key,
            safe_details={"reason": reason},
        )
    if metadata.st_uid != uid:
        raise ConfigurationError(
            code=code,
            message_key=message_key,
            safe_details={"reason": "wrong_owner"},
        )
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ConfigurationError(
            code=code,
            message_key=message_key,
            safe_details={"reason": "unsafe_permissions"},
        )


def resolve_xdg_paths(
    env: Mapping[str, str] | None = None,
    *,
    uid: int | None = None,
    home_resolver: HomeResolver = _default_home,
    runtime_fallback_resolver: RuntimeFallbackResolver = _default_runtime_fallback,
    stat_reader: StatReader = _lstat,
) -> XdgPaths:
    """Resolve application paths without creating or modifying anything."""

    source = os.environ if env is None else env
    current_uid = os.getuid() if uid is None else uid
    home = _absolute_home(source, current_uid, home_resolver)

    config_base = _persistent_base(source, "XDG_CONFIG_HOME", home / ".config")
    data_base = _persistent_base(source, "XDG_DATA_HOME", home / ".local" / "share")
    state_base = _persistent_base(source, "XDG_STATE_HOME", home / ".local" / "state")
    cache_base = _persistent_base(source, "XDG_CACHE_HOME", home / ".cache")

    configured_runtime = source.get("XDG_RUNTIME_DIR", "")
    if configured_runtime:
        runtime_base = Path(configured_runtime)
        _validate_runtime_base(
            runtime_base,
            uid=current_uid,
            stat_reader=stat_reader,
            unavailable=False,
        )
    else:
        runtime_base = runtime_fallback_resolver(current_uid)
        _validate_runtime_base(
            runtime_base,
            uid=current_uid,
            stat_reader=stat_reader,
            unavailable=True,
        )

    return XdgPaths(
        config=config_base / APP_DIRECTORY_NAME,
        data=data_base / APP_DIRECTORY_NAME,
        state=state_base / APP_DIRECTORY_NAME,
        cache=cache_base / APP_DIRECTORY_NAME,
        runtime=runtime_base / APP_DIRECTORY_NAME,
    )


def verify_private_directory(path: Path, *, uid: int | None = None) -> os.stat_result:
    """Validate an existing Jarvis-owned real directory as mode 0700."""

    current_uid = os.getuid() if uid is None else uid
    try:
        metadata = path.lstat()
    except OSError as error:
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.directory_unavailable",
            internal_message=str(error),
        ) from error
    if not stat.S_ISDIR(metadata.st_mode):
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.unsafe_directory",
            safe_details={"reason": "not_real_directory"},
        )
    if metadata.st_uid != current_uid:
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.unsafe_directory",
            safe_details={"reason": "wrong_owner"},
        )
    if stat.S_IMODE(metadata.st_mode) != PRIVATE_DIRECTORY_MODE:
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.unsafe_directory",
            safe_details={"reason": "unsafe_permissions"},
        )
    return metadata


def initialize_xdg_directories(paths: XdgPaths, *, uid: int | None = None) -> tuple[Path, ...]:
    """Create and validate Jarvis-owned XDG directories, rolling back safe empty creations."""

    current_uid = os.getuid() if uid is None else uid
    created: list[tuple[Path, tuple[int, int]]] = []
    try:
        for path in paths.all():
            if not path.is_absolute():
                raise ConfigurationError(
                    code="xdg.invalid_path",
                    message_key="error.xdg.invalid_path",
                    safe_details={"reason": "not_absolute"},
                )
            existed = path.exists() or path.is_symlink()
            if not existed:
                path.mkdir(mode=PRIVATE_DIRECTORY_MODE, parents=True, exist_ok=False)
            metadata = verify_private_directory(path, uid=current_uid)
            if not existed:
                created.append((path, (metadata.st_dev, metadata.st_ino)))
        return tuple(path for path, _ in created)
    except Exception:
        for path, identity in reversed(created):
            try:
                metadata = path.lstat()
                if (metadata.st_dev, metadata.st_ino) == identity:
                    path.rmdir()
            except OSError:
                pass
        raise


def verify_private_file(path: Path, *, uid: int | None = None) -> os.stat_result:
    """Validate an existing Jarvis-owned regular file as mode 0600 and not a symlink."""

    current_uid = os.getuid() if uid is None else uid
    try:
        metadata = path.lstat()
    except OSError as error:
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.file_unavailable",
            internal_message=str(error),
        ) from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != current_uid
        or metadata.st_nlink != 1
    ):
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.unsafe_file",
            safe_details={"reason": "type_owner_or_links"},
        )
    if stat.S_IMODE(metadata.st_mode) != PRIVATE_FILE_MODE:
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.unsafe_file",
            safe_details={"reason": "unsafe_permissions"},
        )
    return metadata


def verify_private_file_descriptor(descriptor: int, *, uid: int | None = None) -> os.stat_result:
    """Validate an already-open private regular file and reject hardlinked files."""

    current_uid = os.getuid() if uid is None else uid
    try:
        metadata = os.fstat(descriptor)
    except OSError as error:
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.file_unavailable",
            internal_message=str(error),
        ) from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != current_uid
        or metadata.st_nlink != 1
    ):
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.unsafe_file",
            safe_details={"reason": "type_owner_or_links"},
        )
    if stat.S_IMODE(metadata.st_mode) != PRIVATE_FILE_MODE:
        raise StorageError(
            code="storage.io_failed",
            message_key="error.storage.unsafe_file",
            safe_details={"reason": "unsafe_permissions"},
        )
    return metadata
