# Jarvis-CLI technical guide

Jarvis is a Linux CLI assistant built around a GGUF model served by `llama.cpp`. The LLM plans and writes responses; it does not receive direct operating-system access. All local actions cross validated tools, the permission policy, path policy when applicable, confirmation, revalidation, and SQLite audit logging.

Main guide: [README.md](README.md). Português: [README.technical.pt-BR.md](README.technical.pt-BR.md).

## Installation and profiles

Requirements are Linux, Python 3.12+, `curl`, and an instruct/chat GGUF. Run the installer from a clone as the target user:

```bash
bash Setup.sh
```

Setup never escalates a normal-user installation. It installs the application and virtual environment in `~/.local/share/jarvis/app`, commands in `~/.local/bin`, configuration below `~/.config/jarvis`, and state below `~/.local/state/jarvis`. If a compatible `llama`/`llama-server` is unavailable, it clones and builds `llama.cpp` for CPU use. Missing system packages are reported for normal users; when Setup is deliberately run as root, it warns and confines the installation to `/root`.

The configurator discovers GGUF files, creates one named profile per model, assigns a local port, and creates the matching command in `~/.local/bin`. Re-run it with:

```bash
jarvis-config
jarvis-config --a  # edit the active profile XML in nano
```

Profiles live in `~/.config/jarvis/profiles/<profile>/`; profile state lives in `~/.local/state/jarvis/profiles/<profile>/`. The XML is strictly validated and written with private permissions. Invalid configuration stops startup rather than silently applying defaults.

Running Setup again offers repair while retaining user data, or a clean reinstall for that user. It does not modify the source clone.

## Operation

Use the profile command selected during configuration:

```bash
jarvis
jarvis "show the current directory"
jarvis --r 2 "summarize this project"
jarvis --full-stop
jarvis --full-stop-all
```

`--r N` accepts `0` through `4` for Off, Low, Medium, High, and Max reasoning. The configured default is used when `--r` is omitted. The launcher starts the profile's `llama-server` through `systemd --user` when available and uses a managed fallback otherwise. It only stops servers it started or manages.

| Chat command | Effect |
| --- | --- |
| `/help` | Shows the local command reference. |
| `/reasoning off|low|medium|high|max` | Saves the reasoning level; a template-mode change can request a server restart. |
| `/model [profile]` | Lists profiles or switches to one. |
| `/context [tokens|reset]` | Shows or changes context; token values must be positive multiples of 1024. |
| `/permissions [risk decision]` | Shows or changes global permissions. |
| `/config` | Shows the active profile summary. |
| `/learning` and `/finish` | Manage the private interactive learning context. |
| `/clear` | Clears the terminal without clearing chat context. |
| `/license` | Displays GPL-3.0. |
| `/exit` or `/sair` | Closes the chat. |
| `/quit` | Closes the chat and requests server shutdown after memory work. |

The editable profile resources are `Persona.md`, `Context.md`, `WaitingMessages.txt`, `GoodbyeMessages.txt`, `Whitelist.txt`, `Blacklist.txt`, and `LearningContext.md`. Use the respective CLI options such as `jarvis --persona`, `jarvis --context`, and `jarvis --blacklist` to open them in Nano.

## Tools and security model

There is no generic shell tool. Registered tools provide directory listing, bounded text reads, file metadata/search, processes, system information, current/user directories, file and directory creation, writing/appending/moving/renaming, deletion of files or empty directories, and execution of an explicit `.sh` file or executable. Conversation-history search is available only when memory storage is configured.

| Risk | Default decision | Examples |
| --- | --- | --- |
| `READ` | `ALLOW` | inspect files, search, processes, hardware |
| `CREATE` | `ALLOW` | create a file or directory |
| `MODIFY` | `CONFIRM` | write, append, move, rename |
| `DELETE` | `CONFIRM` | delete a file or empty directory |
| `EXECUTE` | `ALLOW` | run an explicit file path |
| `PRIVILEGED` | fixed `DENY` | privileged system operations |

The five configurable risks can be changed through `/permissions` or the configurator. A confirmation authorizes one exact pending action, expires, and is consumed once. `execute_file` uses separate arguments with `shell=False`; it requires an explicit path and user intent, and rejects privilege escalation, inline evaluation, setuid/setgid executables, and selected destructive operations.

`Whitelist.txt` optionally limits path tools to listed absolute roots. `Blacklist.txt` can only make the global policy stricter. Each non-comment line has an absolute (or `~`-based) path and one to five codes in this order: `READ MODIFY CREATE DELETE EXECUTE`; `0` denies, `1` confirms, `2` allows, and `-` leaves that position unchanged. Example:

```text
~/Projects 21202
```

An absent, unreadable, or invalid path-policy file closes path-based tools. Paths are canonicalized and paths behind symlinks, sources, destinations, parent directories, and execution working directories are checked. Critical system areas, Jarvis configuration/state, and non-read access to the source project remain protected.

Files, persona/context text, model output, memory, and tool output are untrusted data. They cannot alter policy or authorize an action. A model failure to make structured tool calls is reported instead of being replaced by invented local information.

## Data, privacy, and removal

Conversation logs, runtime logs, audit records, and runtime metadata are held under the profile's state directory. Profile customization and compact notes reside in the profile configuration directory. Retention and size limits are configurable; data is not encrypted, so do not put credentials in prompts, persona files, or logs.

Jarvis is local by default. Configuring an external OpenAI-compatible endpoint means prompts and context sent to that endpoint are no longer local.

```bash
jarvis --remove  # keep configuration and state
jarvis --purge   # remove standard configuration and state too
```

The uninstall flow requires the exact phrase `jarvis remove` or `jarvis purge`, applies only to the current user, removes managed user services and commands, and keeps the source checkout. An audit database configured outside Jarvis's standard state path is not removed automatically.

## License and limitations

Copyright (C) 2026 Jose Nunes. Licensed under [GPL-3.0-only](LICENSE). The project is experimental and supplied without warranty. Review permissions, paths, confirmations, selected model, and endpoint before authorizing actions.
