<p align="center">
  <img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="150">
</p>

# Jarvis-CLI

Jarvis is a local Linux assistant powered by a GGUF model running through `llama.cpp`. The language model only plans requests: file and system access always goes through the application's validated tools and permission policy.

Portuguese documentation: [README.pt-BR.md](README.pt-BR.md)

## Install

Clone the project and run:

```bash
bash Setup.sh
```

The setup only installs Jarvis, its Python environment, the llama server and the configuration command. When installation finishes, it automatically starts the configuration wizard.

The automatic installer is officially supported on Debian, Ubuntu and their derivatives. Jarvis may work on other Linux distributions, but that setup path has not been tested and system dependencies may need to be installed manually.

Run Setup as a regular user. It also creates an isolated, root-owned administrative installation under `/usr/local/lib/jarvis-local`. `sudo jarvis` runs the assistant as root while preserving the directory from which it was invoked.

The administrative configuration starts as an independent copy of the Setup configuration at `/root/.config/jarvis/config.xml`. Its state, runtime, logs, and audit database live under `/root/.local/state/jarvis`. Use `sudo jarvis-config` to change it without affecting the regular user.

Running as root increases the reach of tools. The Tool Router, confirmations, blacklist, critical-path protections, and `PRIVILEGED` denial remain active, but use this command only when administrative access is required.

The configurator has ten entries: Model and reasoning, Identity, Behavior, Timeouts, Permissions, Logs and panel, Appearance, Persona and context, Save and exit, and Exit without saving. In an interactive terminal, use the arrow keys and Enter for menus, lists, and yes/no questions; text and numbers are still typed normally. Incompatible terminals automatically receive the numbered fallback.

When using `jarvis-config`, the review shows only modified fields as `previous value → new value`. During `Setup.sh`, it shows the complete initial configuration summary. Exiting without saving writes nothing.

### Advanced configuration

All persistent configuration is stored in:

```text
~/.config/jarvis/config.xml
```

The file is simple, indented, and includes both PT-BR and English comments explaining each section. Advanced users may edit it directly; changes are validated and take effect the next time Jarvis starts. Invalid values, unknown elements, or malformed XML stop startup with a clear error instead of silently applying defaults.

The XML is created with `0600` permissions and may contain an API key. Remove sensitive data before sharing it. The internal runtime is regenerated automatically at `~/.local/state/jarvis/runtime.env` and should not be edited.

Terminal colors live in `~/.config/jarvis/colors.toml`. Jarvis creates a complete orange palette and preserves valid `#RRGGBB` values on every session while replacing only missing or invalid fields. The Appearance menu can detect terminal support automatically, force colors, or disable them; automatic mode also honors `NO_COLOR`.

To open the XML directly in Nano, run:

```bash
jarvis-config --a
```

After upgrading an older installation, run `jarvis-config` once to create the XML. The old `~/.config/jarvis/settings.json` and `.env` may supply initial values to the wizard, but they are not migrated during normal startup and remain untouched as backups.

### Uninstall

To remove the application, service, shortcuts, CLI, and runtime while keeping configuration, audit data, and conversations for a future reinstall, run:

```bash
jarvis --remove
```

Confirm by typing exactly `jarvis remove`. To also delete configuration and all data stored in Jarvis's standard directories, run:

```bash
jarvis --purge
```

This mode requires `jarvis purge`. Running `bash Uninstall.sh` from the project directory is equivalent to `jarvis --purge`; `bash Uninstall.sh --remove` is also available. The source repository is not deleted. For safety, a manually configured audit file outside Jarvis's standard directories is not removed automatically.
Uninstallation also removes the administrative launchers and application copy. `--remove` preserves root configuration and logs, while `--purge` removes them as well.

## Use

With the default name:

```bash
jarvis
jarvis "what are my computer specifications?"
jarvis --r 3 "analyze this project"
```

`--r` controls the initial reasoning level for that chat: `-1` uses the configured default, `0` disables it, `1` is Low, `2` Medium, `3` High, and `4` Max. The initial default is Medium. During a session, `/reasoning off|low|medium|high|max` applies immediately and persists the new default.

