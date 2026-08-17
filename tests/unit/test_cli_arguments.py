from __future__ import annotations

import sys

import pytest

from jarvis.cli import __main__ as cli_main
from jarvis.cli import application
from jarvis.cli.application import EXIT_USAGE, HELP_TEXT
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
    cli_main.main()
    assert "Usage: jarvis-config" in capsys.readouterr().out


def test_jarvis_help_is_local(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["jarvis-help"])
    cli_main.help_main()
    assert "Usage: jarvis-config" in capsys.readouterr().out


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
