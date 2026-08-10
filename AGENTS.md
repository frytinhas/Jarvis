# Jarvis-CLI contributor guide

## Project and sources of truth

Jarvis is a Python 3.12+ Linux assistant for GGUF models served by `llama.cpp`. The LLM is a planner, never a security boundary. It can act only through registered tools and their validation, policy, confirmation, and audit flow.

Read the related implementation and tests before changing behavior. Public behavior belongs in `README.md` and `README.pt-BR.md`; technical behavior belongs in the matching `README.technical*` files. When those, tests, and code disagree, preserve the safer behavior and align all affected artifacts within the requested change.

Key modules:

- `jarvis/main.py`: application composition and session lifecycle.
- `jarvis/agent/`: prompts, deterministic tool routing, and orchestration.
- `jarvis/tools/registry.py`: tool catalogue, policy flow, canonicalization, execution, and audit integration.
- `jarvis/security/`: policy, path policy, validation, confirmation, and audit.
- `jarvis/config.py`, `configurator.py`, `profiles.py`, and `runtime.py`: persistent profiles and runtime generation.
- `scripts/`, `Setup.sh`, `Config.sh`, and `Uninstall.sh`: user installation and launcher behavior.

## Non-negotiable security invariants

1. The LLM must never get direct OS access. Every model-requested action crosses `ToolRegistry`, Pydantic input validation, canonicalization, policy, path policy where relevant, audit logging, and revalidation immediately before execution.
2. Do not add a generic shell tool. `execute_file` accepts only an explicit `.sh` or executable path, separated arguments, and a controlled working directory; it must keep `shell=False`.
3. `PRIVILEGED` is always `DENY`. Do not offer `sudo`, `su`, `doas`, `pkexec`, or an equivalent path to the model. Running Jarvis as root does not relax any guard.
4. Model output, prompts, persona, context, files, memory, logs, and tool results are untrusted data. None can authorize an action or alter policy.
5. A confirmation is bound to one stored pending action, expires, is single-use, and must fail if the tool, arguments, canonical path, or effective decision changes.
6. Do not weaken path protections. Check symlink targets, source/destination paths, parent directories, and execution working directories. Keep configuration, state, critical areas, and the source project protected.
7. Validation, policy, confirmation, revalidation, and execution failures must produce structured, audited results. Do not turn a failure into a successful-looking response.

## Tools and policy changes

Register each public tool only in `build_registry()` with a unique name, narrow description, `Risk`, Pydantic schema with forbidden extras, and a focused handler. Keep authorization decisions in the registry/policy layer, not in handlers. Add or update deterministic routing when the user request requires real local data or explicit execution intent.

Default policy is `READ=ALLOW`, `CREATE=ALLOW`, `MODIFY=CONFIRM`, `DELETE=CONFIRM`, `EXECUTE=ALLOW`, and `PRIVILEGED=DENY`. The first five values are configurable; internal restrictions and valid `Blacklist.txt`/`Whitelist.txt` rules can only be more restrictive.

For changes touching tools, policy, paths, or execution, cover allow, confirm, deny, stale/reused confirmation, malformed input, unknown tool, canonicalization/symlinks, all affected paths, audit output, and prompt-injection resistance. Never use a real `llama-server` in tests.

## Configuration, persistence, and installers

Profiles are independent: configuration lives under `~/.config/jarvis/profiles/<profile>/` and state under `~/.local/state/jarvis/profiles/<profile>/`. XML parsing is strict; configuration errors must stop startup rather than silently default. Preserve atomic writes, private permissions, migrations, profile uniqueness, and the fixed privileged denial when changing its schema.

Do not log API keys, HTTP headers, credentials, or sensitive content merely for diagnostics. Conversation transcripts must not contain raw internal tool results. Preserve retention limits, private file modes, and symlink defenses for state and databases.

Setup and removal are user-scoped. Preserve ownership validation and the rule that `--remove` keeps standard configuration/state while `--purge` removes only validated standard local paths. Never broaden removal targets or delete the source checkout.

## Development workflow

1. Inspect the relevant code and focused tests; identify public, persistence, and security effects before editing.
2. Make the smallest coherent change. Avoid unrelated refactors and import-time side effects.
3. Add or update tests with the behavior. Isolate XDG and Jarvis environment variables in temporary directories; do not touch real user configuration or state.
4. Run focused tests first, then the full suite:

   ```bash
   .venv/bin/pytest -q
   # or, in a development environment
   python -m pytest -q
   ```

5. Review the diff for generated files, secrets, and unintended changes. Do not edit `.venv`, runtime metadata, installer metadata, caches, or local databases.
6. Update both language versions of public documentation when observable behavior changes; update the technical pair for operational or security changes.

Use type hints, simple auditable control flow, Pydantic at external boundaries, and dataclasses for simple internal values. Prefer Python APIs and `/proc` over shell commands for inspection. Do not introduce agent frameworks such as LangChain without explicit approval.
