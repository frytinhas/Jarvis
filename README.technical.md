# Jarvis-CLI technical guide

<p align="center"><img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="140"></p>

Operational and security reference for Jarvis. For installation and daily use, start with the [main guide](README.md). [Português](README.technical.pt-BR.md) · [Contributing](CONTRIBUTING.md)

## Trust boundary

Jarvis runs an instruct/chat GGUF through `llama.cpp`. The LLM plans and writes replies, but never has direct operating-system access. Every model-requested action passes through registered-tool selection, Pydantic validation, policy evaluation, path checks where relevant, confirmation, immediate revalidation, execution, and SQLite audit logging.

The model is not a security boundary. Prompts, persona/context files, model output, memory, logs, files, and tool results are untrusted data. They cannot grant permissions or change policy.

## Install, repair, and runtime

Requirements are Linux, Python 3.12+, `curl`, and an instruct/chat GGUF. Install from a clone as the target user:

```bash
bash Setup.sh
```

A normal user installation never escalates privileges. It installs the application and virtual environment in `~/.local/share/jarvis/app`, user commands in `~/.local/bin`, configuration in `~/.config/jarvis`, and state in `~/.local/state/jarvis`. When needed, Setup builds a CPU `llama.cpp`; missing system packages are reported instead of installed with elevation.

`jarvis-update` validates ownership and runs the repair flow from the recorded source checkout. Running Setup again offers repair with retained user data or a clean reinstall for that user. Neither flow modifies or removes the source clone.

The launcher manages `llama-server` through `systemd --user` when available, otherwise through a tracked fallback process. It only stops servers it started or manages.

```bash
jarvis --full-stop      # stop the active profile's managed server
jarvis --full-stop-all  # request shutdown of every managed profile server
```

## Profiles, GGUFs, and stored data

Profiles are named shared workspaces stored below:

```text
~/.config/jarvis/profiles/<profile>/
~/.local/state/jarvis/profiles/<profile>/
```

The profile XML is the shared configuration: persona, context, learning context, permissions, behavior, server settings, and audit database. Its `models.json` catalogue records associated GGUF paths; the XML's active model is the profile's last selected GGUF.

Each GGUF also gets a private directory identified from its canonical path. This keeps conversation storage, runtime/debug logs, session markers, and `jarvis-notes` isolated even when models share a profile. Learning context and audit history remain profile-wide.

| Operation | Result |
| --- | --- |
| Select a known GGUF | Opens its associated profile; choose explicitly when it belongs to several profiles. |
| Select `★` GGUF | Choose an existing profile or create a named profile. |
| `/profile name` | Opens that profile with its last selected GGUF. |
| Run the same GGUF twice | Allowed; later sessions receive only an internal notice with other session working directories. |
| Run another GGUF in an occupied profile | Refused until the active model session closes. |

The `jarvis` profile always exists and cannot be deleted. Resetting it erases its associations and information but retains the empty permanent profile. Other profiles can be reset or deleted only after confirmation:

```bash
jarvis-config --reset-profile jarvis
jarvis-config --delete-profile work
```

Existing one-GGUF profiles migrate automatically: their active GGUF is added to the catalogue and legacy logs/notes move to that GGUF's private area.

## Configuration and commands

Run `jarvis-config` to select a profile/model and edit settings. `jarvis-config --a` opens the active XML in Nano. XML parsing is strict; invalid configuration stops startup rather than applying silent defaults. Files are written atomically with private permissions.

Use `jarvis --persona`, `--context`, `--blacklist`, `--whitelist`, `--waiting-messages`, or `--goodbye-messages` to edit the corresponding profile resource.

### Chat control

| Command | Effect |
| --- | --- |
| `/help` | Show the local reference. |
| `/model [GGUF]` | List or select GGUFs; `★` marks an unassociated model. |
| `/profile [name]` | List or select profiles. |
| `/config` | Show the active profile summary. |
| `/clear` | Clear the terminal without clearing chat context. |
| `/exit` or `/sair` | Close the chat. |
| `/quit` | Close the chat and request server shutdown after memory work. |
| `/license` | Display GPL-3.0. |

