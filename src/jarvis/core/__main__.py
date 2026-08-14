"""Foreground `jarvisd` entry point; service installation is deliberately deferred."""

from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
from collections.abc import Sequence

from jarvis.core.runtime import JarvisCore
from jarvis.foundation.errors import JarvisError


async def _run_core() -> None:
    core = JarvisCore()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, lambda: asyncio.create_task(core.request_shutdown()))
    await core.run()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jarvisd", description="Run Jarvis Core in foreground")
    parser.add_argument("--foreground", action="store_true", help=argparse.SUPPRESS)
    parser.parse_args(argv)
    try:
        asyncio.run(_run_core())
    except KeyboardInterrupt:
        return 130
    except JarvisError as error:
        print(json.dumps(error.to_safe_dict(), sort_keys=True), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
