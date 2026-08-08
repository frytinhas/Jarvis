from __future__ import annotations

from pathlib import Path
import os
import stat


PROTECTED_WRITE_PATHS = tuple(
    Path(path) for path in ("/", "/boot", "/dev", "/etc", "/proc", "/sys", "/usr", "/var/lib")
)


class PathValidationError(ValueError):
    pass


def resolve_path(raw_path: str) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise PathValidationError("Path vazio ou inválido")
    return Path(raw_path).expanduser().resolve(strict=False)


def validate_write_path(raw_path: str) -> Path:
    path = resolve_path(raw_path)
    for protected in PROTECTED_WRITE_PATHS:
        if protected == Path("/"):
            if path == protected:
                raise PathValidationError("Escrita no path raiz é bloqueada")
        elif path == protected or protected in path.parents:
            raise PathValidationError(f"Escrita em área protegida: {protected}")
    return path


def validate_execute_path(raw_path: str) -> Path:
    path = resolve_path(raw_path)
    try:
        path = path.resolve(strict=True)
        metadata = path.stat()
    except OSError as error:
        raise PathValidationError(f"Executável inexistente ou inacessível: {path}") from error
    if not path.is_file():
        raise PathValidationError(f"O path de execução não é um arquivo: {path}")
    if metadata.st_mode & (stat.S_ISUID | stat.S_ISGID):
        raise PathValidationError("Executáveis setuid/setgid são bloqueados")
    if path.suffix.lower() != ".sh" and not os.access(path, os.X_OK):
        raise PathValidationError(f"Arquivo sem permissão de execução: {path}")
    return path


def validate_rename_name(name: str) -> str:
    if name in {".", ".."} or Path(name).name != name:
        raise PathValidationError("new_name deve ser somente um nome, sem diretórios")
    return name
