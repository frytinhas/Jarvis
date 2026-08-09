from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_setup_is_local_and_never_invokes_sudo() -> None:
    setup = (PROJECT_ROOT / "Setup.sh").read_text(encoding="utf-8")

    assert "sudo" not in setup
    assert "/usr/local" not in setup
    assert 'APP_DIR="$DATA_DIR/app"' in setup
    assert 'LOCAL_BIN="$INSTALL_HOME/.local/bin"' in setup
    assert "INSTALL_UID=%s" in setup
    assert '"$APP_DIR/.venv/bin/python" -P -m jarvis.installer' in setup
    assert '"$APP_DIR/.venv/bin/python" -P -m jarvis.runtime' in setup


def test_root_setup_warns_and_uses_direct_package_manager() -> None:
    setup = (PROJECT_ROOT / "Setup.sh").read_text(encoding="utf-8")

    assert "Setup está sendo executado como root" in setup
    assert "apt-get update" in setup
    assert "apt-get install" in setup
