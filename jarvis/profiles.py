"""Profile discovery and path selection for independently configured GGUF assistants."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import socket
from uuid import uuid4


PROFILE_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
LEGACY_PROFILE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
PROFILE_ENV = "JARVIS_PROFILE"


def config_root() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()
    return base / "jarvis"


def state_root() -> Path:
    return Path.home() / ".local/state/jarvis"


def normalize_profile_name(value: str) -> str:
    slug = value.strip().lower()
    if not PROFILE_PATTERN.fullmatch(slug):
        raise ValueError(
            "Use letras sem acento, números ou hífen; comece por letra e não use espaços"
        )
    if slug == "jarvis-config":
        raise ValueError("Esse nome é reservado pelo configurador")
    return slug


def active_profile() -> str | None:
    value = os.environ.get(PROFILE_ENV)
    if not value:
        return None
    slug = value.strip().lower()
    if not LEGACY_PROFILE_PATTERN.fullmatch(slug) or slug == "jarvis-config":
        raise ValueError("Perfil ativo inválido")
    return slug


def profile_config_directory(slug: str) -> Path:
    if not LEGACY_PROFILE_PATTERN.fullmatch(slug):
        raise ValueError("Perfil inválido")
    return config_root() / "profiles" / slug


def profile_state_directory(slug: str) -> Path:
    if not LEGACY_PROFILE_PATTERN.fullmatch(slug):
        raise ValueError("Perfil inválido")
    return state_root() / "profiles" / slug


def unnamed_config_directory(identifier: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", identifier):
        raise ValueError("Identificador de perfil sem nome inválido")
    return config_root() / "unnamed" / identifier


def new_profile_id() -> str:
    return uuid4().hex


@dataclass(frozen=True)
class ProfileLocation:
    slug: str | None
    identifier: str
    config_file: Path


def profile_locations() -> list[ProfileLocation]:
    locations: list[ProfileLocation] = []
    named = config_root() / "profiles"
    if named.is_dir():
        for directory in sorted(named.iterdir(), key=lambda item: item.name.lower()):
            if not directory.is_dir() or not LEGACY_PROFILE_PATTERN.fullmatch(directory.name):
                continue
            config_file = directory / "config.xml"
            if config_file.is_file():
                locations.append(ProfileLocation(directory.name, directory.name, config_file))
    unnamed = config_root() / "unnamed"
    if unnamed.is_dir():
        for directory in sorted(unnamed.iterdir(), key=lambda item: item.name):
            config_file = directory / "config.xml"
            if directory.is_dir() and config_file.is_file():
                locations.append(ProfileLocation(None, directory.name, config_file))
    return locations


def private_profile_paths(slug: str) -> tuple[Path, Path]:
    return profile_config_directory(slug), profile_state_directory(slug)


def configured_model_paths() -> dict[Path, ProfileLocation]:
    from jarvis.config import load_config

    result: dict[Path, ProfileLocation] = {}
    for location in profile_locations():
        try:
            model = load_config(location.config_file).settings.model_path
            if model is not None:
                result[model.expanduser().resolve(strict=False)] = location
        except Exception:
            continue
    return result


def validate_profile_uniqueness(config, source: Path) -> None:
    model = config.settings.model_path
    source_resolved = source.expanduser().resolve(strict=False)
    for location in profile_locations():
        if location.config_file.resolve(strict=False) == source_resolved:
            continue
        try:
            other = __import__("jarvis.config", fromlist=["load_config"]).load_config(location.config_file)
        except Exception:
            continue
        if model is not None and other.settings.model_path is not None:
            if model.expanduser().resolve(strict=False) == other.settings.model_path.expanduser().resolve(strict=False):
                raise ValueError("Este GGUF já pertence a outro perfil")
        if config.settings.server_port == other.settings.server_port:
            raise ValueError("A porta do servidor já pertence a outro perfil")


def allocate_server_port(preferred: int = 8080) -> int:
    from jarvis.config import load_config

    used: set[int] = set()
    for location in profile_locations():
        try:
            used.add(load_config(location.config_file).settings.server_port)
        except Exception:
            continue
    for port in range(max(1024, preferred), 65536):
        if port in used:
            continue
        try:
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", port))
        except PermissionError:
            # Some containers prohibit socket creation entirely. Registry uniqueness still applies;
            # the launcher performs the authoritative runtime conflict check.
            return port
        except OSError:
            continue
        return port
    raise OSError("Nenhuma porta local está disponível para outro perfil")


def profile_paths(directory: Path) -> dict[str, Path]:
    return {
        "persona_path": directory / "Persona.md",
        "context_path": directory / "Context.md",
        "waiting_messages_path": directory / "WaitingMessages.txt",
        "goodbye_messages_path": directory / "GoodbyeMessages.txt",
        "blacklist_path": directory / "Blacklist.txt",
        "whitelist_path": directory / "Whitelist.txt",
        "learning_context_path": directory / "LearningContext.md",
    }


def build_profile_config(model: Path, display_name: str, *, autostart: bool = True):
    from jarvis.config import default_config

    slug = normalize_profile_name(display_name)
    directory = profile_config_directory(slug)
    port = allocate_server_port()
    config = default_config()
    settings = config.settings.model_copy(update={
        "profile_id": new_profile_id(),
        "learning_state": "pending",
        "model_directory": model.parent,
        "model_path": model.expanduser().resolve(strict=True),
        "server_port": port,
        "assistant_name": display_name,
        "command_name": slug,
        "autostart": autostart,
        **profile_paths(directory),
    })
    advanced = config.advanced.model_copy(update={
        "llm_base_url": f"http://127.0.0.1:{port}/v1",
        "audit_db_path": profile_state_directory(slug) / "audit.db",
    })
    return config.model_copy(update={"settings": settings, "advanced": advanced})


def migrate_legacy_profile() -> str | None:
    """Move the version-12 single-profile layout into the named profile layout."""
    from jarvis.config import load_config, save_config

    legacy = config_root() / "config.xml"
    if not legacy.is_file():
        return None
    config = load_config(legacy)
    slug = config.settings.command_name.lower()
    if not LEGACY_PROFILE_PATTERN.fullmatch(slug):
        raise ValueError(f"Nome legado inválido: {slug}")
    destination = profile_config_directory(slug)
    if (destination / "config.xml").exists():
        return slug
    destination.mkdir(parents=True, exist_ok=False)
    destination.chmod(0o700)
    old_paths = {
        "persona_path": config.settings.persona_path,
        "context_path": config.settings.context_path,
        "waiting_messages_path": config.settings.waiting_messages_path,
        "goodbye_messages_path": config.settings.goodbye_messages_path,
        "blacklist_path": config.settings.blacklist_path,
        "whitelist_path": config.settings.whitelist_path,
        "learning_context_path": config_root() / "LearningContext.md",
    }
    new_paths = profile_paths(destination)
    for field, source in old_paths.items():
        target = new_paths[field]
        if source.exists() and source.parent == config_root():
            shutil.move(str(source), target)
    colors = config_root() / "colors.toml"
    if colors.exists():
        shutil.move(str(colors), destination / colors.name)
    for notes_name in ("jarvis-notes", "jarvis-notes.lock"):
        notes = config_root() / notes_name
        if notes.exists():
            shutil.move(str(notes), destination / notes.name)
    state_destination = profile_state_directory(slug)
    state_destination.mkdir(parents=True, exist_ok=True)
    state_destination.chmod(0o700)
    for candidate in list(state_root().iterdir()) if state_root().is_dir() else []:
        if candidate.name == "profiles":
            continue
        shutil.move(str(candidate), state_destination / candidate.name)
    audit = config.advanced.audit_db_path
    if audit.expanduser().resolve(strict=False) == (state_root() / "audit.db").resolve(strict=False):
        audit = state_destination / "audit.db"
    settings = config.settings.model_copy(update={
        "profile_id": config.settings.profile_id or new_profile_id(),
        "learning_state": "complete",
        **new_paths,
    })
    advanced = config.advanced.model_copy(update={"audit_db_path": audit})
    save_config(config.model_copy(update={"settings": settings, "advanced": advanced}), destination / "config.xml")
    legacy.unlink()
    return slug
