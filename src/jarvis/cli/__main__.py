"""Package chat entry and retained configuration/help console entrypoints."""

from __future__ import annotations

import sys

from .application import EXIT_USAGE, HELP_TEXT, run_sync
from .chat_application import CHAT_HELP_TEXT, parse_arguments, run_chat_sync
from .presenter import TerminalPresenter


def main() -> None:
    arguments = sys.argv[1:]
    if _chat_help_requested(arguments):
        print(CHAT_HELP_TEXT, end="")
        return
    try:
        parsed = parse_arguments(arguments)
    except ValueError as error:
        print(f"jarvis: {error}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE) from error
    raise SystemExit(run_chat_sync(parsed, TerminalPresenter()))


def config_main() -> None:
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
    print(CHAT_HELP_TEXT, end="")


def _chat_help_requested(arguments: list[str]) -> bool:
    help_flags = {"-h", "--h", "--help"}
    if len(arguments) == 1:
        return arguments[0] in help_flags
    if len(arguments) == 2:
        return arguments[0].startswith("--profile-alias=") and arguments[1] in help_flags
    return len(arguments) == 3 and arguments[0] == "--profile-alias" and arguments[2] in help_flags


if __name__ == "__main__":
    main()
