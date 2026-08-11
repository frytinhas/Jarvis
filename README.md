# Jarvis-CLI

Jarvis-CLI is a privacy-first, telemetry-free local AI assistant for Linux. The project is in its
security-foundation milestone: no assistant, profile, model runtime, host tool, network feature, or
public Jarvis command exists yet.

The current foundation is designed to provide user-local XDG storage, versioned defaults, SQLite
migrations, bounded redacted infrastructure diagnostics, quota reservations, typed errors, and
active-installation identity checks. Local model inference and all user-facing clients are later
milestones.

## Requirements

- Linux, initially Ubuntu, Debian, or a Debian-derived distribution.
- CPython 3.12 or newer.
- Development dependencies installed explicitly by a maintainer. Application startup and tests do
  not install or download dependencies.

Jarvis-CLI has no runtime Python dependencies in Milestone 000 and performs no intentional network
access or telemetry.

## Foundation commands

The only executable development surface in this milestone is module based:

```bash
PYTHONPATH=src python -m jarvis.foundation initialize --json
PYTHONPATH=src python -m jarvis.foundation inspect --json
```

Always point all five XDG roots, including a pre-created mode-`0700` `XDG_RUNTIME_DIR`, at a
disposable location when evaluating foundation behavior. See
[`docs/development.md`](docs/development.md) for the complete procedure.

## License

Jarvis-CLI is licensed under GPL-3.0-only. See [`LICENSE`](LICENSE).

