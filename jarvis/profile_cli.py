"""Small validated CLI used by launch scripts for profile metadata."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jarvis.profiles import (
    associate_profile_model, model_key, profile_config_directory, profile_locations, profile_models, select_profile_model,
)


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    port = sub.add_parser("port-in-use")
    port.add_argument("port", type=int)
    switch = sub.add_parser("switch-target")
    switch.add_argument("path", type=Path)
    key = sub.add_parser("model-key")
    key.add_argument("path", type=Path)
    options = parser.parse_args(arguments)
    if options.command == "list":
        for location in profile_locations():
            if location.slug is not None:
                print(location.slug)
        return
    if options.command == "port-in-use":
        if not 1 <= options.port <= 65535:
            raise SystemExit(2)
        wanted = f"{options.port:04X}"
        for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
            try:
                lines = table.read_text(encoding="ascii").splitlines()[1:]
            except OSError:
                continue
            for line in lines:
                fields = line.split()
                if len(fields) > 3 and fields[1].rsplit(":", 1)[-1] == wanted and fields[3] == "0A":
                    raise SystemExit(0)
        raise SystemExit(1)
    if options.command == "model-key":
        print(model_key(options.path))
        return
    path = options.path.expanduser().absolute()
    if path.is_symlink() or not path.is_file():
        raise SystemExit("Pedido de troca ausente ou inseguro")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"Pedido de troca inválido: {error}") from error
    target = payload.get("target") if isinstance(payload, dict) else None
    model = payload.get("model") if isinstance(payload, dict) else None
    if not isinstance(target, str) or not (profile_config_directory(target) / "config.xml").is_file():
        raise SystemExit("Perfil de destino inválido ou inexistente")
    if model is not None:
        if not isinstance(model, str):
            raise SystemExit("Modelo de destino inválido")
        selected = Path(model).expanduser().resolve(strict=False)
        if selected not in profile_models(target):
            if payload.get("associate") is True:
                associate_profile_model(target, selected)
            else:
                raise SystemExit("Modelo não associado ao perfil de destino")
        select_profile_model(target, selected)
    print(target)


if __name__ == "__main__":
    main()
