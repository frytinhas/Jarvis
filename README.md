# Jarvis-CLI

Jarvis-CLI is a privacy-first, telemetry-free local AI assistant for Linux. The implemented domain
currently includes the security foundation, persistent profile identity/configuration, one
foreground Jarvis Core behind versioned local IPC, the profile-first `jarvis-config` client, and a
read-only local GGUF registry with minimum `jarvis-manage` configuration. No model process,
inference, chat, host tool, network feature, TUI, or public Jarvis assistant command exists yet.

The current implementation provides user-local XDG storage, versioned defaults, SQLite migrations,
bounded redacted infrastructure diagnostics, quota reservations, typed errors, active-installation
identity checks, and Core-owned profile/model lifecycle/configuration APIs. `jarvis-config`,
`jarvis-manage`, and `jarvis-help` are thin local clients; logical profile aliases are data mappings
only and do not create commands. GGUF discovery is explicit, bounded, descriptor-based, and
read-only. Local model inference and assistant clients are later milestones.

## Requirements

- Linux, initially Ubuntu, Debian, or a Debian-derived distribution.
- CPython 3.12 or newer.
- Development dependencies installed explicitly by a maintainer. Application startup and tests do
  not install or download dependencies.

Jarvis-CLI has no runtime Python dependencies through Milestone 004 and performs no intentional
network access or telemetry.

## Development commands

```bash
PYTHONPATH=src python -m jarvis.foundation initialize --json
PYTHONPATH=src python -m jarvis.foundation inspect --json
PYTHONPATH=src python -m jarvis.core --foreground
PYTHONPATH=src python -m jarvis.cli --help
PYTHONPATH=src python -m jarvis.manage --help
```

An installed development wheel exposes `jarvisd`, `jarvis-config`, `jarvis-help`, and
`jarvis-manage`. It does not
expose `jarvis` or physical profile commands, daemonize, install systemd units, register PATH
entries, or start a model. The protocol is documented in
[`docs/ipc-protocol.md`](docs/ipc-protocol.md).

Always point all five XDG roots, including a pre-created mode-`0700` `XDG_RUNTIME_DIR`, at a
disposable location when evaluating foundation behavior. See
[`docs/development.md`](docs/development.md) for the complete procedure.

## License

Jarvis-CLI is licensed under GPL-3.0-only. See [`LICENSE`](LICENSE).
