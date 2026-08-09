<p align="center"><img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="140"></p>

# Jarvis-CLI

A local Linux assistant powered by GGUF models served by `llama.cpp`. The model only plans: files, processes, memory, and system access are available exclusively through validated tools, path policy, confirmation, and auditing.

For a quick start, see the [simple guide](README.simple.md). Português: [README.pt-BR.md](README.pt-BR.md).

## Installation

Requirements: Linux, Python 3.12+, `curl`, and an instruct/chat GGUF model. The automatic installer officially supports Debian, Ubuntu, and derivatives.

```bash
git clone https://github.com/frytinhas/Jarvis-CLI.git
cd Jarvis-CLI
bash Setup.sh
```

Setup never calls `sudo` and installs only for the current user:

| Item | Default location |
| --- | --- |
| Application and venv | `~/.local/share/jarvis/app` |
| Commands | `~/.local/bin` |
| Configuration | `~/.config/jarvis` |
| State, logs, and audit | `~/.local/state/jarvis` |

User-scoped dependencies are prepared locally. If Python, a compiler, or another system package is missing, Setup explains what must be installed. When already running as root, it warns, uses `/root`, and may install apt packages directly; it creates no global copy and changes no other user. A normal installation must not be run through `sudo`: an UID or HOME different from its owner is rejected.

Running Setup again offers repair with retained data or a clean reinstall for the current user only. Administrative copies left by older versions are not modified.

## Configuration and use

Setup opens the configurator. To open it later:

```bash
jarvis-config
```

Choose the GGUF, context, reasoning, name, behavior, timeouts, permissions, memory, activity panel, and appearance. The strictly validated XML lives at `~/.config/jarvis/config.xml` with mode `0600`; invalid configuration stops startup. `jarvis-config --a` opens the XML in Nano.

```bash
jarvis
jarvis "list the files in this directory"
jarvis --r 3 "analyze this project"
```

`--r` accepts `-1` (configured), `0` (Off), `1` (Low), `2` (Medium), `3` (High), and `4` (Max). The initial default is Off. The configured reasoning level also controls template thinking: level `0` disables it and levels `1` through `4` enable it. Changing between Off and an active level with `/reasoning` offers to restart the server so the template change is applied.

| Local command | Purpose |
| --- | --- |
| `/help` | Lists commands and options. |
| `/reasoning off\|low\|medium\|high\|max` | Changes and saves reasoning. |
| `/model` | Selects another GGUF. |
| `/context [tokens\|reset]` | Shows or changes model context. |
| `/permissions [category decision]` | Shows or changes global policy. |
| `/config` | Shows the current summary. |
| `/clear` | Clears the terminal while keeping chat context. |
| `/license` | Displays the complete GPL. |
| `/exit`, `/sair` | Closes only the chat. |
| `/quit` | Closes chat and stops the server after background memory work finishes. |

`Ctrl+C` cancels only the current generation or execution. `jarvis --full-stop` stops a managed server kept in the background.

## Tools and security

Jarvis has no generic shell tool. Local read requests use real tools; without an explicit target, an unambiguous reference from the visible current conversation is used, otherwise the invocation directory is the default. Commands printed by the model are never executed.

| Risk | Default | Examples |
| --- | --- | --- |
| `READ` | `ALLOW` | List, read, search, processes, and hardware. |
| `CREATE` | `ALLOW` | Create a file or directory. |
| `MODIFY` | `CONFIRM` | Write, append, move, or rename. |
| `DELETE` | `CONFIRM` | Delete a file or empty directory. |
| `EXECUTE` | `ALLOW` | Run an explicit `.sh` or binary path. |
| `PRIVILEGED` | fixed `DENY` | Privileged actions are never offered to the model. |

Every call passes through the registry, Pydantic schema, canonicalization, policy, revalidation, and audit. Confirmations authorize one exact action and expire. Symlinks, sources, destinations, and working directories receive policy; `/`, critical areas, and the application directory remain protected.

`Whitelist.txt` defines accessible roots. `Blacklist.txt` can only restrict policy, with five positions: `READ MODIFY CREATE DELETE EXECUTE`. `0` denies, `1` confirms, `2` allows, and `-` inherits. Example: `~/Projects 21202`. A missing or invalid file closes all path-based tools.

`execute_file` uses `shell=False`, separate arguments, a timeout, and an explicit path. It blocks setuid/setgid, privilege elevation, inline evaluation, and known critical operations. The user's original intent must authorize execution.

If the server cannot construct structured tool grammar, Jarvis does not retry the local request without tools or invent data. The failure is associated with that GGUF; returning to the model shows one warning and starts with tools enabled. The terminal may disable them for the current session only.

## Memory, customization, and server

| Resource | Default location |
| --- | --- |
| Persona and context | `~/.config/jarvis/Persona.md`, `Context.md` |
| Waiting and goodbye messages | `WaitingMessages.txt`, `GoodbyeMessages.txt` |
| Path rules | `Whitelist.txt`, `Blacklist.txt` |
| Conversations | `~/.local/state/jarvis/logs/conversations.db` |
| Compact profile notes | `~/.config/jarvis/jarvis-notes` |
| Sensitive audit log | `~/.local/state/jarvis/audit.db` |

Memory, persona, context, files, and tool results are untrusted data and never grant authorization. Raw internal tool results do not enter the transcript. Retention, size, panel detail, and server persistence are configurable. Data is not encrypted and must not contain credentials.

The launcher uses user systemd when available and its own fallback otherwise. Only servers started or managed by Jarvis are stopped. A remote OpenAI-compatible endpoint may be configured; prompts and context sent there are then no longer strictly local.

## Removal

```bash
jarvis --remove  # keep configuration, conversations, and audit
jarvis --purge   # also remove standard local data
```

Confirmation requires `jarvis remove` or `jarvis purge`. Removal affects only the current user, never asks for sudo, preserves the source clone, and does not automatically delete an audit database configured outside standard paths.

## License and disclaimer

Copyright (C) 2026 Jose Nunes. Licensed under [GPL-3.0-only](LICENSE). Use `/license` for the full text.

This is experimental software supplied without warranty. Review permissions, paths, and confirmations before allowing changes or execution; you are responsible for the selected model, endpoint, and authorized actions.
