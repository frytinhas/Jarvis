<p align="center">
  <img src="jarvis/ui/Icon.png" alt="Jarvis Local" width="150">
</p>

# Jarvis Local

Jarvis is a local Ubuntu assistant powered by a GGUF model running through `llama.cpp`. The language model only plans requests: file and system access always goes through the application's validated tools and permission policy.

Portuguese documentation: [README.pt-BR.md](README.pt-BR.md)

## Install

Clone the project and run:

```bash
bash Setup.sh
```

The setup only installs Jarvis, its Python environment, the llama server and the configuration command. When installation finishes, it automatically starts the configuration wizard.

The wizard asks, in order, for:

1. The folder containing your local GGUF models and which model to use.
2. Which permission categories are available.
3. Which enabled categories may run without confirmation.
4. Whether to keep or restore `Persona.md`.
5. Whether to use a custom assistant name and terminal command.
6. Whether the model server starts automatically with your user session.
7. Whether the model server stays on after the last chat closes.
8. Whether a command-line message starts a continuing chat or answers once and exits.

Nothing is saved until the final summary is confirmed.

## Use

With the default name:

```bash
jarvis
jarvis "what are my computer specifications?"
```

If you choose a custom name such as Bob, use:

```bash
bob
bob "list the files in my Downloads folder"
```

The custom name changes the public command, terminal labels and assistant identity. Internal project files and services remain named Jarvis. Run `jarvis-config` at any time to reconfigure it.

Jarvis also appears in Ubuntu's application menu with its icon. Opening it there starts the same terminal assistant.

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
- `EXECUTE`: reserved for future process/application tools.

The first-run defaults allow `READ` and `CREATE` without confirmation. `MODIFY`, `DELETE` and `EXECUTE` require confirmation. Critical paths and privileged actions remain blocked regardless of these choices.

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
