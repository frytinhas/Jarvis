<p align="center"><img src="jarvis/ui/Icon.png" alt="Jarvis-CLI" width="120"></p>

# Jarvis-CLI — simple guide

Jarvis is a Linux assistant that runs a local GGUF model and accesses the computer only through controlled tools.

## Install

You need Linux, Python 3.12+, `curl`, and an instruct/chat GGUF model.

```bash
git clone https://github.com/frytinhas/Jarvis-CLI.git
cd Jarvis-CLI
bash Setup.sh
```

Setup does not use `sudo`. It installs only for the current user under `~/.local/share/jarvis/app` and creates commands in `~/.local/bin`. Local dependencies are attempted automatically; if a system package is required, Setup explains what to install.

If Setup is already running as root, it displays a warning and installs only under `/root`. Do not run a normal user's installation through `sudo`.

At the end, select your `.gguf` file in the configurator. To configure again:

```bash
jarvis-config
```

## Use

```bash
jarvis
jarvis "list the files in this folder"
```

Useful commands:

- `/help`: help.
- `/model`: changes the model.
- `/reasoning off|low|medium|high|max`: changes reasoning.
- `/permissions`: shows permissions.
- `/exit`: closes chat.
- `/quit`: closes chat and stops the server after memory is saved.

Jarvis never executes text such as `ls` or commands invented by the model. Reads use real tools; changes and deletion follow policy and may require confirmation.

## Remove

```bash
jarvis --remove  # keep configuration and history
jarvis --purge   # also remove local data
```

Removal affects only the current user and never asks for sudo. See the [complete README](README.md) for security, memory, advanced configuration, and licensing.
