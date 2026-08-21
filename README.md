# Jarvis-CLI

Jarvis-CLI is a privacy-first, telemetry-free local AI assistant for Linux. The implemented domain
currently includes the security foundation, persistent profile identity/configuration, one
foreground Jarvis Core behind versioned local IPC, the profile-first `jarvis-config` client, a
read-only local GGUF registry, a Core-owned per-profile `llama-server` runtime manager, and the
client-neutral M006A chat pipeline. A negotiated IPC test client can submit, stream, cancel,
reattach to, and inspect durable profile/model chat turns. No assistant chat presentation, host
tool, external-network feature, TUI, or public `jarvis` assistant command exists yet.

The current implementation provides user-local XDG storage, versioned defaults, SQLite migrations,
bounded redacted infrastructure diagnostics, quota reservations, typed errors, active-installation
identity checks, and Core-owned profile/model lifecycle/configuration APIs. `jarvis-config`,
`jarvis-manage`, and `jarvis-help` are thin local clients; logical profile aliases are data mappings
only and do not create commands. GGUF discovery is explicit, bounded, descriptor-based, and
read-only. `jarvis-manage` can start, inspect, stop, and switch authenticated loopback-only model
runtimes, with one runtime per profile and a configurable installation-wide capacity (default 2).
Chat uses a bounded per-profile FIFO, typed provider streaming, centralized provenance-accounted
context, first-chat learning activation, and isolated conversation/diagnostic persistence.
Assistant presentation remains M006B.

## Requirements

- Linux, initially Ubuntu, Debian, or a Debian-derived distribution.
- CPython 3.12 or newer.
- Development dependencies installed explicitly by a maintainer. Application startup and tests do
  not install or download dependencies.

Jarvis-CLI has no runtime Python dependencies through Milestone 006A and performs no external
network access or telemetry. Local generation uses authenticated IPv4 loopback HTTP/SSE only
between Core and its owned `llama-server` process.

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
