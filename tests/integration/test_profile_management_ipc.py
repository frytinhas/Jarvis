from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from jarvis.core.runtime import JarvisCore
from jarvis.ipc.models import PROFILE_CATALOG, PROFILE_MANAGEMENT
from jarvis.profiles.service import ProfileConfigService
from jarvis.storage.xdg import resolve_xdg_paths
from tests.support.ipc_client import RawTestClient

pytestmark = pytest.mark.integration


async def _start() -> tuple[JarvisCore, asyncio.Task[None], Path]:
    core = JarvisCore()
    task = asyncio.create_task(core.run())
    socket_path = resolve_xdg_paths().runtime / "core.sock"
    for _ in range(200):
        if socket_path.exists():
            return core, task, socket_path
        await asyncio.sleep(0.005)
    raise AssertionError("Core did not publish its socket")


def _payload(events: list[dict[str, object]]) -> dict[str, object]:
    payload = events[-1].get("payload")
    assert isinstance(payload, dict)
    return payload


def _error_code(events: list[dict[str, object]]) -> str:
    error = events[-1].get("error")
    assert isinstance(error, dict)
    return str(error["code"])


def test_create_resolve_rename_and_section_update_over_profile_management_ipc() -> None:
    async def run() -> None:
        core, task, socket_path = await _start()
        client = await RawTestClient.connect(
            socket_path, optional_capabilities=(PROFILE_CATALOG, PROFILE_MANAGEMENT)
        )
        try:
            created = await client.request(
                request_id=str(uuid4()),
                operation="profiles.create",
                payload={"display_name": "João Trabalho"},
            )
            profile = created[-1]["payload"]["profile"]
            assert profile["command_alias"] == "joao-trabalho"
            resolved = await client.request(
                request_id=str(uuid4()),
                operation="profiles.resolve_alias",
                payload={"command_alias": "joao-trabalho"},
            )
            assert resolved[-1]["payload"]["profile"]["profile_id"] == profile["profile_id"]
            snapshot = await client.request(
                request_id=str(uuid4()),
                operation="profiles.configuration.section.get",
                profile_id=profile["profile_id"],
                payload={"section": "persona"},
            )
            data = snapshot[-1]["payload"]
            updated = await client.request(
                request_id=str(uuid4()),
                operation="profiles.configuration.section.update",
                profile_id=profile["profile_id"],
                payload={
                    "section": "persona",
                    "value": "A focused assistant.",
                    "expected_identity_revision": data["identity_revision"],
                    "expected_configuration_revision": data["configuration_revision"],
                },
            )
            assert updated[-1]["payload"]["value"] == "A focused assistant."
            renamed = await client.request(
                request_id=str(uuid4()),
                operation="profiles.rename",
                profile_id=profile["profile_id"],
                payload={
                    "display_name": "Work",
                    "expected_identity_revision": profile["identity_revision"],
                },
            )
            assert renamed[-1]["payload"]["profile"]["profile_id"] == profile["profile_id"]
            old_alias = await client.request(
                request_id=str(uuid4()),
                operation="profiles.resolve_alias",
                payload={"command_alias": "joao-trabalho"},
            )
            assert _error_code(old_alias) == "profile.not_found"
            new_alias = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.resolve_alias",
                    payload={"command_alias": "work"},
                )
            )["profile"]
            assert isinstance(new_alias, dict)
            assert new_alias["profile_id"] == profile["profile_id"]
        finally:
            await client.close()
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_all_m003_sections_are_revision_checked_and_profile_isolated() -> None:
    async def run() -> None:
        core, task, socket_path = await _start()
        client = await RawTestClient.connect(
            socket_path, optional_capabilities=(PROFILE_CATALOG, PROFILE_MANAGEMENT)
        )
        try:
            first = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.create",
                    payload={"display_name": "First"},
                )
            )["profile"]
            second = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.create",
                    payload={"display_name": "Second"},
                )
            )["profile"]
            assert isinstance(first, dict) and isinstance(second, dict)
            values: dict[str, object] = {
                "persona": "Persona one",
                "profile-context": "Context one",
                "appearance": {
                    "accent_color": "#123456",
                    "foreground_color": "#abcdef",
                    "background_color": "#010203",
                },
                "waiting-messages": ["Wait safely"],
                "goodbye-messages": ["Goodbye safely"],
                "visible-logging": "full",
                "permissions": {
                    name: "ask"
                    for name in (
                        "create",
                        "copy",
                        "read",
                        "screen",
                        "internet",
                        "execute",
                        "delete",
                        "modify",
                        "move",
                    )
                },
            }
            stale: dict[str, object] | None = None
            for section, value in values.items():
                snapshot = _payload(
                    await client.request(
                        request_id=str(uuid4()),
                        operation="profiles.configuration.section.get",
                        profile_id=str(first["profile_id"]),
                        payload={"section": section},
                    )
                )
                if section == "persona":
                    stale = snapshot
                updated = _payload(
                    await client.request(
                        request_id=str(uuid4()),
                        operation="profiles.configuration.section.update",
                        profile_id=str(first["profile_id"]),
                        payload={
                            "section": section,
                            "value": value,
                            "expected_identity_revision": snapshot["identity_revision"],
                            "expected_configuration_revision": snapshot["configuration_revision"],
                        },
                    )
                )
                assert updated["value"] == value
            assert stale is not None
            stale_update = await client.request(
                request_id=str(uuid4()),
                operation="profiles.configuration.section.update",
                profile_id=str(first["profile_id"]),
                payload={
                    "section": "persona",
                    "value": "stale overwrite",
                    "expected_identity_revision": stale["identity_revision"],
                    "expected_configuration_revision": stale["configuration_revision"],
                },
            )
            assert _error_code(stale_update) == "profile.concurrent_modification"
            second_persona = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.configuration.section.get",
                    profile_id=str(second["profile_id"]),
                    payload={"section": "persona"},
                )
            )
            assert second_persona["value"] != "Persona one"
        finally:
            await client.close()
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_management_capability_and_malformed_payloads_fail_before_acceptance() -> None:
    async def run() -> None:
        core, task, socket_path = await _start()
        unprivileged = await RawTestClient.connect(socket_path)
        managed = await RawTestClient.connect(
            socket_path, optional_capabilities=(PROFILE_MANAGEMENT,)
        )
        try:
            mismatch = await unprivileged.request(
                request_id=str(uuid4()),
                operation="profiles.create",
                payload={"display_name": "Blocked"},
            )
            assert len(mismatch) == 1
            assert _error_code(mismatch) == "ipc.capability_mismatch"
            malformed = await managed.request(
                request_id=str(uuid4()),
                operation="profiles.create",
                payload={"display_name": "Work", "unexpected": True},
            )
            assert len(malformed) == 1
            assert _error_code(malformed) == "ipc.invalid_message"
            oversized = await managed.request(
                request_id=str(uuid4()),
                operation="profiles.create",
                payload={"display_name": "a" * 513},
            )
            assert len(oversized) == 1
            assert _error_code(oversized) == "ipc.invalid_message"
            alias_as_identity = await managed.request(
                request_id=str(uuid4()),
                operation="profiles.resolve_alias",
                profile_id="10000000-0000-4000-8000-000000000001",
                payload={"command_alias": "jarvis"},
            )
            assert len(alias_as_identity) == 1
            assert _error_code(alias_as_identity) == "ipc.invalid_message"
            startup_reset = await managed.request(
                request_id=str(uuid4()),
                operation="profiles.reset.preview",
                profile_id="10000000-0000-4000-8000-000000000001",
                payload={"scope": "startup"},
            )
            assert len(startup_reset) == 1
            assert _error_code(startup_reset) == "ipc.operation_not_supported"
        finally:
            await unprivileged.close()
            await managed.close()
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_section_read_uses_one_atomic_profile_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_split_read(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("section read must not use a second configuration transaction")

    monkeypatch.setattr(ProfileConfigService, "get_section", forbidden_split_read)

    async def run() -> None:
        core, task, socket_path = await _start()
        client = await RawTestClient.connect(
            socket_path, optional_capabilities=(PROFILE_CATALOG, PROFILE_MANAGEMENT)
        )
        try:
            profiles = _payload(
                await client.request(request_id=str(uuid4()), operation="profiles.list")
            )["profiles"]
            assert isinstance(profiles, list) and isinstance(profiles[0], dict)
            snapshot = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.configuration.section.get",
                    profile_id=str(profiles[0]["profile_id"]),
                    payload={"section": "persona"},
                )
            )
            assert snapshot["identity_revision"] == 1
            assert snapshot["configuration_revision"] == 1
        finally:
            await client.close()
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)

    asyncio.run(run())


