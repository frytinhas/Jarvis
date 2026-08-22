# Jarvis-CLI

Jarvis-CLI is a privacy-first, telemetry-free local AI assistant for Linux. The implemented domain
currently includes the security foundation, persistent profile identity/configuration, one
foreground Jarvis Core behind versioned local IPC, the profile-first `jarvis-config` client, a
read-only local GGUF registry, a Core-owned per-profile `llama-server` runtime manager, the
client-neutral M006A chat pipeline, the M006B simple CLI presenter, and the M006C permanent
user-local installation/socket-activation foundation. Installed use exposes canonical `jarvis`
from a Jarvis-managed private environment, while `python -m jarvis.cli` remains the development
entry. No host tool, external-network feature, TUI, dynamic physical profile command, updater, or
profile model autostart exists yet.

The current implementation provides user-local XDG storage, versioned defaults, SQLite migrations,
bounded redacted infrastructure diagnostics, quota reservations, typed errors, active-installation
identity checks, and Core-owned profile/model lifecycle/configuration APIs. `jarvis-config`,
`jarvis-manage`, and `jarvis-help` are thin local clients; logical profile aliases are data mappings
only and do not create commands. GGUF discovery is explicit, bounded, descriptor-based, and
read-only. `jarvis-manage` can start, inspect, stop, and switch authenticated loopback-only model
runtimes, with one runtime per profile and a configurable installation-wide capacity (default 2).
Chat uses a bounded per-profile FIFO, typed provider streaming, centralized provenance-accounted
context, first-chat learning activation, and isolated conversation/diagnostic persistence.
The simple CLI intercepts its bounded M006B slash-command set, exposes learning state and five
visible logging modes, and never accesses persistence, runtime handles, or providers directly.

## Requirements

- Linux, initially Ubuntu, Debian, or a Debian-derived distribution.
- CPython 3.12 or newer.
- Development dependencies installed explicitly by a maintainer. Application startup and tests do
  not install or download dependencies.

Jarvis-CLI has no runtime Python dependencies through Milestone 006C and performs no external
network access or telemetry. Local generation uses authenticated IPv4 loopback HTTP/SSE only
between Core and its owned `llama-server` process.

## Development commands

```bash
PYTHONPATH=src python -m jarvis.foundation initialize --json
PYTHONPATH=src python -m jarvis.foundation inspect --json
PYTHONPATH=src python -m jarvis.core --foreground
PYTHONPATH=src python -m jarvis.cli --help
PYTHONPATH=src python -m jarvis.cli "olá"
PYTHONPATH=src python -m jarvis.cli --profile-alias work "olá"
PYTHONPATH=src python -m jarvis.manage --help
```

M006C's explicit local-wheel bootstrap is `python -m jarvis.installation PATH/TO/WHEEL`. It creates
`$XDG_DATA_HOME/jarvis-cli/installation/venv`, collision-safe fixed launchers under
`$HOME/.local/bin`, a mode-0600 installation manifest under XDG state, and `jarvisd.socket` plus
`jarvisd.service` under the user systemd configuration root. It never edits shell startup files;
when `$HOME/.local/bin` is absent from PATH it reports the exact action. Production Core is a
foreground socket-activated service, not a launcher-spawned background process. The protocol is documented in
[`docs/ipc-protocol.md`](docs/ipc-protocol.md).

Always point all five XDG roots, including a pre-created mode-`0700` `XDG_RUNTIME_DIR`, at a
disposable location when evaluating foundation behavior. See
[`docs/development.md`](docs/development.md) for the complete procedure.

## License

Jarvis-CLI is licensed under GPL-3.0-only. See [`LICENSE`](LICENSE).
