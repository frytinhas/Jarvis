from pathlib import Path

import tomllib

from jarvis.legal import license_text


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_package_declares_gpl_v3_only_and_bundles_license() -> None:
    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["license"] == "GPL-3.0-only"
    assert metadata["project"]["license-files"] == ["LICENSE"]
    assert "GNU GENERAL PUBLIC LICENSE" in license_text()


def test_administrative_install_includes_license() -> None:
    setup = (PROJECT_ROOT / "Setup.sh").read_text(encoding="utf-8")

    assert '"$PROJECT_DIR/LICENSE" "$root_stage/"' in setup
