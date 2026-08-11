from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from jarvis.config.defaults import DefaultsRegistry, transition_persisted_defaults
from jarvis.foundation.errors import ConfigurationError

pytestmark = pytest.mark.unit


def _valid_toml() -> str:
    return """
defaults_schema_version = 1
product_defaults_version = 1
[foundation_diagnostics]
total_bytes = 268435456
file_bytes = 8388608
event_bytes = 65536
text_bytes = 16384
max_depth = 8
max_container_entries = 100
max_closed_files = 32
retention_days = 30
"""


def test_packaged_defaults_are_deterministic_and_exact() -> None:
    first = DefaultsRegistry.load_packaged().current()
    second = DefaultsRegistry.load_packaged().current()
    assert first == second
    assert first.defaults_schema_version == 1
    assert first.product_defaults_version == 1
    assert first.foundation_diagnostics.total_bytes == 256 * 1024 * 1024
    assert first.foundation_diagnostics.file_bytes == 8 * 1024 * 1024
    assert first.foundation_diagnostics.event_bytes == 64 * 1024
    assert first.foundation_diagnostics.text_bytes == 16 * 1024


def test_defaults_snapshot_is_immutable() -> None:
    snapshot = DefaultsRegistry.load_packaged().current()
    with pytest.raises(FrozenInstanceError):
        snapshot.product_defaults_version = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "source",
    [
        _valid_toml().replace("retention_days = 30", ""),
        _valid_toml() + "unknown = 1\n",
        _valid_toml().replace("event_bytes = 65536", "event_bytes = -1"),
        _valid_toml().replace("event_bytes = 65536", "event_bytes = 'large'"),
    ],
)
def test_missing_unknown_and_invalid_values_fail_closed(source: str) -> None:
    with pytest.raises(ConfigurationError) as caught:
        DefaultsRegistry.from_toml(source)
    assert caught.value.code == "defaults.invalid"


@pytest.mark.parametrize(
    "source",
    [
        _valid_toml().replace("defaults_schema_version = 1", "defaults_schema_version = 2"),
        _valid_toml().replace("product_defaults_version = 1", "product_defaults_version = 2"),
    ],
)
def test_unsupported_versions_fail_closed(source: str) -> None:
    with pytest.raises(ConfigurationError) as caught:
        DefaultsRegistry.from_toml(source)
    assert caught.value.code == "defaults.unsupported_version"


def test_transition_requires_an_explicit_supported_version_path() -> None:
    original = {"setting": "value"}
    unchanged = transition_persisted_defaults(original, from_version=1, to_version=1)
    assert unchanged == original
    with pytest.raises(TypeError):
        unchanged["setting"] = "changed"  # type: ignore[index]
    with pytest.raises(ConfigurationError):
        transition_persisted_defaults(original, from_version=1, to_version=2)
    with pytest.raises(ConfigurationError):
        transition_persisted_defaults(original, from_version=3, to_version=1)


def test_future_quota_categories_are_not_present_in_foundation_defaults() -> None:
    source = _valid_toml() + "\n[chat_diagnostics]\ntotal_bytes = 1\n"
    with pytest.raises(ConfigurationError) as caught:
        DefaultsRegistry.from_toml(source)
    assert caught.value.safe_details["unknown"] == "chat_diagnostics"
