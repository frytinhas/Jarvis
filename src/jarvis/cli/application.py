"""Profile-first configuration flow over the public local IPC client."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping

from jarvis.ipc.client import JarvisIpcClient
from jarvis.ipc.errors import IpcError
from jarvis.ipc.models import PROFILE_CATALOG, PROFILE_MANAGEMENT, REQUEST_STREAM
from jarvis.profiles.models import ProfileId
from jarvis.storage.xdg import resolve_xdg_paths

from .presenter import TerminalPresenter, display_text

EXIT_USAGE = 64
EXIT_INTERRUPTED = 130

HELP_TEXT = """Jarvis Configuration

Usage: jarvis-config

Configure a local Jarvis profile through the running jarvisd Core.
This command never starts a model. Select a profile first, then edit its
configuration or manage its logical alias. Logical aliases are not commands yet.
"""


class ClientOperationError(RuntimeError):
    def __init__(self, code: str, message_key: str) -> None:
        self.code = code
        self.message_key = message_key
        super().__init__(code)


def _safe_error_message(error: ClientOperationError) -> str:
    if error.code == "profile.concurrent_modification":
        return "The profile changed. Select it again and retry."
    if error.code == "profile.protected":
        return "The permanent Jarvis profile cannot be changed by this action."
    if error.code.startswith("profile.confirmation_"):
        return "The confirmation is no longer valid. Preview the action again."
    if error.code in {"profile.invalid_name", "profile.name_conflict"}:
        return "That profile name is invalid or already in use."
    return f"The operation failed safely ({display_text(error.code)})."


async def _result(
    client: JarvisIpcClient,
    operation: str,
    *,
    payload: Mapping[str, object] | None = None,
    profile_id: ProfileId | None = None,
) -> Mapping[str, object]:
    events = [
        event async for event in client.request(operation, payload=payload, profile_id=profile_id)
    ]
    if not events:
        raise RuntimeError("Core returned no result")
    final = events[-1]
    # Pre-acceptance failures are unsequenced ``type: error`` messages, while
    # a dispatched request fails as its single terminal ``event_type: error``.
    # Both are client-visible typed failures and must never fall through to a
    # renderer traceback.
    if final.get("type") == "error" or final.get("event_type") == "error":
        error = final.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message_key = error.get("message_key")
            if isinstance(code, str) and isinstance(message_key, str):
                raise ClientOperationError(code, message_key)
        raise ClientOperationError("ipc.invalid_message", "error.ipc.invalid_message")
    result_payload = final.get("payload")
    if not isinstance(result_payload, dict):
        raise RuntimeError("Core returned invalid result")
    return result_payload


async def run_configuration(presenter: TerminalPresenter) -> int:
    if not presenter.interactive:
        presenter.write("jarvis-config requires an interactive terminal.")
        return EXIT_USAGE
    client = await JarvisIpcClient.connect(
        resolve_xdg_paths().runtime / "core.sock",
        required_capabilities=(REQUEST_STREAM, PROFILE_CATALOG, PROFILE_MANAGEMENT),
        client_name="jarvis-config",
    )
    try:
        while True:
            catalog = await _result(client, "profiles.list")
            profiles = catalog.get("profiles")
            if not isinstance(profiles, list):
                raise RuntimeError("Core returned invalid catalog")
            choices = [
                display_text(profile.get("display_name", ""))
                for profile in profiles
                if isinstance(profile, dict)
            ]
            choices.append("+ Create new profile")
            selected = presenter.choose("Jarvis Configuration\n\nSelect a profile:", choices)
            if selected < 0:
                return 0
            if selected == len(choices) - 1:
                name = presenter.prompt("Display name")
                try:
                    created = await _result(
                        client, "profiles.create", payload={"display_name": name}
                    )
                except ClientOperationError as error:
                    presenter.write(_safe_error_message(error))
                    continue
                profile = created.get("profile")
                if isinstance(profile, dict):
                    created_name = display_text(profile.get("display_name", ""))
                    created_alias = profile.get("command_alias", "")
                    presenter.write(f"Created {created_name} ({created_alias}).")
                continue
            profile = profiles[selected]
            if not isinstance(profile, dict):
                raise RuntimeError("Core returned invalid profile")
            try:
                await _profile_menu(client, presenter, profile)
            except ClientOperationError as error:
                presenter.write(_safe_error_message(error))
    finally:
        await client.close()


async def _profile_menu(
    client: JarvisIpcClient, presenter: TerminalPresenter, profile: Mapping[str, object]
) -> None:
    profile_id = str(profile["profile_id"])
    stable_id = ProfileId.parse(profile_id)
    sections = [
        ("Persona", "persona"),
        ("Profile context", "profile-context"),
        ("Appearance", "appearance"),
        ("Waiting messages", "waiting-messages"),
        ("Goodbye messages", "goodbye-messages"),
        ("Permissions (not enforced yet)", "permissions"),
        ("Advanced: visible logging", "visible-logging"),
        ("Rename profile", None),
        ("Reset a configuration section", "__reset__"),
        ("Delete profile", "__delete__"),
    ]
    selected = presenter.choose(
        f"Profile: {display_text(profile.get('display_name', ''))}", [item[0] for item in sections]
    )
    if selected < 0:
        return
    _label, section = sections[selected]
    if section is None:
        name = presenter.prompt("New display name")
        await _result(
            client,
            "profiles.rename",
            profile_id=stable_id,
            payload={
                "display_name": name,
                "expected_identity_revision": profile["identity_revision"],
            },
        )
        presenter.write("Profile renamed.")
        return
    if section == "__reset__":
        scope = presenter.prompt("Section to reset (or whole-profile)")
        preview = await _result(
            client, "profiles.reset.preview", profile_id=stable_id, payload={"scope": scope}
        )
        wire = preview.get("preview")
        if not isinstance(wire, dict):
            raise RuntimeError("Core returned invalid reset preview")
        presenter.write(f"Reset preview: {display_text(wire.get('items', ''))}")
        if presenter.confirm("Apply this reset?"):
            await _result(
                client,
                "profiles.reset.confirm",
                profile_id=stable_id,
                payload={
                    "operation_id": wire["operation_id"],
                    "scope": scope,
                    "confirmation_token": wire["confirmation_token"],
                },
            )
            presenter.write("Reset complete.")
        return
    if section == "__delete__":
        if profile.get("kind") == "jarvis":
            presenter.write("The permanent Jarvis profile cannot be deleted.")
            return
        preview = await _result(client, "profiles.delete.preview", profile_id=stable_id, payload={})
        wire = preview.get("preview")
        if not isinstance(wire, dict):
            raise RuntimeError("Core returned invalid delete preview")
        presenter.write(f"Delete preview: {display_text(wire.get('items', ''))}")
        if presenter.confirm("Delete this profile?"):
            await _result(
                client,
                "profiles.delete.confirm",
                profile_id=stable_id,
                payload={
                    "operation_id": wire["operation_id"],
                    "confirmation_token": wire["confirmation_token"],
                },
            )
            presenter.write("Profile deleted.")
        return
    snapshot = await _result(
        client,
        "profiles.configuration.section.get",
        profile_id=stable_id,
        payload={"section": section},
    )
    presenter.write(f"Current {section}: {display_text(snapshot.get('value', ''))}")
    while True:
        entered = presenter.prompt(
            "New value (JSON for appearance/messages/permissions; blank cancels)"
        )
        if not entered:
            return
        if section in {"appearance", "waiting-messages", "goodbye-messages", "permissions"}:
            try:
                value: object = json.loads(entered)
                break
            except json.JSONDecodeError:
                presenter.write("Invalid JSON. Try again or leave blank to cancel.")
        else:
            value = entered
            break
    await _result(
        client,
        "profiles.configuration.section.update",
        profile_id=stable_id,
        payload={
            "section": section,
            "value": value,
            "expected_identity_revision": snapshot["identity_revision"],
            "expected_configuration_revision": snapshot["configuration_revision"],
        },
    )
    presenter.write("Configuration updated.")


def run_sync(presenter: TerminalPresenter) -> int:
    try:
        return asyncio.run(run_configuration(presenter))
    except (EOFError, KeyboardInterrupt):
        return EXIT_INTERRUPTED
    except OSError:
        presenter.write("jarvis-config: Jarvis Core is unavailable.")
        return 1
    except IpcError as error:
        presenter.write(f"jarvis-config: The Core connection failed safely ({error.code}).")
        return 1
    except ClientOperationError as error:
        presenter.write(f"jarvis-config: {_safe_error_message(error)}")
        return 1
