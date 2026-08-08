from __future__ import annotations

from pathlib import Path

from jarvis.agent.prompts import default_context_path, default_persona_path
from jarvis.settings import UserSettings
from jarvis.ui.waiting import default_waiting_messages_path


def ensure_private_resources(settings: UserSettings) -> None:
    """Create missing editable resources without ever replacing user content."""
    config_directory = settings.whitelist_path.expanduser().parent
    installation_home = (
        config_directory.parent.parent
        if config_directory.name == "jarvis" and config_directory.parent.name == ".config"
        else Path.home().resolve()
    )
    resources = (
        (settings.persona_path, default_persona_path().read_bytes()),
        (settings.context_path, default_context_path().read_bytes()),
        (settings.waiting_messages_path, default_waiting_messages_path().read_bytes()),
        (settings.blacklist_path, b"# path READ MODIFY CREATE DELETE EXECUTE\n"),
        (settings.whitelist_path, f"{installation_home}\n/mnt\n".encode()),
    )
    for path, content in resources:
        path = path.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        if not path.exists():
            path.write_bytes(content)
        if path.is_file():
            path.chmod(0o600)
