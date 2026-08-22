from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from jarvis.config.defaults import DefaultsRegistry, transition_persisted_defaults
from jarvis.foundation.errors import ConfigurationError
from jarvis.models.errors import InvalidRuntimeConfigurationError
from jarvis.models.models import ModelRuntimeConfig

pytestmark = pytest.mark.unit


def _valid_toml() -> str:
    return """
defaults_schema_version = 5
product_defaults_version = 6
[foundation_diagnostics]
total_bytes = 268435456
file_bytes = 8388608
event_bytes = 65536
text_bytes = 16384
max_depth = 8
max_container_entries = 100
max_closed_files = 32
retention_days = 30
[profile_defaults]
persona_text = "Persona"
profile_context_text = ""
accent_color = "#4fc3f7"
foreground_color = "#e6edf3"
background_color = "#0d1117"
waiting_messages = []
goodbye_messages = []
visible_logging_mode = "essential-minimum"
start_with_computer = false
[profile_defaults.permissions]
create = "allow"
copy = "allow"
read = "allow"
screen = "allow"
internet = "allow"
execute = "allow"
delete = "ask"
modify = "ask"
move = "ask"
[model_defaults]
reasoning = "medium"
context_window = 0
[model_defaults.runtime_config]
temperature = 0.8
top_p = 0.95
top_k = 40
min_p = 0.0
repeat_penalty = 1.1
gpu_layers = 0
threads = 1
batch_size = 2048
flash_attention = false
startup_timeout_seconds = 60
generation_timeout_seconds = 600
tool_timeout_seconds = 60
network_timeout_seconds = 30
shutdown_timeout_seconds = 30
llama_server_arguments = []
[model_defaults.scanner_limits]
max_directories = 32
max_path_bytes = 4096
max_depth = 16
max_directory_entries = 100000
max_candidates = 100000
metadata_budget_bytes = 16777216
max_metadata_entries = 8192
max_key_bytes = 256
max_display_string_bytes = 16384
max_array_payload_bytes = 16777216
max_array_elements = 1000000
max_metadata_payload_bytes = 16777216
[runtime_manager]
max_concurrent_runtimes = 2
max_pending_starts = 16
stream_capture_bytes = 1048576
event_retention_count = 1000
endpoint_allocation_attempts = 16
[chat]
max_message_bytes = 65536
max_partial_bytes = 262144
max_session_bytes = 8388608
max_diagnostic_bytes = 16777216
minimum_diagnostic_reservation_bytes = 4096
max_diagnostic_summary_bytes = 16384
max_context_contribution_bytes = 65536
max_provider_delta_bytes = 65536
max_sse_frame_bytes = 262144
max_sse_response_bytes = 67108864
max_queued_generations = 16
"""


def test_packaged_defaults_are_deterministic_and_exact() -> None:
    first = DefaultsRegistry.load_packaged().current()
    second = DefaultsRegistry.load_packaged().current()
    assert first == second
    assert first.defaults_schema_version == 5
    assert first.product_defaults_version == 6
    assert first.model_defaults.context_window == 0
    assert first.foundation_diagnostics.total_bytes == 256 * 1024 * 1024
    assert first.foundation_diagnostics.file_bytes == 8 * 1024 * 1024
    assert first.foundation_diagnostics.event_bytes == 64 * 1024
    assert first.foundation_diagnostics.text_bytes == 16 * 1024
    assert first.profile_defaults.visible_logging_mode == "essential-minimum"
    assert first.profile_defaults.permissions["delete"] == "ask"
    assert first.model_defaults.runtime_config["temperature"] == 0.8
    assert first.model_defaults.runtime_config["llama_server_arguments"] == ()
    assert first.runtime_manager.max_concurrent_runtimes == 2
    assert first.chat.max_queued_generations == 16


def test_defaults_snapshot_is_immutable() -> None:
    snapshot = DefaultsRegistry.load_packaged().current()
    with pytest.raises(FrozenInstanceError):
        snapshot.product_defaults_version = 2  # type: ignore[misc]


@pytest.mark.parametrize("value", [True, -1, 1_000_001])
def test_context_window_auto_domain_rejects_invalid_values(value: object) -> None:
    with pytest.raises(InvalidRuntimeConfigurationError):
        ModelRuntimeConfig(context_window=value)  # type: ignore[arg-type]


def test_defaults_transition_from_five_preserves_explicit_model_values() -> None:
    assert transition_persisted_defaults(
        {"context_window": 8192}, from_version=5, to_version=6
    ) == {"context_window": 8192}


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
        _valid_toml().replace("defaults_schema_version = 5", "defaults_schema_version = 1"),
        _valid_toml().replace("product_defaults_version = 6", "product_defaults_version = 1"),
    ],
)
def test_unsupported_versions_fail_closed(source: str) -> None:
    with pytest.raises(ConfigurationError) as caught:
        DefaultsRegistry.from_toml(source)
    assert caught.value.code == "defaults.unsupported_version"


def test_transition_requires_an_explicit_supported_version_path() -> None:
    original = {"setting": "value"}
    unchanged = transition_persisted_defaults(original, from_version=5, to_version=5)
    assert unchanged == original
    with pytest.raises(TypeError):
        unchanged["setting"] = "changed"  # type: ignore[index]
    with pytest.raises(ConfigurationError):
        transition_persisted_defaults(original, from_version=1, to_version=5)
    with pytest.raises(ConfigurationError):
        transition_persisted_defaults(original, from_version=5, to_version=1)


def test_future_quota_categories_are_not_present_in_foundation_defaults() -> None:
    source = _valid_toml() + "\n[chat_diagnostics]\ntotal_bytes = 1\n"
    with pytest.raises(ConfigurationError) as caught:
        DefaultsRegistry.from_toml(source)
    assert caught.value.safe_details["unknown"] == "chat_diagnostics"


def test_no_fictitious_profile_defaults_version_one_transition_exists() -> None:
    with pytest.raises(ConfigurationError) as caught:
        transition_persisted_defaults({}, from_version=1, to_version=5)
    assert caught.value.code == "defaults.unsupported_version"


@pytest.mark.parametrize(
    "source",
    [
        _valid_toml().replace('delete = "ask"', 'delete = "sometimes"'),
        _valid_toml().replace('accent_color = "#4fc3f7"', 'accent_color = "blue"'),
        _valid_toml().replace("start_with_computer = false", 'start_with_computer = "false"'),
        _valid_toml().replace('move = "ask"', ""),
    ],
)
def test_invalid_profile_defaults_fail_closed(source: str) -> None:
    with pytest.raises(ConfigurationError):
        DefaultsRegistry.from_toml(source)
