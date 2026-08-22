"""M006B simple interactive and one-shot chat client over Core IPC."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from uuid import uuid4

from jarvis.ipc.client import JarvisIpcClient
from jarvis.ipc.errors import IpcError
from jarvis.ipc.models import (
    CHAT_V1,
    CORE_HEALTH,
    EVENT_REPLAY,
    MODEL_REGISTRY,
    PROFILE_CATALOG,
    PROFILE_MANAGEMENT,
    REQUEST_CANCEL,
    REQUEST_STREAM,
    RUNTIME_MANAGER,
    SESSION_RESUME,
    SETUP_V1,
    RequestId,
)
from jarvis.profiles.models import ProfileId, VisibleLoggingMode
from jarvis.storage.xdg import resolve_xdg_paths

from .application import ClientOperationError, _result
from .commands import SlashCommand, SlashCommandError, parse_slash_command
from .presenter import TerminalPresenter, display_text
from .rendering import StreamRenderer

EXIT_USAGE = 64
EXIT_INTERRUPTED = 130

CHAT_HELP_TEXT = """Jarvis Simple CLI

Usage:
  jarvis [--profile-alias ALIAS] [request ...]
  python -m jarvis.cli [--profile-alias ALIAS] [request ...]  (development)

Without a request, open the simple interactive client. With a request, run one
non-TUI turn. The default logical profile is jarvis; aliases are resolved by Core.

Options:
  --profile-alias ALIAS  Select a logical profile alias through Core
  -h, --h, --help        Show this help without connecting to Core or starting a model
"""

INTERACTIVE_HELP_TEXT = """Commands:
  /help                  Show this command list
  /quit, /exit           Leave the simple CLI
  /clear                 Start a new session on the next message (history is retained)
  /model                 Show the selected model
  /reasoning             Show the selected model's reasoning level
  /context               Show the selected model's context window
  /status                Show Core, runtime, session, and learning status
  /server                Show the profile runtime status
  /config                Show how to configure the active profile
  /license               Show license information
  /logs                  Show the last turn's bounded human diagnostic summary
  /learning [status]     Show learning status
  /learning start        Start learning for this profile/model
  /learning finish       Finish learning for this profile/model
