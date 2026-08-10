# Jarvis-CLI

<p align="center"><img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="140"></p>

Jarvis is a local Linux assistant for GGUF chat models served by `llama.cpp`. It can inspect or act on your computer only through narrowly scoped tools, permission rules, confirmations, and an audit log.

[Leia em português](README.pt-BR.md) · [Technical guide](README.technical.md) · [Contributing](CONTRIBUTING.md)

## What Jarvis is for

Use Jarvis to talk to a local model about your work, inspect files and system information, and request supported actions with visible safeguards. The model is a planner, not a security boundary: it never receives a general shell or permission to elevate privileges.

## Before you start

You need:

- Linux
- Python 3.12 or newer
- `curl`
- An instruct/chat model in `.gguf` format

Automatic setup is supported on Debian, Ubuntu, and derivatives. On other distributions, install any missing system dependencies first.

## Install

Clone the project and run Setup as the same user who will use Jarvis:

```bash
git clone https://github.com/frytinhas/Jarvis-CLI.git
cd Jarvis-CLI
bash Setup.sh
```

Do not use `sudo` for a normal user installation. Setup creates an isolated user installation, prepares `llama.cpp` when needed, and opens the configurator so you can choose your first GGUF. The permanent initial profile is named `jarvis`.

If `~/.local/bin` is not in your `PATH`, open a new terminal after setup finishes.

## Start chatting

```bash
jarvis
jarvis "list the files in this directory"
jarvis --r 3 "analyze this project"
```

`--r` selects reasoning for this run: `0` off, `1` low, `2` medium, `3` high, and `4` max. Run `jarvis-config` whenever you want to review configuration.

Your first interactive session can collect optional learning information. Nothing from that session is retained unless you approve a summary with `/finish`.

## Models and profiles

A profile is a shared workspace for one or more GGUFs. It keeps shared persona, context, learning, permissions, and audit history. Conversation logs, diagnostic logs, and private notes stay separate for each GGUF inside that profile.

Use `/model` to see known GGUFs. A `★` means the model has not been assigned to a profile yet.

```text
/model                 # list GGUFs
/model my-model.gguf   # select a GGUF
/profile               # list profiles
/profile work          # open work with its last selected GGUF
```

When selecting a new GGUF, Jarvis lets you choose an existing profile or create one. A GGUF may belong to multiple profiles; if so, Jarvis asks which one to use. Different GGUFs cannot run simultaneously in the same profile, but multiple sessions of the same GGUF can.

The original `jarvis` profile is permanent. It can be reset, but not deleted:

```bash
jarvis-config --reset-profile jarvis
jarvis-config --delete-profile work
```

Both operations require confirmation. Deleting another profile removes its configuration and data.

## Useful chat commands

| Command | What it does |
| --- | --- |
| `/help` | Shows all local commands. |
| `/model [GGUF]` | Lists or changes GGUFs. |
| `/profile [name]` | Lists or changes profiles. |
| `/reasoning off|low|medium|high|max` | Saves the default reasoning level. |
| `/context [tokens|reset]` | Shows or changes context size. |
| `/permissions` | Shows or changes tool permissions. |
| `/config` | Shows the active configuration. |
| `/exit` | Closes the chat. |
| `/quit` | Closes the chat and requests managed-server shutdown. |

Use `Ctrl+C` to cancel current generation or execution without closing the chat. Use `jarvis --full-stop` to stop the managed model server without opening a session.

## Safety and privacy

- Jarvis has no generic shell tool and never offers privileged operations.
- File changes and deletions require confirmation by default; permissions can only be made more restrictive by path rules.
- Prompts, model output, files, memory, and tool results are untrusted data. They cannot authorize an action.
- Diagnostic logs redact credentials and raw file/tool content, but local data is not encrypted. Do not put secrets in prompts, persona files, or notes.

Jarvis is local by default. Configuring an external OpenAI-compatible endpoint sends prompts and context to that endpoint.

Read the [technical guide](README.technical.md) for the complete security model, data layout, command reference, and operational details.

## Update or remove

After updating the source checkout, run `jarvis-update` to use the safe repair flow; it preserves configuration and state.

```bash
jarvis --remove  # remove Jarvis, keep configuration and state
jarvis --purge   # also remove standard local configuration and state
```

Removal is user-scoped, requires an exact confirmation phrase, and never removes the source checkout.

## License

Copyright (C) 2026 Jose Nunes. Licensed under [GPL-3.0-only](LICENSE). Jarvis is experimental software supplied without warranty.
