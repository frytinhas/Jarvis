"""Internal maintainer entry point for Milestone 000 foundation state."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from jarvis.foundation.bootstrap import initialize_foundation, inspect_foundation
from jarvis.foundation.errors import JarvisError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m jarvis.foundation")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("initialize", "inspect"):
        child = subparsers.add_parser(command)
        child.add_argument("--json", action="store_true", help="emit compact JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "initialize":
            result = initialize_foundation()
        else:
            result = inspect_foundation()
    except JarvisError as error:
        print(
            json.dumps({"status": "error", "error": error.to_safe_dict()}, sort_keys=True),
            file=sys.stderr,
        )
        return 1
    except Exception:
        safe = {
            "status": "error",
            "error": {
                "envelope_version": 1,
                "code": "foundation.error",
                "message_key": "error.foundation.unexpected",
                "details": {},
            },
        }
        print(json.dumps(safe, sort_keys=True), file=sys.stderr)
        return 1
    indent = None if arguments.json else 2
    print(json.dumps(result, sort_keys=True, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
