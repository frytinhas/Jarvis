from __future__ import annotations

from jarvis.hardware import DEFAULT_CONTEXT_SIZE, detect_vram_mib, recommended_context_size


def test_recommended_context_uses_half_vram_and_rounds_to_nearest_step() -> None:
    assert recommended_context_size(12 * 1024) == 6144
    assert recommended_context_size(6144) == 3072
    assert recommended_context_size(1024) == 1024


def test_recommended_context_uses_safe_fallback_without_detected_vram(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("jarvis.hardware.detect_vram_mib", lambda: None)

    assert recommended_context_size() == DEFAULT_CONTEXT_SIZE


def test_detected_vram_uses_the_largest_gpu(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("jarvis.hardware._nvidia_vram_mib", lambda: [6144, 12288])
    monkeypatch.setattr("jarvis.hardware._drm_vram_mib", lambda: [8192])

    assert detect_vram_mib() == 12288
