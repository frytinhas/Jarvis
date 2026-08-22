from __future__ import annotations

import sys

import pytest

from jarvis.cli import __main__ as cli_main
from jarvis.cli import application, chat_application
from jarvis.cli.application import EXIT_USAGE, HELP_TEXT
from jarvis.cli.chat_application import CHAT_HELP_TEXT, ChatArguments, parse_arguments
from jarvis.cli.presenter import TerminalPresenter

pytestmark = pytest.mark.unit


def test_help_is_local_and_declares_logical_aliases_only() -> None:
    assert "never starts a model" in HELP_TEXT
    assert "not commands yet" in HELP_TEXT
    assert EXIT_USAGE == 64


@pytest.mark.parametrize("flag", ["-h", "--h", "--help"])
def test_config_help_flags_render_without_running_client(
    flag: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["jarvis-config", flag])
    monkeypatch.setattr(cli_main, "run_sync", lambda _presenter: pytest.fail("started client"))
    cli_main.config_main()
    assert "Usage: jarvis-config" in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["-h", "--h", "--help"])
def test_chat_help_flags_are_local(
    flag: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["python -m jarvis.cli", flag])
    monkeypatch.setattr(
        cli_main, "run_chat_sync", lambda *_args: pytest.fail("started chat client")
    )
    cli_main.main()
    assert "python -m jarvis.cli" in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        ["--profile-alias", "work", "--help"],
        ["--profile-alias=work", "--h"],
    ],
)
def test_alias_help_is_local(
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["python -m jarvis.cli", *arguments])
    monkeypatch.setattr(
        cli_main, "run_chat_sync", lambda *_args: pytest.fail("started chat client")
    )
    cli_main.main()
    assert "python -m jarvis.cli" in capsys.readouterr().out


def test_chat_argument_dispatch_is_default_or_core_alias_and_one_shot() -> None:
    assert parse_arguments([]) == ChatArguments("jarvis", None)
    assert parse_arguments(["olá"]) == ChatArguments("jarvis", "olá")
    assert parse_arguments(["--profile-alias", "work"]) == ChatArguments("work", None)
    assert parse_arguments(["--profile-alias=work", "olá", "mundo"]) == ChatArguments(
        "work", "olá mundo"
    )
    assert "Core" in CHAT_HELP_TEXT


@pytest.mark.parametrize(
    "arguments",
    [
        ["--profile-alias"],
        ["--profile-alias="],
        ["--unknown"],
    ],
)
def test_chat_argument_errors_fail_before_core(arguments: list[str]) -> None:
    with pytest.raises(ValueError):
        parse_arguments(arguments)


def test_chat_eof_detaches_without_reporting_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def detached(_arguments: ChatArguments, _presenter: TerminalPresenter) -> int:
        raise EOFError

    monkeypatch.setattr(chat_application, "run_chat", detached)

    assert chat_application.run_chat_sync(ChatArguments("jarvis", None), TerminalPresenter()) == 0


def test_jarvis_help_is_local(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["jarvis-help"])
    cli_main.help_main()
    assert "python -m jarvis.cli" in capsys.readouterr().out


def test_ctrl_c_and_eof_exit_130(monkeypatch: pytest.MonkeyPatch) -> None:
    for exception in (KeyboardInterrupt(), EOFError()):

        async def interrupted(
            _presenter: TerminalPresenter, active: BaseException = exception
        ) -> int:
            raise active

        monkeypatch.setattr(application, "run_configuration", interrupted)
        assert application.run_sync(TerminalPresenter()) == application.EXIT_INTERRUPTED


def test_safe_error_rendering_never_includes_raw_details() -> None:
    error = application.ClientOperationError(
        "profile.concurrent_modification", "error.profile.concurrent_modification"
    )
    rendered = application._safe_error_message(error)
    assert rendered == "The profile changed. Select it again and retry."
    assert "traceback" not in rendered.casefold()
