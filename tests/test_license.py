from pathlib import Path

import tomllib

from jarvis.legal import consume_license_notice, license_text, schedule_license_notice


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_package_declares_gpl_v3_only_and_bundles_license() -> None:
    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["license"] == "GPL-3.0-only"
    assert metadata["project"]["license-files"] == ["LICENSE"]
    assert "GNU GENERAL PUBLIC LICENSE" in license_text()


def test_local_install_includes_license() -> None:
    setup = (PROJECT_ROOT / "Setup.sh").read_text(encoding="utf-8")

    assert '"$SOURCE_DIR/pyproject.toml" "$SOURCE_DIR/LICENSE"' in setup


def test_license_notice_is_consumed_once(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("HOME", str(tmp_path))
    schedule_license_notice()
    assert consume_license_notice()
    assert not consume_license_notice()
