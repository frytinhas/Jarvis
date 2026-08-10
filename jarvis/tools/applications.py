"""Safe discovery and launch of installed freedesktop applications."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
from typing import Any

from jarvis.security.validator import PathValidationError, validate_execute_path


_FIELD_CODE = re.compile(r"%(?:%|[fFuUdDnNickvm])")
_UNSAFE_EXECUTABLES = {"sudo", "su", "doas", "pkexec", "env", "sh", "bash", "dash", "zsh"}


@dataclass(frozen=True)
class Application:
    desktop_id: str
    name: str
    generic_name: str
    keywords: tuple[str, ...]
    executable: Path
    arguments: tuple[str, ...]


def application_directories() -> tuple[Path, ...]:
    # User-writable desktop entries are deliberately excluded. Otherwise a model could create a
    # new entry through the file tools and turn this narrow launcher into an indirect shell.
    roots = (Path("/usr/local/share"), Path("/usr/share"), Path("/var/lib/flatpak/exports/share"))
    return tuple(root / "applications" for root in roots)


def discover_applications() -> list[Application]:
    """Read desktop entries, preferring the user's entry for duplicate desktop IDs."""
    found: dict[str, Application] = {}
    for directory in reversed(application_directories()):
        try:
            entries = sorted(directory.rglob("*.desktop"))
        except OSError:
            continue
        for entry in entries:
            try:
                app = _parse_desktop_entry(entry, directory)
            except (OSError, UnicodeError, ValueError, PathValidationError):
                continue
            if app is not None:
                found[app.desktop_id] = app
    return sorted(found.values(), key=lambda app: (_normal(app.name), app.desktop_id))


def resolve_application(query: str) -> Application:
    normalized = _normal(query)
    if not normalized:
        raise ValueError("Nome do aplicativo vazio")
    scored = sorted(
        ((_score(normalized, app), app) for app in discover_applications()),
        key=lambda item: (-item[0], _normal(item[1].name), item[1].desktop_id),
    )
    if not scored or scored[0][0] < 0.58:
        raise ValueError(f"Aplicativo não encontrado: {query}")
    score, selected = scored[0]
    # A close second can be a different program with a similarly misspelled name.
    if len(scored) > 1 and score - scored[1][0] < 0.08 and scored[1][0] >= 0.58:
        choices = ", ".join(app.name for _, app in scored[:5])
        raise ValueError(f"Aplicativo ambíguo: {query}. Opções: {choices}")
    return selected


def launch_application(
    query: str,
    desktop_id: str | None = None,
    executable: str | None = None,
    arguments: list[str] | None = None,
) -> dict[str, Any]:
    app = resolve_application(query)
    expected_arguments = list(app.arguments)
    if desktop_id != app.desktop_id or executable != str(app.executable) or list(arguments or []) != expected_arguments:
        raise ValueError("A resolução do aplicativo mudou; tente novamente")
    process = subprocess.Popen(
        [str(app.executable), *expected_arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        start_new_session=True,
    )
    return {"application": app.name, "desktop_id": app.desktop_id, "path": str(app.executable), "pid": process.pid, "background": True}


def _parse_desktop_entry(path: Path, root: Path) -> Application | None:
    values: dict[str, str] = {}
    active = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("["):
            active = line == "[Desktop Entry]"
            continue
        if active and "=" in line:
            key, value = line.split("=", 1)
            values.setdefault(key, value)
    if values.get("Type") != "Application" or values.get("NoDisplay", "false").lower() == "true":
        return None
    name, command = values.get("Name", "").strip(), values.get("Exec", "").strip()
    if not name or not command:
        return None
    argv = _desktop_exec(command)
    executable = _resolve_executable(argv[0])
    if executable.name.lower() in _UNSAFE_EXECUTABLES:
        raise PathValidationError("Launcher de aplicativo usa executável bloqueado")
    relative = path.relative_to(root).with_suffix("")
    desktop_id = "-".join(relative.parts)
    return Application(
        desktop_id=desktop_id,
        name=name,
        generic_name=values.get("GenericName", ""),
        keywords=tuple(item for item in values.get("Keywords", "").split(";") if item),
        executable=executable,
        arguments=tuple(argv[1:]),
    )


def _desktop_exec(command: str) -> list[str]:
    import shlex

    argv = shlex.split(command, posix=True)
    if not argv:
        raise ValueError("Exec vazio")
    cleaned: list[str] = []
    for value in argv:
        if "%" in value:
            if _FIELD_CODE.fullmatch(value) and value != "%%":
                continue
            value = _FIELD_CODE.sub("", value)
            if "%" in value:
                raise ValueError("Código de campo inválido em Exec")
        if "\x00" in value:
            raise ValueError("Argumento inválido")
        cleaned.append(value)
    if not cleaned or not cleaned[0]:
        raise ValueError("Executável ausente")
    return cleaned


def _resolve_executable(command: str) -> Path:
    candidate = Path(command)
    raw = str(candidate.expanduser()) if candidate.is_absolute() else shutil.which(command)
    if raw is None:
        raise PathValidationError(f"Executável do aplicativo não encontrado: {command}")
    return validate_execute_path(raw)


def _normal(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(re.sub(r"[^\w]+", " ", "".join(char for char in folded if not unicodedata.combining(char))).split())


def _score(query: str, app: Application) -> float:
    candidates = (app.name, app.generic_name, app.desktop_id, app.executable.name, *app.keywords)
    scores = []
    for candidate in candidates:
        normalized = _normal(candidate)
        if not normalized:
            continue
        if normalized == query:
            scores.append(1.0)
        elif query in normalized or normalized in query:
            scores.append(0.92)
        else:
            scores.append(SequenceMatcher(a=query, b=normalized).ratio())
    return max(scores, default=0.0)
