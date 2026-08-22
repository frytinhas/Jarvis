"""Stable fixed-command dispatch targets installed by M006C."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from jarvis.cli.__main__ import config_main, help_main
from jarvis.cli.__main__ import main as chat_main
from jarvis.manage.__main__ import main as manage_main

FIXED_COMMANDS = ("jarvis", "jarvis-config", "jarvis-help", "jarvis-manage")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] not in FIXED_COMMANDS:
        print("jarvis-dispatch: invalid fixed command", file=sys.stderr)
        return 64
    command, command_arguments = arguments[0], arguments[1:]
    previous = sys.argv
    sys.argv = [command, *command_arguments]
    try:
        if command == "jarvis":
            chat_main()
            return 0
        if command == "jarvis-config":
            config_main()
            return 0
        if command == "jarvis-help":
            help_main()
            return 0
        return manage_main(command_arguments)
    finally:
        sys.argv = previous


if __name__ == "__main__":
    raise SystemExit(main())
