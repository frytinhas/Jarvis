from __future__ import annotations

import pytest

from jarvis.manage.__main__ import _config_payload, main

pytestmark = pytest.mark.unit


def test_management_help_is_local_and_requires_no_core(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "Jarvis Management" in output
    assert "runtime-update" in output
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0


def test_management_config_adapts_only_protocol_decimal_fields() -> None:
    value = {
        "temperature": 0.25,
        "top_p": 1,
        "min_p": 0.0,
        "repeat_penalty": 1.1,
        "context_window": 8192,
        "reasoning": "high",
    }
    assert _config_payload(value) == {
        **value,
        "temperature": "0.25",
        "min_p": "0.0",
        "repeat_penalty": "1.1",
    }
    assert _config_payload([0.5]) == [0.5]
