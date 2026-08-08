from __future__ import annotations

import argparse
from pathlib import Path

from jarvis.config import load_config, save_config


def clone_config_for_root(
    source: Path,
    target: Path,
    *,
    root_home: Path,
    root_project: Path,
    preserve_existing: bool = False,
) -> None:
    """Create an independent root configuration from a user's configuration."""
    if preserve_existing and target.is_file():
        load_config(target)
        return
    config = load_config(source)
    settings = config.settings.model_copy(
        update={"persona_path": root_project / "Persona.md"}
    )
    advanced = config.advanced.model_copy(
        update={"audit_db_path": root_home / ".local/state/jarvis/audit.db"}
    )
    save_config(
        config.model_copy(update={"settings": settings, "advanced": advanced}),
        target,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preserve-existing", action="store_true")
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("root_home", type=Path)
    parser.add_argument("root_project", type=Path)
    args = parser.parse_args()
    clone_config_for_root(
        args.source,
        args.target,
        root_home=args.root_home,
        root_project=args.root_project,
        preserve_existing=args.preserve_existing,
    )


if __name__ == "__main__":
    main()
