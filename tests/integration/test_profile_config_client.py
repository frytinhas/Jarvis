from __future__ import annotations

import asyncio
import io
from collections.abc import AsyncIterator, Mapping
from typing import Any

import pytest

from jarvis.cli import application
from jarvis.cli.presenter import TerminalPresenter
from jarvis.ipc.client import JarvisIpcClient
from jarvis.ipc.models import PROFILE_CATALOG, PROFILE_MANAGEMENT, REQUEST_STREAM

pytestmark = pytest.mark.integration


class _TtyInput(io.StringIO):
    def isatty(self) -> bool:
        return True


class _TtyOutput(io.StringIO):
    def isatty(self) -> bool:
        return True


class _FakeClient:
    required: tuple[str, ...] = ()
    operations: list[str] = []
    profiles: list[dict[str, object]] = [
        {
            "profile_id": "10000000-0000-4000-8000-000000000001",
            "kind": "jarvis",
            "display_name": "Jarvis",
            "command_alias": "jarvis",
            "identity_revision": 1,
        }
    ]

    @classmethod
    async def connect(cls, _path: object, **kwargs: Any) -> _FakeClient:
        cls.required = tuple(kwargs["required_capabilities"])
        cls.operations = []
        cls.profiles = [dict(cls.profiles[0])]
        return cls()

    async def request(
        self, operation: str, *, payload: Mapping[str, object] | None = None, **_kwargs: Any
    ) -> AsyncIterator[dict[str, object]]:
        self.operations.append(operation)
        result: dict[str, object]
        if operation == "profiles.list":
            result = {"profiles": self.profiles}
        elif operation == "profiles.create":
            assert payload is not None
            profile = {
                "profile_id": "20000000-0000-4000-8000-000000000001",
                "kind": "standard",
                "display_name": payload["display_name"],
                "command_alias": "work",
                "identity_revision": 1,
            }
            self.profiles.append(profile)
            result = {"profile": profile}
        else:
            raise AssertionError(operation)
        yield {
            "type": "event",
            "event_type": "request.completed",
            "terminal": True,
            "payload": result,
        }

    async def close(self) -> None:
        return None


def test_profile_first_create_flow_requires_m003_capabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target: Any = application
    monkeypatch.setattr(target, "JarvisIpcClient", _FakeClient)
    output = _TtyOutput()
    presenter = TerminalPresenter(stdin=_TtyInput("2\nWork\n0\n"), stdout=output)
    assert asyncio.run(application.run_configuration(presenter)) == 0
    assert _FakeClient.operations == ["profiles.list", "profiles.create", "profiles.list"]
    assert set(_FakeClient.required) == {REQUEST_STREAM, PROFILE_CATALOG, PROFILE_MANAGEMENT}
    transcript = output.getvalue()
    assert transcript.index("Select a profile") < transcript.index("Created Work (work).")


def test_non_tty_exits_usage_without_connecting(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_connect(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("non-TTY must not connect to Core")

    monkeypatch.setattr(JarvisIpcClient, "connect", fail_connect)
    presenter = TerminalPresenter(stdin=io.StringIO(), stdout=io.StringIO())
    assert asyncio.run(application.run_configuration(presenter)) == application.EXIT_USAGE


def test_terminal_error_event_becomes_a_safe_client_operation_error() -> None:
    class _ErrorClient:
        async def request(
            self, *_args: object, **_kwargs: object
        ) -> AsyncIterator[dict[str, object]]:
            yield {
                "type": "event",
                "event_type": "error",
                "terminal": True,
                "error": {
                    "code": "profile.protected",
                    "message_key": "error.profile.protected",
                },
            }

    with pytest.raises(application.ClientOperationError) as caught:
        asyncio.run(application._result(_ErrorClient(), "profiles.delete.preview"))  # type: ignore[arg-type]
    assert caught.value.code == "profile.protected"