Local commands support Tab completion and are never sent to the model:

- `/help`: show available commands.
- `/reasoning`: inspect or change reasoning.
- `/model`: list or select a GGUF from the configured directory. The server can restart immediately or apply the change on the next launch.
- `/config`: show a read-only configuration summary.
- `/clear`: clear the screen without deleting conversation context.
- `/license`: show the complete GPL text.
- `/exit`: close the session; `/quit` and `/sair` are aliases.

If you choose a custom name such as Bob, use:

```bash
bob
bob "list the files in my Downloads folder"
```

The custom name changes the public command, terminal labels and assistant identity. Internal project files and services remain named Jarvis. Run `jarvis-config` at any time to reconfigure it.

On compatible desktop environments, Jarvis also appears in the application menu with its icon. Opening it there starts the same terminal assistant.

## Chat and model server

Use `/sair` to close a chat. By default, Jarvis stops its managed model server when the last open chat closes. You can change this in `jarvis-config` so the model stays ready in the background.

To stop a server kept in the background without changing its automatic-start preference, run:

```bash
jarvis --full-stop
```

Use your custom command name instead of `jarvis` when applicable. Jarvis only stops a server it started or manages; it does not terminate an unrelated server found at the same address.

When called from a folder, Jarvis automatically knows that folder and uses it as the base for relative paths:

```bash
cd ~/Projects/my-app
jarvis "summarize this project"
```

A command-line message can remain in the conversation after the first answer, which is the default, or answer once and close. Choose the behavior in `jarvis-config`.

## Permissions

Permissions are configured by category:

- `READ`: inspect files and system information.
- `CREATE`: create files and directories.
- `MODIFY`: write, append, move and rename.
- `DELETE`: remove files and empty directories.
- `EXECUTE`: run an explicit `.sh` script or binary path, without a generic shell.

The first-run defaults allow `READ` and `CREATE` without confirmation. `MODIFY`, `DELETE` and `EXECUTE` require confirmation. Critical paths and privileged actions remain blocked regardless of these choices.

Jarvis does not ask in prose for permission to use a tool. Allowed `READ` tools run directly; actions configured as `CONFIRM` produce an exact-arguments confirmation through the Policy Engine. Local specification questions require real hardware inspection and no component is guessed if inspection fails. Large files can be read in bounded chunks.

`execute_file` accepts only an explicit file, separate arguments, an optional working directory, timeout, and background mode. It uses `shell=False`, blocks known privilege frontends and inline interpreter code. With `EXECUTE=ALLOW`, it runs without confirmation—including under `sudo jarvis`, where the child process has root privileges. This combination is extremely powerful; keep `CONFIRM` as the default and restrict paths in `Blacklist.txt`.

During foreground generation or execution, `Ctrl+C` cancels only the current operation and keeps the chat open.

### Permissions by file or folder

Edit [Blacklist.txt](Blacklist.txt) to make permissions stricter for particular paths. Each line contains a file or directory followed by a five-position code in this order:

```text
path READ MODIFY CREATE DELETE EXECUTE
~/UnrealProjects 21202
```

`0` denies the operation, `1` requires confirmation and `2` permits it without confirmation. A short code leaves trailing positions unspecified, while `-` inherits an individual position from an earlier matching rule. Any position never defined defaults to `0`.

Rules are processed from top to bottom. A later matching line overrides the positions it declares, including when that later line refers to a parent directory. These rules can only restrict the permissions selected in `jarvis-config`; they never grant broader access.

The file is checked when a new chat starts. If it is missing or invalid, all file-based tools are disabled until it is corrected and a new chat is opened. The Jarvis-CLI project directory itself is permanently read-only to tools.

## Context and local memory

Edit [Context.md](Context.md) to teach Jarvis useful references and working habits without changing its personality. The default context tells it to resolve folders such as Documents through your HOME, try safe name variations and use READ tools before asking questions that it can answer locally. Security rules always take priority over this file.

