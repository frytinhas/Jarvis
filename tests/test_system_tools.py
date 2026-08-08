from pathlib import Path

from jarvis.tools.system import get_user_directories


def test_user_directories_reads_xdg_without_shell(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    config = tmp_path / "config"
    config.mkdir()
    (config / "user-dirs.dirs").write_text(
        'XDG_DOCUMENTS_DIR="$HOME/Documentos"\nXDG_DOWNLOAD_DIR="$HOME/Baixados"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))

    result = get_user_directories()

    assert result["home"] == str(tmp_path)
    assert result["directories"]["documents"][0] == str(tmp_path / "Documentos")
    assert result["directories"]["downloads"][0] == str(tmp_path / "Baixados")
