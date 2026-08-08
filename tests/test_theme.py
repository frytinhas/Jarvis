from __future__ import annotations

from io import StringIO
from pathlib import Path

from jarvis.settings import ColorMode
from jarvis.ui.markdown import render_markdown
from jarvis.ui.theme import DEFAULT_COLORS, Theme, ensure_colors_file


def test_colors_file_is_created_and_repairs_only_invalid_values(tmp_path: Path) -> None:
    path = tmp_path / "colors.toml"
    colors = ensure_colors_file(path)
    assert colors == DEFAULT_COLORS
    payload = path.read_text(encoding="utf-8")
    payload = payload.replace('#ff8700"', '#123AbC"', 1)
    payload = payload.replace('error = "#ff5f5f"', 'error = "orange"')
    path.write_text(payload.replace('muted = "#8a8a8a"\n', ''), encoding="utf-8")

    repaired = ensure_colors_file(path)

    assert repaired["primary"] == "#123AbC"
    assert repaired["error"] == DEFAULT_COLORS["error"]
    assert repaired["muted"] == DEFAULT_COLORS["muted"]
    assert '#123AbC' in path.read_text(encoding="utf-8")


def test_malformed_theme_salvages_valid_assignments(tmp_path: Path) -> None:
    path = tmp_path / "colors.toml"
    path.write_text('primary = "#102030"\nbroken = [\n', encoding="utf-8")

    assert ensure_colors_file(path)["primary"] == "#102030"


def test_markdown_renderer_highlights_safe_markup_and_strips_injected_ansi() -> None:
    theme = Theme(DEFAULT_COLORS, True)
    rendered = render_markdown("# Título\n**forte** e `código` \x1b[31mruim", theme)

    assert "\x1b[38;2" in rendered
    assert "\x1b[31m" not in rendered
    assert "**" not in rendered
    assert "`" not in rendered


def test_auto_colors_respect_no_color(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("NO_COLOR", "1")
    assert not Theme.load(ColorMode.AUTO, stream=StringIO(), path=tmp_path / "colors.toml").enabled