Jarvis saves a private summary and the visible user/assistant conversation in:

```text
~/.local/state/jarvis/logs/conversations.db
```

Conversations are stored in a local SQLite database. The five newest summaries are available as recent context. For older conversations, Jarvis can use its controlled `search_conversation_logs` READ tool. This makes requests such as “remember the code we worked on yesterday?” possible without a vector database or external service.

By default, logs are kept for 30 days and the folder is limited to 100 MB. Run `jarvis-config` to change either value. A value less than or equal to zero means unlimited. Expired and oldest logs are removed locally when needed. The database is private to your user account but is not encrypted, so conversations should not be treated as a password vault.

The activity panel has five levels. `Essential`, the default, shows tools, commands, paths, and changed content; reads show only their target and metadata. `Minimal-Essential` shows only tools and states. `Server-Essential` adds server logs, `Full` includes complete technical diagnostics, and `None` keeps only the conversation and waiting messages. In `Full` and `Server-Essential`, Jarvis asks at session startup whether logs should be saved under `~/.local/state/jarvis/logs/runtime/`.

Edit [WaitingMessages.txt](WaitingMessages.txt) to customize the short messages shown while the model is working. On startup, Jarvis randomly selects a non-empty line and then advances through the list in circular order every 5–10 seconds. In interactive terminals, each message replaces the previous one on the same line. Leave the file empty to disable them.

Each interaction allows up to 128 tool cycles, 600 seconds of total active processing, and 120 seconds per model request. The configured values are disclosed to the model at session startup. Time spent waiting for human confirmation does not consume the total. In `Essential`, `Server-Essential`, and `Full`, completed tools show their duration followed by the interaction's accumulated active time, both against the total timeout. Change tool cycles under `jarvis-config → Behavior` and time limits under `jarvis-config → Timeouts`.

## Personality

Edit [Persona.md](Persona.md) to change tone and behavior. It is written in English by default, but may contain instructions in any language. The name selected in `jarvis-config` always overrides names written in the persona. The wizard can restore the original persona after confirmation.

## Model suggestions

Use an instruct/chat GGUF model, preferably a `Q4_K_M` quantization. Lightweight options include:

- [Qwen3 4B GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF)
- [Phi-4 Mini 3.8B GGUF](https://huggingface.co/unsloth/Phi-4-mini-instruct-GGUF)
- [Llama 3.2 3B Instruct GGUF](https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF)
- [Gemma 3 4B Instruct GGUF](https://huggingface.co/lmstudio-community/gemma-3-4b-it-GGUF)

Larger alternatives such as Qwen3 8B or Gemma 4 12B generally require more memory. Tool-calling quality depends on the selected model and its chat template.

Never start the model with `--tools all`; Jarvis must remain the only layer allowed to execute protected tools.

## License

Copyright (C) 2026 Jose Nunes.

Jarvis-CLI is free software licensed under the [GNU General Public License version 3](LICENSE), version 3 only (`GPL-3.0-only`). You may use, study, modify and redistribute it under that license. Every configurator save—and settings persisted by `/reasoning` or `/model`—schedules the short notice once for the next session. Type `/license` at any time to read the complete bundled license.

Distributions must retain the copyright and license notices, include the GPL, and make the corresponding source available as required by the license. Modified distributions must prominently identify their changes and the relevant dates. Models, `llama.cpp`, Python dependencies and other separately obtained third-party components remain governed by their own licenses.

## Disclaimer

This is a vibe-coded experimental project provided without warranties. Use it entirely at your own risk. Neither the project author nor the AI that assisted in producing it accepts responsibility for data loss, system damage or any other consequence caused by its use.

Jarvis only intermediates between you, the configured language model and its controlled local tools. With the default local endpoint, prompts, conversation logs, tool results and audit data remain on your computer, and the project includes no telemetry or intentional prompt-sharing mechanism. Installation still downloads dependencies, and configuring a remote model endpoint may send information to that endpoint under its own terms. No malicious behavior was intentionally included, but this is not a guarantee that the software is free of defects or vulnerabilities.
