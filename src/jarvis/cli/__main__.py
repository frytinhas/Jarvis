"""Entrypoints for the M003 local configuration and help clients."""

from __future__ import annotations

import sys

from .application import EXIT_USAGE, HELP_TEXT, run_sync
from .presenter import TerminalPresenter


def main() -> None:
    arguments = sys.argv[1:]
    if arguments in (["--help"], ["-h"], ["--h"]):
        print(HELP_TEXT, end="")
        return
    if arguments:
        print("jarvis-config: unsupported arguments", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)
    raise SystemExit(run_sync(TerminalPresenter()))


def help_main() -> None:
    if sys.argv[1:] not in ([], ["--help"], ["-h"], ["--h"]):
        raise SystemExit(EXIT_USAGE)
    print(HELP_TEXT, end="")


if __name__ == "__main__":
    main()
