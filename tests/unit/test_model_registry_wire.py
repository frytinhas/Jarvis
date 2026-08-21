from __future__ import annotations

import pytest

from jarvis.ipc.server import _profile_model_config_from_wire
from jarvis.models.errors import InvalidRuntimeConfigurationError
from jarvis.models.models import ModelRuntimeConfig

pytestmark = pytest.mark.unit


def _wire_config(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = ModelRuntimeConfig().to_mapping()
    for key in ("temperature", "top_p", "min_p", "repeat_penalty"):
        value[key] = repr(value[key])
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    "decimal",
    ["nan", "inf", "-inf", "1e0", "+1.0", "01.0", ".5", "1.", "0.12345678901234567", "9" * 65],
)
def test_model_config_wire_rejects_noncanonical_or_unbounded_decimals(decimal: str) -> None:
    with pytest.raises(InvalidRuntimeConfigurationError):
        _profile_model_config_from_wire(_wire_config(temperature=decimal))


def test_model_config_wire_accepts_bounded_canonical_decimals_and_normalizes_negative_zero() -> (
    None
):
    parsed = _profile_model_config_from_wire(
        _wire_config(temperature="0.25", top_p="1.0", min_p="-0.0", repeat_penalty="1.1")
    )
    config = ModelRuntimeConfig.from_mapping(parsed)
    assert config.temperature == 0.25
    assert config.top_p == 1.0
    assert config.min_p == 0.0
    assert repr(config.min_p) == "0.0"


@pytest.mark.parametrize("kwargs", [{"reasoning": []}, {"llama_server_arguments": "--unsafe"}])
def test_runtime_config_rejects_malformed_domain_values_without_raw_type_errors(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(InvalidRuntimeConfigurationError):
        ModelRuntimeConfig(**kwargs)  # type: ignore[arg-type]
