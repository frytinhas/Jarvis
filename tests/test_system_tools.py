from pathlib import Path

from jarvis.tools.system import _parse_pci_ids, get_system_info, get_user_directories


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


def test_system_info_has_grounded_hardware_sections() -> None:
    result = get_system_info()

    assert result["cpu"]["model"]
    assert result["cpu"]["logical_cpus"] >= 1
    assert result["memory"]["total_bytes"] is None or result["memory"]["total_bytes"] > 0
    assert result["os"]["kernel"]
    assert "gpus" in result
    assert result["storage"]["root"]["total_bytes"] > 0


def test_pci_parser_prefers_exact_subsystem_name() -> None:
    pci_ids = """1002  Advanced Micro Devices, Inc. [AMD/ATI]
\t744c  Navi 31 [Radeon RX 7900 XT/7900 XTX/7900 GRE]
\t\t1eae 7901  Radeon RX 7900 XT Exact Board
"""

    vendor, model, exact = _parse_pci_ids(pci_ids, "1002", "744c", "1eae", "7901")

    assert vendor.startswith("Advanced Micro Devices")
    assert model == "Radeon RX 7900 XT Exact Board"
    assert exact is True


def test_pci_parser_keeps_family_name_when_subsystem_is_unknown() -> None:
    pci_ids = """1002  AMD
\t744c  Navi 31 [Radeon RX 7900 XT/7900 XTX/7900 GRE]
"""

    _, model, exact = _parse_pci_ids(pci_ids, "1002", "744c", "ffff", "ffff")

    assert "7900 XT/7900 XTX" in model
    assert exact is False
