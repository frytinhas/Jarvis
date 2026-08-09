from __future__ import annotations

import argparse
from pathlib import Path

from jarvis.config import load_config, save_config
from jarvis.resources import ensure_private_resources


def repair_user_config(target: Path) -> None:
    """Migrate a retained local configuration and create missing resources."""
    config = load_config(target)
    ensure_private_resources(config.settings)
    save_config(config, target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repair-user", type=Path, required=True)
    args = parser.parse_args()
    repair_user_config(args.repair_user)


if __name__ == "__main__":
    main()
