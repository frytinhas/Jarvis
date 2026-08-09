from __future__ import annotations

import argparse
from pathlib import Path

from jarvis.config import load_config, save_config
from jarvis.resources import ensure_private_resources
from jarvis.security.policy import Decision, Risk
from jarvis.settings import editable_paths


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
        existing = load_config(target)
        ensure_private_resources(existing.settings)
        save_config(existing, target)
        return
    config = load_config(source)
    paths = editable_paths(root_home / ".config/jarvis")
    permissions = dict(config.settings.permissions)
    permissions.update({
        Risk.READ: Decision.ALLOW,
        Risk.CREATE: Decision.ALLOW,
        Risk.MODIFY: Decision.ALLOW,
        Risk.DELETE: Decision.CONFIRM,
        Risk.EXECUTE: Decision.ALLOW,
        Risk.PRIVILEGED: Decision.DENY,
    })
    settings = config.settings.model_copy(update={
        "permissions": permissions,
        "persona_path": paths["persona"],
        "context_path": paths["context"],
        "waiting_messages_path": paths["waiting_messages"],
        "goodbye_messages_path": paths["goodbye_messages"],
        "blacklist_path": paths["blacklist"],
        "whitelist_path": paths["whitelist"],
    })
    advanced = config.advanced.model_copy(
        update={"audit_db_path": root_home / ".local/state/jarvis/audit.db"}
    )
    root_config = config.model_copy(update={"settings": settings, "advanced": advanced})
    save_config(root_config, target)
    ensure_private_resources(root_config.settings)


def repair_user_config(target: Path) -> None:
    """Migrate a retained user configuration and create only missing resources."""
    config = load_config(target)
    ensure_private_resources(config.settings)
    save_config(config, target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preserve-existing", action="store_true")
    parser.add_argument("--repair-user", type=Path)
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("target", type=Path, nargs="?")
    parser.add_argument("root_home", type=Path, nargs="?")
    parser.add_argument("root_project", type=Path, nargs="?")
    args = parser.parse_args()
    if args.repair_user is not None:
        repair_user_config(args.repair_user)
        return
    if None in (args.source, args.target, args.root_home, args.root_project):
        parser.error("source, target, root_home e root_project são obrigatórios")
    clone_config_for_root(
        args.source,
        args.target,
        root_home=args.root_home,
        root_project=args.root_project,
        preserve_existing=args.preserve_existing,
    )


if __name__ == "__main__":
    main()
