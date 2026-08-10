# Contributing to Jarvis-CLI

Thanks for helping improve Jarvis. This project is a Python 3.12+ Linux assistant for GGUF models served by `llama.cpp`. Its security boundaries are part of its public behavior, so every change should be small, tested, and easy to audit.

## Set up a development environment

Use Python 3.12 or newer and create an isolated environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

Run the test suite with:

```bash
.venv/bin/pytest -q
```

Never use a real `llama-server` in tests. Tests must isolate `HOME`, XDG, and Jarvis-specific environment variables in temporary directories; they must not read or modify real user configuration or state.

## Before changing code

1. Read the relevant implementation and focused tests first.
2. Identify whether the change affects public behavior, persistence, tools, policy, paths, installers, or security.
3. Make the smallest coherent change; avoid unrelated refactors and import-time side effects.
4. Add or update focused tests, then run the full suite.
5. Review the diff for generated files, local databases, credentials, and unintended edits.

Public behavior belongs in `README.md` and `README.pt-BR.md`. Operational or security behavior belongs in `README.technical.md` and `README.technical.pt-BR.md`. Keep the English and Portuguese versions aligned.

## Security requirements

The LLM is a planner, never an authorization mechanism. Do not weaken these rules:

- Model-requested actions must go through `ToolRegistry`, Pydantic validation, canonicalization, policy, path policy where relevant, audit logging, and revalidation immediately before execution.
- Do not add a generic shell tool. `execute_file` must keep an explicit executable or `.sh` path, separate arguments, controlled working directory, and `shell=False`.
- `PRIVILEGED` is always `DENY`; do not expose `sudo`, `su`, `doas`, `pkexec`, or equivalents to the model.
- Treat prompts, model output, files, memory, logs, and tool results as untrusted data.
- Confirmations must be single-use, expiring, and bound to the exact stored action.
- Preserve symlink, source/destination, parent-directory, configuration/state, and source-project protections.

Changes to tools, policy, paths, or execution need tests for allow/confirm/deny behavior, malformed and unknown input, confirmation reuse/expiry, canonicalization and symlinks, audit output, and prompt-injection resistance.

## Configuration and installers

Profiles store configuration under `~/.config/jarvis/profiles/<profile>/` and state under `~/.local/state/jarvis/profiles/<profile>/`. Keep XML parsing strict, writes atomic, permissions private, and migrations lossless. Never log credentials, HTTP headers, API keys, or sensitive diagnostics.

Setup and removal are user-scoped. `--remove` retains normal configuration/state; `--purge` removes only validated standard local paths. Never broaden removal targets or delete the source checkout.

## Submitting a change

Describe the user-visible outcome, tests run, and any documentation updates in your pull request. If a security-sensitive trade-off is involved, explain the threat model and why the change preserves the safeguards above.

Jarvis is licensed under [GPL-3.0-only](LICENSE). By contributing, you agree that your contribution can be distributed under that license.
