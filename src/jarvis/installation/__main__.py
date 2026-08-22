"""Explicit local-wheel bootstrap entry point."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from jarvis.foundation.errors import JarvisError
from jarvis.installation.bootstrap import install_from_wheel


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install Jarvis from a local wheel")
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args(argv)
    try:
        result = install_from_wheel(args.wheel)
    except JarvisError as error:
        print(json.dumps(error.to_safe_dict(), sort_keys=True))
        return 1
    print(
        json.dumps(
            {
                "outcome": result.outcome,
                "installation_root": str(result.installation_root),
                "manifest": str(result.manifest),
                "path_action": result.path_action,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
