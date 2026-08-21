"""Thin `jarvis-manage` IPC presenter; no repository access."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence

from jarvis.ipc.client import JarvisIpcClient
from jarvis.ipc.errors import IpcError
from jarvis.ipc.models import REQUEST_STREAM
from jarvis.storage.xdg import resolve_xdg_paths

HELP = """Jarvis Management

Manage local model directories and the stored llama-server path through Jarvis Core."""

_DECIMAL_CONFIG_FIELDS = frozenset({"temperature", "top_p", "min_p", "repeat_penalty"})


def _config_payload(value: object) -> object:
    """Adapt JSON decimal numbers to protocol-v1's exact decimal-string representation."""

    if not isinstance(value, dict):
        return value
    return {
        key: repr(item) if key in _DECIMAL_CONFIG_FIELDS and isinstance(item, float) else item
        for key, item in value.items()
    }


async def _run(args: argparse.Namespace) -> int:
    c = await JarvisIpcClient.connect(
        resolve_xdg_paths().runtime / "core.sock",
        required_capabilities=(REQUEST_STREAM, "model-registry-v1"),
        client_name="jarvis-manage",
    )
    try:
        payload = (
            {"directories": args.directories, "runtime_path": args.runtime_path}
            if args.command == "runtime-update"
            else {}
        )
        operation = {
            "runtime-get": "installation.runtime.get",
            "runtime-update": "installation.runtime.update",
            "refresh": "models.refresh",
            "list": "models.list",
            "get": "models.get",
            "profile-models": "profiles.models.list",
            "select": "profiles.models.select",
            "config-get": "profiles.models.config.get",
            "config-update": "profiles.models.config.update",
        }[args.command]
        if args.command in {"get", "config-get"}:
            payload = {"model_id": args.model_id}
        if args.command == "select":
            payload = {"model_id": args.model_id, "expected_profile_model_revision": args.revision}
        if args.command == "config-update":
            payload = {
                "model_id": args.model_id,
                "expected_profile_model_revision": args.revision,
                "config": _config_payload(json.loads(args.config)),
            }
        events = [
            event
            async for event in c.request(
                operation, payload=payload, profile_id=getattr(args, "profile_id", None)
            )
        ]
        final = events[-1]
        print(json.dumps(final, sort_keys=True))
        if final.get("type") == "error" or final.get("event_type") == "error":
            return 1
    finally:
        await c.close()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jarvis-manage", description=HELP)
    sub = p.add_subparsers(dest="command")
    sub.add_parser("runtime-get")
    u = sub.add_parser("runtime-update")
    u.add_argument("--directory", dest="directories", action="append", default=[])
    u.add_argument("--runtime-path")
    sub.add_parser("refresh")
    sub.add_parser("list")
    g = sub.add_parser("get")
    g.add_argument("model_id")
    for command in ("profile-models", "select", "config-get", "config-update"):
        item = sub.add_parser(command)
        item.add_argument("--profile-id", required=True)
        if command != "profile-models":
            item.add_argument("model_id")
        if command in {"select", "config-update"}:
            item.add_argument("--revision", required=True, type=int)
        if command == "config-update":
            item.add_argument("--config", required=True)
    a = p.parse_args(argv)
    if not a.command:
        p.print_help()
        return 0
    try:
        return asyncio.run(_run(a))
    except (OSError, IpcError) as error:
        code = error.code if isinstance(error, IpcError) else "ipc.core_unavailable"
        print(json.dumps({"error": {"code": code}}, sort_keys=True), file=sys.stderr)
        return 1
    except json.JSONDecodeError:
        print(
            json.dumps({"error": {"code": "model.invalid_runtime_configuration"}}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
