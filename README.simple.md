<p align="center">
  <img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="150">
</p>

# Jarvis-CLI — simple guide

Jarvis is a local AI assistant for Linux that runs in the terminal.

This is only a quick beginner's guide. For every setting, permission and feature, read the complete READMEs in [English](README.md) and [Portuguese](README.pt-BR.md).

## Install

The automatic installer is officially supported on Debian, Ubuntu and their derivatives.

1. Open the terminal. On Ubuntu, you can usually press `Ctrl + Alt + T`.
2. Copy and run these commands one at a time:

```bash
git clone https://github.com/frytinhas/Jarvis-CLI.git
cd Jarvis-CLI
bash Setup.sh
```

3. Follow the questions shown on the screen. Use the arrow keys to choose an option and press Enter to confirm.

Run Setup as a regular user. Do not use `sudo bash Setup.sh`.

## How to use

After installation, open the terminal and run:

```bash
jarvis
```

Type your question and press Enter. You can also send a question directly:

```bash
jarvis "what are my computer specifications?"
```

Basic commands inside Jarvis:

- `/help` shows the available commands.
- `/clear` clears the screen.
- `/exit` closes the conversation.

To change the settings later, run:

```bash
jarvis-config
```

If you chose a different name during installation, use that name instead of `jarvis`.

Jarvis may ask for confirmation before changing, deleting or running something. Read the displayed action before confirming it.

## License

Copyright (C) 2026 Jose Nunes.

Jarvis-CLI is free software licensed under the [GNU General Public License version 3](LICENSE), version 3 only (`GPL-3.0-only`). You may use, study, modify and redistribute it under that license. Every configurator save—and settings persisted by `/reasoning` or `/model`—schedules the short notice once for the next session. Type `/license` at any time to read the complete bundled license.

Distributions must retain the copyright and license notices, include the GPL, and make the corresponding source available as required by the license. Modified distributions must prominently identify their changes and the relevant dates. Models, `llama.cpp`, Python dependencies and other separately obtained third-party components remain governed by their own licenses.

## Disclaimer

This is a vibe-coded experimental project provided without warranties. Use it entirely at your own risk. Neither the project author nor the AI that assisted in producing it accepts responsibility for data loss, system damage or any other consequence caused by its use.

Jarvis only intermediates between you, the configured language model and its controlled local tools. With the default local endpoint, prompts, conversation logs, tool results and audit data remain on your computer, and the project includes no telemetry or intentional prompt-sharing mechanism. Installation still downloads dependencies, and configuring a remote model endpoint may send information to that endpoint under its own terms. No malicious behavior was intentionally included, but this is not a guarantee that the software is free of defects or vulnerabilities.
