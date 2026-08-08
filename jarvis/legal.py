"""Legal notices displayed by the interactive interface."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path


COPYRIGHT_NOTICE = "Jarvis-CLI  Copyright (C) 2026  Jose Nunes"
STARTUP_LICENSE_NOTICE = (
    "This program comes with ABSOLUTELY NO WARRANTY. It is free software under the "
    "GNU GPL v3; you may redistribute it under certain conditions. Type /license for details."
)
LICENSE_FALLBACK = """\
Jarvis-CLI is free software: you can redistribute it and/or modify it under the terms
of version 3 of the GNU General Public License, as published by the Free Software
Foundation.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.

The complete license text should accompany this distribution in the LICENSE file.
It is also available at <https://www.gnu.org/licenses/gpl-3.0.html>.
"""


def license_text() -> str:
    """Return the bundled GPL text, including from an installed wheel."""
    source_license = Path(__file__).resolve().parent.parent / "LICENSE"
    candidates = [source_license]
    try:
        distribution = metadata.distribution("jarvis-local")
        candidates.extend(
            distribution.locate_file(entry)
            for entry in distribution.files or ()
            if entry.name == "LICENSE"
        )
    except metadata.PackageNotFoundError:
        pass

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
    return LICENSE_FALLBACK