### Conversation behavior

| Command | Effect |
| --- | --- |
| `/reasoning off|low|medium|high|max` | Save the default reasoning level; a template-mode change can require server restart. |
| `/context N` | Set a positive context length that is a multiple of 1024. |
| `/context reset` | Restore the automatically recommended context length. |
| `/learning` | Start a new interactive learning session. |
| `/finish` | Propose an approval-gated learning summary. |

### Permissions

`/permissions` displays the effective configurable policy. `/permissions risk decision` updates one global decision, where the accepted risks are `read`, `create`, `modify`, `delete`, and `exec`; decisions are `allow`, `confirmation`, or `deny`.

| Risk | Default | Examples |
| --- | --- | --- |
| `READ` | `ALLOW` | inspect files, processes, system information |
| `CREATE` | `ALLOW` | create a file or directory |
| `MODIFY` | `CONFIRM` | write, append, move, rename |
| `DELETE` | `CONFIRM` | delete a file or empty directory |
| `EXECUTE` | `ALLOW` | run an explicit file path |
| `PRIVILEGED` | fixed `DENY` | privilege escalation and equivalent paths |

## Tools and path policy

There is no generic shell tool. Registered tools provide bounded file reading/search, file metadata, directory listing, process and system inspection, file/directory creation and modification, deletion of files or empty directories, and execution of an explicit `.sh` file or executable.

`execute_file` uses separate arguments with `shell=False`. It requires user intent and an explicit permitted path, and rejects privilege escalation, inline evaluation, setuid/setgid executables, and selected destructive operations.

`Whitelist.txt` optionally restricts path tools to listed absolute roots. `Blacklist.txt` can only make policy stricter. Each non-comment blacklist line is an absolute or `~` path followed by one to five codes for `READ MODIFY CREATE DELETE EXECUTE`: `0` deny, `1` confirm, `2` allow, and `-` unchanged.

```text
~/Projects 21202
```

Invalid or unreadable path-policy files close path-based tools. Jarvis canonicalizes paths and checks symlink targets, sources, destinations, parent directories, and execution working directories. Critical system areas, Jarvis configuration/state, and non-read access to the source project remain protected.

## Privacy, retention, and removal

Conversation logs and diagnostic logs are private to the active profile/GGUF. Debug JSONL is always enabled under that GGUF's `logs/debug` directory, independent of the display level. Its default combined size limit is 200 MB; retention and size limits are configurable. Configuration is sanitized, and credentials plus raw file/tool content are redacted.

Data is not encrypted. Do not put passwords, tokens, API keys, or other secrets in prompts, profile resources, notes, or logs. Configuring a remote OpenAI-compatible endpoint sends prompts and context to that endpoint.

```bash
jarvis --remove  # keep configuration and state
jarvis --purge   # remove standard configuration and state too
```

The uninstall flow requires the exact phrase `jarvis remove` or `jarvis purge`, applies only to the current user, removes managed user services and commands, and preserves the source checkout. An audit database configured outside the standard Jarvis state path is not removed automatically.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Profile or configuration is missing | Run `jarvis-config`; do not hand-edit a missing XML. |
| GGUF is not listed | Re-open `jarvis-config` and select its containing directory, then use `/model`. |
| GGUF cannot be switched in a profile | Close sessions using a different GGUF in that profile first. |
| Server port is occupied | Keep the external process running and assign another profile port through configuration. |
| Configuration error at startup | Correct the reported XML/path-policy error; Jarvis intentionally does not fall back silently. |
| Model server is unhealthy | Use `jarvis --full-stop`, then start Jarvis again; only Jarvis-managed servers are stopped. |

## License and limitations

Copyright (C) 2026 Jose Nunes. Licensed under [GPL-3.0-only](LICENSE). Jarvis is experimental software supplied without warranty. Review the selected model, endpoint, paths, permissions, and every confirmation before authorizing an action.
