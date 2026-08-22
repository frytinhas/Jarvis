"""Strict parsing for M006B interactive presentation commands."""

from __future__ import annotations

import shlex
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SlashCommand:
    name: str
    arguments: tuple[str, ...]


class SlashCommandError(ValueError):
    pass


AUTHORIZED_COMMANDS = frozenset(
    {
        "help",
        "quit",
        "exit",
        "clear",
        "model",
        "reasoning",
        "context",
        "status",
        "server",
        "config",
        "license",
        "logs",
        "learning",
    }
)


def parse_slash_command(value: str) -> SlashCommand | None:
    stripped = value.strip()
    if not stripped.startswith("/"):
        return None
    try:
        parts = shlex.split(stripped)
    except ValueError as error:
        raise SlashCommandError("Malformed slash command.") from error
    if not parts or not parts[0].startswith("/") or parts[0] == "/":
        raise SlashCommandError("Malformed slash command.")
    name = parts[0][1:].casefold()
    if name not in AUTHORIZED_COMMANDS:
        raise SlashCommandError(f"Unknown command: /{name}")
    command = SlashCommand(name, tuple(parts[1:]))
    _validate(command)
    return command


def _validate(command: SlashCommand) -> None:
    if command.name == "learning":
        if command.arguments not in {(), ("status",), ("start",), ("finish",)}:
            raise SlashCommandError("Usage: /learning [status|start|finish]")
        return
    if command.arguments:
        raise SlashCommandError(f"Usage: /{command.name}")
