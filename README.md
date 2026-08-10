# Jarvis-CLI

<p align="center"><img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="140"></p>

Jarvis is a local assistant for Linux. It runs an instruct/chat GGUF model through `llama.cpp`; the model can inspect or act on the computer only through controlled tools, permissions, confirmations, and an audit log.

Português: [README.pt-BR.md](README.pt-BR.md). For installation internals, profiles, security rules, and the complete command reference, see the [technical guide](README.technical.md).

## What you need

- Linux
- Python 3.12 or later
- `curl`
- An instruct/chat model in `.gguf` format

The automatic setup is officially supported on Debian, Ubuntu, and their derivatives. Other distributions may need their system dependencies installed manually.

## Install

```bash
git clone https://github.com/frytinhas/Jarvis-CLI.git
cd Jarvis-CLI
bash Setup.sh
```

Run Setup as the user who will use Jarvis. Do not run a normal-user installation with `sudo`. The setup creates an isolated installation for that user, prepares `llama.cpp` when necessary, then opens an interactive configurator. Choose a GGUF file and a profile name; that name becomes the command you use to start the assistant.

If `~/.local/bin` is not already on your `PATH`, open a new shell after Setup finishes.

After updating the source checkout, run `jarvis-update` to apply it with the safe repair flow; it preserves configuration and state.

## Use

Start the profile command chosen during configuration (for example, `jarvis`):

```bash
jarvis
jarvis "list the files in this directory"
jarvis --r 3 "analyze this project"
```

`--r` selects reasoning for this invocation: `0` is off, `1` low, `2` medium, `3` high, and `4` max. Use `jarvis-config` whenever you want to create, edit, or choose profiles again.

Learning sessions always use reasoning off, independently of this setting. On the first run, learning is discarded unless you explicitly approve a summary with `/finish`; closing the terminal, Ctrl+C, or `/exit` saves none of that learning conversation.

Jarvis always writes a private diagnostic JSONL session log under the active profile state directory (`logs/debug`), regardless of the display log setting. The default combined limit is 200 MB and retention is configurable. These logs redact credentials and raw file/tool content.

Inside the chat, these commands are the most useful:

- `/help` — show all local commands.
- `/model` — list or switch to another configured profile/model.
- `/reasoning off|low|medium|high|max` — save the default reasoning level.
- `/permissions` — display or change the global permission policy.
- `/config` — show the active profile settings.
- `/exit` — close the chat.
- `/quit` — close the chat and stop its managed model server after memory work completes.

`Ctrl+C` cancels the current generation or execution without closing the chat. Use `jarvis --full-stop` to stop the managed server without opening a session.

The interactive prompt handles long wrapped input without duplicating text. It supports cursor editing and Shift+arrow selection before sending, without retaining sent-message history. Terminal pastes stay as one editable draft, even when they contain line breaks; press Enter explicitly to send.

## Safety in brief

Jarvis does not provide the model with a generic shell. It uses narrowly defined tools for files, processes, and system information. File changes and deletion require confirmation by default; permissions can be made more restrictive. Privileged operations are never offered to the model.

Review every confirmation before accepting it. Persona files, conversations, files read by the model, and tool output are untrusted data—not authorization. Jarvis is local by default, but configuring a remote OpenAI-compatible endpoint sends prompts and context to that endpoint.

## Remove

```bash
jarvis --remove  # remove the application and keep configuration and state
jarvis --purge   # also remove standard local configuration and state
```

Removal asks for an exact confirmation phrase, affects only the current user, and preserves the source clone.

## License

Copyright (C) 2026 Jose Nunes. Licensed under [GPL-3.0-only](LICENSE). Jarvis is experimental software supplied without warranty.
