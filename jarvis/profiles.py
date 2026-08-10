"""Profile discovery and path selection for independently configured GGUF assistants."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
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


def model_key(model: Path) -> str:
    """Stable private directory name for a GGUF without exposing its path."""
    canonical = str(model.expanduser().resolve(strict=False))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def model_state_directory(slug: str, model: Path) -> Path:
    return profile_state_directory(slug) / "models" / model_key(model)


def model_config_directory(slug: str, model: Path) -> Path:
    return profile_config_directory(slug) / "models" / model_key(model)


def _catalog_path(slug: str) -> Path:
    return profile_config_directory(slug) / "models.json"


def profile_models(slug: str) -> list[Path]:
    """Return validated GGUF associations for a named profile.

    The sidecar is deliberately narrow: the XML remains the shared profile configuration.
    """
    path = _catalog_path(slug)
    try:
        raw = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    result: list[Path] = []
    for value in raw:
        if not isinstance(value, str):
            continue
        candidate = Path(value).expanduser().resolve(strict=False)
        if candidate.suffix.lower() == ".gguf" and candidate not in result:
            result.append(candidate)
    if result or path.exists():
        return result
    # A legacy named profile had exactly one active GGUF in config.xml.
    try:
        from jarvis.config import load_config
        active = load_config(profile_config_directory(slug) / "config.xml").settings.model_path
        return [active.expanduser().resolve(strict=False)] if active is not None else []
    except Exception:
        return []


def save_profile_models(slug: str, models: list[Path]) -> None:
    target = _catalog_path(slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    normalized = sorted({str(item.expanduser().resolve(strict=False)) for item in models})
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(target)


def associate_profile_model(slug: str, model: Path) -> None:
    candidate = model.expanduser().resolve(strict=False)
    if candidate.suffix.lower() != ".gguf":
        raise ValueError("O modelo precisa ser um arquivo GGUF")
    models = profile_models(slug)
    if candidate not in models:
        models.append(candidate)
        save_profile_models(slug, models)


def profile_model_owners(model: Path) -> list[str]:
    candidate = model.expanduser().resolve(strict=False)
    return [location.slug for location in profile_locations()
            if location.slug is not None and candidate in profile_models(location.slug)]


def select_profile_model(slug: str, model: Path) -> None:
    """Make an already associated model the profile's last selected model."""
    from jarvis.config import load_config, save_config

    candidate = model.expanduser().resolve(strict=False)
    ensure_profile_catalog(slug)
    if candidate not in profile_models(slug):
        raise ValueError("O GGUF não está associado a este perfil")
    config_file = profile_config_directory(slug) / "config.xml"
    config = load_config(config_file)
    settings = config.settings.model_copy(update={
        "model_directory": candidate.parent,
        "model_path": candidate,
    })
    save_config(config.model_copy(update={"settings": settings}), config_file)
    marker = profile_state_directory(slug) / "restart-required"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()


def create_profile_for_model(model: Path, display_name: str) -> str:
    """Create a named profile with defaults and its first GGUF association."""
    from jarvis.config import save_config
    from jarvis.resources import ensure_private_resources

    slug = normalize_profile_name(display_name)
    target = profile_config_directory(slug)
    if target.exists():
        raise ValueError("Já existe um perfil com esse nome")
    config = build_profile_config(model, display_name, autostart=True)
    ensure_private_resources(config.settings)
    save_config(config, target / "config.xml")
    associate_profile_model(slug, model)
    return slug


def delete_profile(slug: str) -> None:
    """Delete a non-permanent profile and all data below its validated roots."""
    slug = normalize_profile_name(slug)
    if slug == "jarvis":
        raise ValueError("O perfil permanente jarvis não pode ser apagado; use resetar")
    config = profile_config_directory(slug)
    state = profile_state_directory(slug)
    if not (config / "config.xml").is_file():
        raise ValueError("Perfil inexistente")
    shutil.rmtree(config)
    if state.exists():
        shutil.rmtree(state)


def reset_profile(slug: str) -> None:
    """Erase profile information while retaining its reserved name and empty shell."""
    from jarvis.config import default_config, save_config
    from jarvis.resources import ensure_private_resources

    slug = normalize_profile_name(slug)
    config = profile_config_directory(slug)
    state = profile_state_directory(slug)
    if not (config / "config.xml").is_file():
        raise ValueError("Perfil inexistente")
    shutil.rmtree(config)
    if state.exists():
        shutil.rmtree(state)
    config.mkdir(parents=True, exist_ok=False)
    config.chmod(0o700)
    empty = default_config()
    paths = profile_paths(config)
    settings = empty.settings.model_copy(update={
        "profile_id": new_profile_id(), "assistant_name": "Jarvis" if slug == "jarvis" else slug,
        "command_name": slug, "model_directory": None, "model_path": None, "autostart": False,
        **paths,
    })
    advanced = empty.advanced.model_copy(update={"audit_db_path": profile_state_directory(slug) / "audit.db"})
    updated = empty.model_copy(update={"settings": settings, "advanced": advanced})
    ensure_private_resources(updated.settings)
    save_config(updated, config / "config.xml")
    save_profile_models(slug, [])


def configured_model_paths() -> dict[Path, ProfileLocation]:
    from jarvis.config import load_config

    result: dict[Path, ProfileLocation] = {}
    for location in profile_locations():
        try:
            if location.slug is not None:
                ensure_profile_catalog(location.slug)
                for model in profile_models(location.slug):
                    result[model] = location
            else:
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


def ensure_profile_catalog(slug: str) -> None:
    """Backfill the catalogue for version-13 named profiles on first use."""
    from jarvis.config import load_config

    path = _catalog_path(slug)
    if path.exists():
        return
    config = load_config(profile_config_directory(slug) / "config.xml")
    if config.settings.model_path is not None:
        model = config.settings.model_path
        save_profile_models(slug, [model])
        # Version-13 data was private to the sole model. Keep it, but place it
        # under the canonical GGUF key before another model can be associated.
        old_state = profile_state_directory(slug)
        new_state = model_state_directory(slug, model)
        new_state.mkdir(parents=True, exist_ok=True)
        for name in ("logs",):
            source = old_state / name
            if source.exists() and not (new_state / name).exists():
                shutil.move(str(source), new_state / name)
        old_notes = profile_config_directory(slug) / "jarvis-notes"
        old_lock = profile_config_directory(slug) / "jarvis-notes.lock"
        new_config = model_config_directory(slug, model)
        new_config.mkdir(parents=True, exist_ok=True)
        for source in (old_notes, old_lock):
            if source.exists() and not (new_config / source.name).exists():
                shutil.move(str(source), new_config / source.name)
    else:
        save_profile_models(slug, [])


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