def test_reset_delete_confirmation_and_alias_lifecycle_over_ipc() -> None:
    async def run() -> None:
        core, task, socket_path = await _start()
        client = await RawTestClient.connect(
            socket_path, optional_capabilities=(PROFILE_CATALOG, PROFILE_MANAGEMENT)
        )
        try:
            catalog = _payload(
                await client.request(request_id=str(uuid4()), operation="profiles.list")
            )["profiles"]
            assert isinstance(catalog, list)
            jarvis = catalog[0]
            assert isinstance(jarvis, dict)
            created = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.create",
                    payload={"display_name": "Disposable"},
                )
            )["profile"]
            assert isinstance(created, dict)
            profile_id = str(created["profile_id"])
            snapshot = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.configuration.section.get",
                    profile_id=profile_id,
                    payload={"section": "persona"},
                )
            )
            await client.request(
                request_id=str(uuid4()),
                operation="profiles.configuration.section.update",
                profile_id=profile_id,
                payload={
                    "section": "persona",
                    "value": "Customized",
                    "expected_identity_revision": snapshot["identity_revision"],
                    "expected_configuration_revision": snapshot["configuration_revision"],
                },
            )
            cancelled_preview = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.reset.preview",
                    profile_id=profile_id,
                    payload={"scope": "persona"},
                )
            )["preview"]
            assert isinstance(cancelled_preview, dict)
            still_custom = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.configuration.section.get",
                    profile_id=profile_id,
                    payload={"section": "persona"},
                )
            )
            assert still_custom["value"] == "Customized"
            reset = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.reset.preview",
                    profile_id=profile_id,
                    payload={"scope": "whole-profile"},
                )
            )["preview"]
            assert isinstance(reset, dict)
            forged = await client.request(
                request_id=str(uuid4()),
                operation="profiles.reset.confirm",
                profile_id=profile_id,
                payload={
                    "operation_id": reset["operation_id"],
                    "scope": "whole-profile",
                    "confirmation_token": "forged",
                },
            )
            assert _error_code(forged) == "profile.confirmation_invalid"
            confirmation = {
                "operation_id": reset["operation_id"],
                "scope": "whole-profile",
                "confirmation_token": reset["confirmation_token"],
            }
            completed = await client.request(
                request_id=str(uuid4()),
                operation="profiles.reset.confirm",
                profile_id=profile_id,
                payload=confirmation,
            )
            assert _payload(completed)["scope"] == "whole-profile"
            replay = await client.request(
                request_id=str(uuid4()),
                operation="profiles.reset.confirm",
                profile_id=profile_id,
                payload=confirmation,
            )
            assert _error_code(replay) == "profile.confirmation_invalid"
            jarvis_delete = await client.request(
                request_id=str(uuid4()),
                operation="profiles.delete.preview",
                profile_id=str(jarvis["profile_id"]),
                payload={},
            )
            assert _error_code(jarvis_delete) == "profile.protected"
            delete_preview = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.delete.preview",
                    profile_id=profile_id,
                    payload={},
                )
            )["preview"]
            assert isinstance(delete_preview, dict)
            assert (await call_alias(client, "disposable"))["profile_id"] == profile_id
            delete_preview = _payload(
                await client.request(
                    request_id=str(uuid4()),
                    operation="profiles.delete.preview",
                    profile_id=profile_id,
                    payload={},
                )
            )["preview"]
            assert isinstance(delete_preview, dict)
            delete_result = await client.request(
                request_id=str(uuid4()),
                operation="profiles.delete.confirm",
                profile_id=profile_id,
                payload={
                    "operation_id": delete_preview["operation_id"],
                    "confirmation_token": delete_preview["confirmation_token"],
                },
            )
            assert _payload(delete_result)["deleted_profile_id"] == profile_id
            missing = await client.request(
                request_id=str(uuid4()),
                operation="profiles.resolve_alias",
                payload={"command_alias": "disposable"},
            )
            assert _error_code(missing) == "profile.not_found"
        finally:
            await client.close()
            await core.request_shutdown()
            await asyncio.wait_for(task, 5)

    asyncio.run(run())


async def call_alias(client: RawTestClient, alias: str) -> dict[str, object]:
    profile = _payload(
        await client.request(
            request_id=str(uuid4()),
            operation="profiles.resolve_alias",
            payload={"command_alias": alias},
        )
    )["profile"]
    assert isinstance(profile, dict)
    return profile
