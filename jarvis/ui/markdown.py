from __future__ import annotations

import re

from jarvis.ui.theme import Theme


_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INLINE = re.compile(r"(`[^`\n]+`|\*\*[^*\n]+\*\*)")


def sanitize_terminal_text(text: str) -> str:
    return _CONTROL.sub("", _ANSI.sub("", text))


def _inline(text: str, theme: Theme) -> str:
    pieces: list[str] = []
    position = 0
    for match in _INLINE.finditer(text):
        pieces.append(text[position:match.start()])
        token = match.group(0)
        if token.startswith("`"):
            pieces.append(theme.paint(token[1:-1], "code"))
        else:
            pieces.append(theme.paint(token[2:-2], "bold", strong=True))
        position = match.end()
    pieces.append(text[position:])
    return "".join(pieces)


def render_markdown(text: str, theme: Theme) -> str:
    clean = sanitize_terminal_text(text)
    rendered: list[str] = []
    in_code = False
    for raw_line in clean.splitlines():
        stripped = raw_line.lstrip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            rendered.append(theme.paint(raw_line, "code"))
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            rendered.append(theme.paint(heading.group(2), "heading", strong=True))
            continue
        bullet = re.match(r"^(\s*)([-*+]\s+)(.*)$", raw_line)
        if bullet:
            marker = theme.paint("• ", "accent", strong=True)
            rendered.append(f"{bullet.group(1)}{marker}{_inline(bullet.group(3), theme)}")
            continue
        rendered.append(_inline(raw_line, theme))
    return "\n".join(rendered)
