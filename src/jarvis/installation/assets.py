"""Deterministic M006C dispatcher and systemd-user asset rendering."""

from __future__ import annotations

import shlex
from pathlib import Path

from jarvis.installation.paths import InstallationPaths

FIXED_COMMANDS = ("jarvis", "jarvis-config", "jarvis-help", "jarvis-manage")


def rendered_assets(paths: InstallationPaths) -> dict[Path, tuple[str, int, str]]:
    python = shlex.quote(str(paths.private_python))
    assets: dict[Path, tuple[str, int, str]] = {}
    for command in FIXED_COMMANDS:
        body = f'#!/bin/sh\nset -eu\nexec {python} -m jarvis.dispatch {shlex.quote(command)} "$@"\n'
        assets[paths.dispatchers / command] = (f"dispatcher:{command}", 0o755, body)
    assets[paths.systemd_user / "jarvisd.socket"] = (
        "systemd:socket",
        0o600,
        """[Unit]
Description=Jarvis Core IPC socket

[Socket]
ListenStream=%t/jarvis-cli/core.sock
SocketMode=0600
DirectoryMode=0700
FileDescriptorName=jarvis-core
Service=jarvisd.service

[Install]
WantedBy=sockets.target
""",
    )
    assets[paths.systemd_user / "jarvisd.service"] = (
        "systemd:service",
        0o600,
        f"""[Unit]
Description=Jarvis Core
Requires=jarvisd.socket
After=jarvisd.socket
StartLimitIntervalSec=30s
StartLimitBurst=3

[Service]
Type=simple
ExecStart={python} -m jarvis.core --socket-activation
Restart=on-failure
RestartSec=1s
NoNewPrivileges=yes

""",
    )
    return assets