"""

_REQUIRED_CAPABILITIES = (
    REQUEST_STREAM,
    REQUEST_CANCEL,
    CORE_HEALTH,
    PROFILE_CATALOG,
    PROFILE_MANAGEMENT,
    MODEL_REGISTRY,
    RUNTIME_MANAGER,
    SETUP_V1,
    CHAT_V1,
    SESSION_RESUME,
    EVENT_REPLAY,
)


@dataclass(frozen=True, slots=True)
class ChatArguments:
    profile_alias: str
    request: str | None


@dataclass(slots=True)
class ActiveProfile:
    profile_id: ProfileId
    display_name: str
    command_alias: str
    model_id: str
    model_config: Mapping[str, object]
    visible_logging_mode: VisibleLoggingMode


def parse_arguments(arguments: Sequence[str]) -> ChatArguments:
    alias = "jarvis"
    request_parts: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--profile-alias":
            if request_parts or index + 1 >= len(arguments):
                raise ValueError("--profile-alias requires one value before the request")
            alias = arguments[index + 1]
            index += 2
            continue
        if argument.startswith("--profile-alias="):
            if request_parts:
                raise ValueError("--profile-alias must precede the request")
            alias = argument.partition("=")[2]
            index += 1
            continue
        if argument.startswith("-") and not request_parts:
            raise ValueError(f"unsupported option: {argument}")
        request_parts.extend(arguments[index:])
        break
    if not alias:
        raise ValueError("profile alias cannot be empty")
    request = " ".join(request_parts) if request_parts else None
    if request is not None and not request.strip():
        raise ValueError("request cannot be empty")
    return ChatArguments(alias, request)


class SimpleChatClient:
    def __init__(
        self,
        client: JarvisIpcClient,
        presenter: TerminalPresenter,
        profile: ActiveProfile,
    ) -> None:
        self.client = client
        self.presenter = presenter
        self.profile = profile
        self.session_id: str | None = None
        self.last_turn_id: str | None = None
        self.learning_status: str | None = None
        self.new_session = False

    @classmethod
    async def connect(
        cls, presenter: TerminalPresenter, alias: str, *, socket_path: Path | None = None
    ) -> SimpleChatClient:
        path = socket_path or resolve_xdg_paths().runtime / "core.sock"
        client = await JarvisIpcClient.connect_ready(
            path,
            required_capabilities=_REQUIRED_CAPABILITIES,
            client_name="jarvis-simple-cli",
        )
        try:
            resolved = await _result(
                client, "profiles.resolve_alias", payload={"command_alias": alias}
            )
            profile_wire = resolved.get("profile")
            if not isinstance(profile_wire, dict):
                raise RuntimeError("Core returned invalid profile")
            profile_id = ProfileId.parse(str(profile_wire["profile_id"]))
            await _complete_setup(client, presenter, profile_id)
            associations = await _result(client, "profiles.models.list", profile_id=profile_id)
            selected = _selected_association(associations)
            logging = await _result(
                client,
                "profiles.configuration.section.get",
                profile_id=profile_id,
                payload={"section": "visible-logging"},
            )
            mode = VisibleLoggingMode(str(logging.get("value")))
            profile = ActiveProfile(
                profile_id=profile_id,
                display_name=str(profile_wire.get("display_name", alias)),
                command_alias=str(profile_wire.get("command_alias", alias)),
                model_id=str(selected["model_id"]),
                model_config=_mapping(selected.get("config"), "model configuration"),
                visible_logging_mode=mode,
            )
            return cls(client, presenter, profile)
        except BaseException:
            await client.close()
            raise

    async def close(self) -> None:
        await self.client.close()

    async def show_startup(self) -> None:
        self.presenter.write(
            f"{display_text(self.profile.display_name)} "
            f"[{display_text(self.profile.command_alias)}]"
        )
        try:
            learning = await self._learning("status")
        except ClientOperationError as error:
            if error.code != "chat.not_found":
                raise
            self.learning_status = None
            self.presenter.write("Learning session will start with the first chat.")
        else:
            self._render_learning(learning, banner=True)

    async def submit(self, content: str) -> int:
        request_id = RequestId(uuid4())
        payload: dict[str, object] = {"content": content}
        if self.new_session:
            payload["new_session"] = True
        elif self.session_id is not None:
            payload["session_id"] = self.session_id
        renderer = StreamRenderer(self.presenter, self.profile.visible_logging_mode)
        events = self.client.request(
            "chat.submit",
            payload=payload,
            profile_id=self.profile.profile_id,
            request_id=request_id,
        )
        try:
            while True:
                try:
                    disconnected = await self._consume_events(events, renderer)
                except IpcError as error:
                    if error.code != "ipc.replay_unavailable":
                        raise
                    await self._show_authoritative_request_status(request_id)
                    return 1
                if not disconnected:
                    break
                resumed = await self._resume(request_id, renderer.state.last_sequence)
                if resumed is None:
                    return 1
                events = resumed
        except asyncio.CancelledError:
            try:
                result = await asyncio.shield(self.client.cancel(request_id))
                self.presenter.write(
                    f"Cancellation {display_text(result.get('outcome', 'requested'))}."
                )
            except (IpcError, OSError):
                self.presenter.write(
                    "Cancellation could not be confirmed; Core remains authoritative."
                )
            raise
        if renderer.state.terminal_count != 1:
            self.presenter.write("Core did not provide exactly one terminal outcome.")
            return 1
        self.new_session = False
        return 1 if renderer.state.terminal_error else 0

    async def _consume_events(
        self, events: AsyncIterator[dict[str, object]], renderer: StreamRenderer
    ) -> bool:
        async for event in events:
            if _is_disconnect(event):
                self.presenter.write("Core connection lost; reconnecting to authoritative work.")
                return True
            self._observe_chat_event(event)
            renderer.render(event)
        return False

    async def _resume(
        self, request_id: RequestId, after_sequence: int
    ) -> AsyncIterator[dict[str, object]] | None:
        previous = self.client
        try:
            resumed = await previous.resume()
        except (IpcError, OSError):
            self.presenter.write(
                "Reconnect unavailable; the request state could not be authoritatively retrieved."
            )
            return None
        await previous.close()
        self.client = resumed
        self.presenter.write("Reconnected; attaching to the existing request.")
        return resumed.attach(request_id, after_sequence=after_sequence)

    def _observe_chat_event(self, event: Mapping[str, object]) -> None:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            return
        event_type = event.get("event_type")
        if event_type == "response_started":
            self.session_id = _optional_text(payload.get("session_id"))
            self.last_turn_id = _optional_text(payload.get("turn_id"))
            status = _optional_text(payload.get("learning_status"))
            if status == "ACTIVE" and self.learning_status != "ACTIVE":
                self.presenter.write("Learning session is active for this profile and model.")
            self.learning_status = status
        elif event_type == "response_completed":
            self.session_id = _optional_text(payload.get("session_id")) or self.session_id
            self.last_turn_id = _optional_text(payload.get("turn_id")) or self.last_turn_id

    async def execute(self, command: SlashCommand) -> bool:
        name = command.name
        if name == "help":
            self.presenter.write(INTERACTIVE_HELP_TEXT.rstrip())
        elif name in {"quit", "exit"}:
            return False
        elif name == "clear":
            await _result(
                self.client,
                "chat.session.resolve",
                profile_id=self.profile.profile_id,
                payload={"model_id": self.profile.model_id},
            )
            self.session_id = None
            self.new_session = True
            self.last_turn_id = None
            self.presenter.write(
                "A new session will begin with your next message; history remains."
            )
        elif name == "model":
            selected = await self._selected_model()
            self.presenter.write(f"Selected model: {display_text(selected['model_id'])}")
        elif name == "reasoning":
            selected = await self._selected_model()
            config = _mapping(selected.get("config"), "model configuration")
            self.presenter.write(f"Reasoning: {display_text(config.get('reasoning', 'unknown'))}")
        elif name == "context":
            selected = await self._selected_model()
            config = _mapping(selected.get("config"), "model configuration")
            context_window = config.get("context_window", "unknown")
            if context_window == 0:
                self.presenter.write("Context window: Auto (model default)")
            else:
                self.presenter.write(f"Context window: {display_text(context_window)} tokens")
        elif name == "status":
            await self._show_status()
        elif name == "server":
            runtime = await _result(
                self.client, "profiles.runtime.status", profile_id=self.profile.profile_id
            )
            self.presenter.write(
                f"Runtime: {display_text(runtime.get('state', 'unknown'))}; "
                f"health={display_text(runtime.get('health', 'unknown'))}"
            )
        elif name == "config":
            await _result(self.client, "profiles.get", profile_id=self.profile.profile_id)
            self.presenter.write(
                f"Run jarvis-config and select {display_text(self.profile.display_name)}."
            )
        elif name == "license":
            self.presenter.write(_license_text())
        elif name == "logs":
            if self.last_turn_id is None:
                self.presenter.write("No turn is available for a diagnostic summary.")
            else:
                summary = await _result(
                    self.client,
                    "chat.diagnostics.summary",
                    profile_id=self.profile.profile_id,
                    payload={"turn_id": self.last_turn_id},
                )
                self._render_diagnostics(summary)
        elif name == "learning":
            await self._selected_model()
            action = command.arguments[0] if command.arguments else "status"
            try:
                learning = await self._learning(action)
            except ClientOperationError as error:
                if action == "status" and error.code == "chat.not_found":
                    self.presenter.write(
                        "Learning has not started; the first chat will activate it."
                    )
                else:
                    raise
            else:
                self._render_learning(learning, banner=False)
        return True

    async def _selected_model(self) -> Mapping[str, object]:
        associations = await _result(
            self.client, "profiles.models.list", profile_id=self.profile.profile_id
        )
        selected = _selected_association(associations)
        self.profile.model_id = str(selected["model_id"])
        self.profile.model_config = _mapping(selected.get("config"), "model configuration")
        return selected

    async def _learning(self, action: str) -> Mapping[str, object]:
        return await _result(
            self.client,
            f"chat.learning.{action}",
            profile_id=self.profile.profile_id,
            payload={"model_id": self.profile.model_id},
        )

    def _render_learning(self, learning: Mapping[str, object], *, banner: bool) -> None:
        status = display_text(learning.get("status", "unknown"))
        self.learning_status = str(learning.get("status"))
        prefix = "Learning session" if banner else "Learning"
        self.presenter.write(f"{prefix}: {status}")

    async def _show_status(self) -> None:
        await self._selected_model()
        health = await _result(self.client, "core.health")
        runtime = await _result(
            self.client, "profiles.runtime.status", profile_id=self.profile.profile_id
        )
        session = await _result(
            self.client,
            "chat.session.resolve",
            profile_id=self.profile.profile_id,
            payload={"model_id": self.profile.model_id},
        )
        try:
            learning = await self._learning("status")
            learning_status = learning.get("status", "unknown")
        except ClientOperationError as error:
            if error.code != "chat.not_found":
                raise
            learning_status = "not-started"
        self.presenter.write(
            f"Core: {display_text(health.get('state', 'unknown'))}; "
            f"runtime={display_text(runtime.get('state', 'unknown'))}; "
            f"session={display_text(session.get('session_id', 'none'))}; "
            f"learning={display_text(learning_status)}"
        )

    async def _show_authoritative_request_status(self, request_id: RequestId) -> None:
        try:
            status = await self.client.status(request_id)
        except (IpcError, OSError):
            self.presenter.write(
                "Replay is unavailable and Core could not provide authoritative request status."
            )
            return
        request = status.get("request")
        if not isinstance(request, dict):
            self.presenter.write("Core returned an invalid authoritative request status.")
            return
        self.presenter.write(
            "Replay is unavailable; authoritative Core request state: "
            f"{display_text(request.get('state', 'unknown'))}."
        )

    def _render_diagnostics(self, summary: Mapping[str, object]) -> None:
        items = summary.get("items")
        if not isinstance(items, list) or not items:
            self.presenter.write("No diagnostic summary is available for this turn.")
            return
        self.presenter.write("Diagnostic summary (human-only):")
        for item in items:
            if isinstance(item, dict):
                self.presenter.write(
                    f"- {display_text(item.get('event_type', 'event'))}: "
                    f"{display_text(item.get('summary', ''))}"
                )


async def run_chat(arguments: ChatArguments, presenter: TerminalPresenter) -> int:
    if arguments.request is None and not presenter.interactive:
        presenter.write("Interactive mode requires a terminal; pass a request for one-shot mode.")
        return EXIT_USAGE
    client = await SimpleChatClient.connect(presenter, arguments.profile_alias)
    try:
        await client.show_startup()
        if arguments.request is not None:
            try:
                command = parse_slash_command(arguments.request)
            except SlashCommandError as error:
                presenter.write(str(error))
                return EXIT_USAGE
            if command is not None:
                await client.execute(command)
                return 0
            return await client.submit(arguments.request)
        while True:
            entered = presenter.prompt_inline(client.profile.display_name).strip()
            if not entered:
                continue
            try:
                command = parse_slash_command(entered)
                if command is not None:
                    if not await client.execute(command):
                        return 0
                    continue
                await client.submit(entered)
            except SlashCommandError as error:
                presenter.write(str(error))
            except ClientOperationError as error:
                presenter.write(f"Operation failed safely ({display_text(error.code)}).")
    finally:
        await client.close()


def run_chat_sync(arguments: ChatArguments, presenter: TerminalPresenter) -> int:
    try:
        return asyncio.run(run_chat(arguments, presenter))
    except EOFError:
        # Closing stdin detaches this presentation client.  It must not imply
        # that authoritative Core-owned work was cancelled.
        return 0
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except OSError:
        presenter.write("jarvis: Jarvis Core is unavailable.")
        return 1
    except IpcError as error:
        presenter.write(f"jarvis: The Core connection failed safely ({display_text(error.code)}).")
        return 1
    except ClientOperationError as error:
        presenter.write(f"jarvis: The operation failed safely ({display_text(error.code)}).")
        return 1


def _selected_association(payload: Mapping[str, object]) -> Mapping[str, object]:
    associations = payload.get("associations")
    if not isinstance(associations, list):
        raise RuntimeError("Core returned invalid model associations")
    selected = [item for item in associations if isinstance(item, dict) and item.get("selected")]
    if len(selected) != 1 or not isinstance(selected[0].get("model_id"), str):
        raise ClientOperationError("model.not_selected", "error.model.not_selected")
    return selected[0]


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError(f"Core returned invalid {label}")
    return value


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _is_disconnect(event: Mapping[str, object]) -> bool:
    if event.get("type") != "error" or event.get("event_type") is not None:
        return False
    error = event.get("error")
    return isinstance(error, dict) and error.get("code") == "ipc.core_unavailable"


def _license_text() -> str:
    try:
        expression = metadata.metadata("jarvis-cli").get("License-Expression")
    except metadata.PackageNotFoundError:
        expression = None
    return f"Jarvis-CLI license: {display_text(expression or 'GPL-3.0-only')}"


async def _complete_setup(
    client: JarvisIpcClient, presenter: TerminalPresenter, profile_id: ProfileId
) -> None:
    state = await _result(client, "setup.start", profile_id=profile_id)
    while True:
        name = state.get("state")
        if name == "ready":
            return
        if name == "validating":
            presenter.write("Validating the local model runtime.")
            state = await _result(
                client,
                "setup.validate",
                profile_id=profile_id,
                payload=_setup_identity(state),
            )
            continue
        if name == "needs-discovery":
            presenter.write("Searching configured model directories for GGUF files.")
            state = await _setup_advance(client, profile_id, state, "discover", None)
            continue
        if not presenter.interactive:
            await _cancel_setup(client, profile_id, state)
            raise ClientOperationError("setup.input_required", "error.setup.input_required")
        if name == "needs-runtime-path":
            value = presenter.prompt("Path to llama-server (blank cancels)").strip()
            if not value:
                await _cancel_setup(client, profile_id, state)
                raise ClientOperationError("setup.cancelled", "error.setup.cancelled")
            state = await _setup_advance(client, profile_id, state, "runtime-path", value)
        elif name == "needs-model-directory":
            value = presenter.prompt("Directory containing GGUF models (blank cancels)").strip()
            if not value:
                await _cancel_setup(client, profile_id, state)
                raise ClientOperationError("setup.cancelled", "error.setup.cancelled")
            state = await _setup_advance(client, profile_id, state, "model-directory", value)
        elif name == "needs-model-selection":
            models = state.get("models")
            available = (
                [
                    item
                    for item in models
                    if isinstance(item, dict) and item.get("availability") == "available"
                ]
                if isinstance(models, list)
                else []
            )
            if not available:
                value = presenter.prompt(
                    "No usable GGUF found; add another model directory"
                ).strip()
                if not value:
                    await _cancel_setup(client, profile_id, state)
                    raise ClientOperationError("setup.cancelled", "error.setup.cancelled")
                state = await _setup_advance(client, profile_id, state, "model-directory", value)
                continue
            labels = [
                display_text(item.get("path", item.get("model_id", "model"))) for item in available
            ]
            choice = presenter.choose("Select a local model:", labels)
            if choice < 0:
                await _cancel_setup(client, profile_id, state)
                raise ClientOperationError("setup.cancelled", "error.setup.cancelled")
            state = await _setup_advance(
                client, profile_id, state, "select-model", available[choice]["model_id"]
            )
        elif name == "needs-essential-settings":
            reasoning = (
                presenter.prompt(
                    "Reasoning level (off/low/medium/high/max; default medium)"
                ).strip()
                or "medium"
            )
            context_text = presenter.prompt("Context window (blank or 0 for Auto)").strip()
            try:
                context_window = 0 if not context_text else int(context_text)
            except ValueError as error:
                raise ClientOperationError(
                    "setup.invalid_input", "error.setup.invalid_input"
                ) from error
            state = await _setup_advance(
                client,
                profile_id,
                state,
                "essential-settings",
                {"reasoning": reasoning, "context_window": context_window},
            )
        else:
            raise ClientOperationError("setup.failed", "error.setup.failed")


def _setup_identity(state: Mapping[str, object]) -> dict[str, object]:
    return {
        "session_token": state["session_token"],
        "expected_revision": state["revision"],
    }


async def _setup_advance(
    client: JarvisIpcClient,
    profile_id: ProfileId,
    state: Mapping[str, object],
    action: str,
    value: object,
) -> Mapping[str, object]:
    return await _result(
        client,
        "setup.advance",
        profile_id=profile_id,
        payload={**_setup_identity(state), "action": action, "value": value},
    )


async def _cancel_setup(
    client: JarvisIpcClient, profile_id: ProfileId, state: Mapping[str, object]
) -> None:
    await _result(
        client,
        "setup.cancel",
        profile_id=profile_id,
        payload=_setup_identity(state),
    )
