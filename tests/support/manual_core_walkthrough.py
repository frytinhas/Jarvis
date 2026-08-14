"""Maintainer-only disposable-XDG walkthrough client; not included in the wheel."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from jarvis.ipc.client import JarvisIpcClient
from jarvis.ipc.models import CORE_CONTROL, CORE_HEALTH, PROFILE_CATALOG
from jarvis.profiles.models import ProfileId


async def _run(path: Path, *, shutdown: bool) -> dict[str, object]:
    client = await JarvisIpcClient.connect(
        path,
        optional_capabilities=(CORE_HEALTH, PROFILE_CATALOG, CORE_CONTROL),
        client_name="m002-manual-walkthrough",
    )
    try:
        if shutdown:
            events = [event async for event in client.request("core.shutdown")]
            return {"terminal": events[-1]}
        health = [event async for event in client.request("core.health")]
        listed = [event async for event in client.request("profiles.list")]
        list_payload = listed[-1]["payload"]
        assert isinstance(list_payload, dict)
        profiles = list_payload["profiles"]
        assert isinstance(profiles, list) and profiles and isinstance(profiles[0], dict)
        profile_id = ProfileId.parse(str(profiles[0]["profile_id"]))
        got = [event async for event in client.request("profiles.get", profile_id=profile_id)]
        return {
            "handshake": {
                "protocol_version": client.handshake.selected_version,
                "core_instance_id": str(client.handshake.core_instance_id),
                "connection_id": str(client.handshake.connection_id),
            },
            "health": health[-1]["payload"],
            "profiles": profiles,
            "get": got[-1]["payload"],
        }
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("socket", type=Path)
    parser.add_argument("--shutdown", action="store_true")
    arguments = parser.parse_args()
    print(
        json.dumps(asyncio.run(_run(arguments.socket, shutdown=arguments.shutdown)), sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
