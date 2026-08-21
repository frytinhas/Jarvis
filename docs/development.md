# Foundation, profile-domain, Core IPC, and configuration-client development

## Scope

Milestones 000–003 contain repository/security infrastructure, the service-level profile domain,
one foreground Core with versioned Unix-domain IPC, and a thin profile-first configuration client.
They deliberately have no model, chat, policy, broker, host tool, updater, installer, TUI, network
subsystem, assistant client, or executable profile alias.
`AGENTS.md` is the product authority, `ROADMAP.md` defines milestone boundaries, `PLANS.md` defines
execution discipline, and `docs/plans/000-foundation.md` plus
`docs/plans/001-profile-system.md` are predecessor evidence records;
`docs/plans/002-core-ipc.md` is predecessor evidence and
`docs/plans/003-profile-config-client.md` is the M003 execution record.

## Supported development interpreters

The package requires CPython 3.12 or newer. Milestone completion requires the complete test suite on
CPython 3.12 and 3.14, and on 3.13 when it is available. An interpreter not present locally is a
reported completion blocker; tests must not download or install one.

Development tools are declared only in the `dev` optional extra. Hatchling is build-only; pytest,
Ruff, and mypy are development-only. The application has zero runtime dependencies. Tooling must be
provisioned explicitly before checks are run and must never be acquired by application startup or
the test suite.

## Required checks

Run from the repository root in an already provisioned environment:

```bash
pytest -m unit
pytest -m integration
pytest -m migration
pytest -m security
pytest
ruff check .
ruff format --check .
mypy src tests
python -m pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/jarvis-m003-wheel .
git diff --check
```

The wheel must contain only the `jarvis` package and its packaged TOML/SQL resources. Its
metadata must report GPL-3.0-only, Python >=3.12, and no `Requires-Dist` entry except optional `dev`
requirements guarded by the `extra == "dev"` marker. It must declare `jarvisd`, `jarvis-config`,
and `jarvis-help` with their documented targets, omit a public `jarvis` or profile command, and
retain zero runtime dependencies.

## Disposable XDG verification

Never initialize against a maintainer's real Jarvis or XDG state. Create five independent roots and
an isolated home:

```bash
verification_root="$(mktemp -d /tmp/jarvis-m000.XXXXXX)"
install -d -m 700 \
  "$verification_root/home" \
  "$verification_root/config" \
  "$verification_root/data" \
  "$verification_root/state" \
  "$verification_root/cache" \
  "$verification_root/runtime"
HOME="$verification_root/home" \
XDG_CONFIG_HOME="$verification_root/config" \
XDG_DATA_HOME="$verification_root/data" \
XDG_STATE_HOME="$verification_root/state" \
XDG_CACHE_HOME="$verification_root/cache" \
XDG_RUNTIME_DIR="$verification_root/runtime" \
PYTHONPATH=src \
python -m jarvis.foundation initialize --json
```

With the same disposable environment, `PYTHONPATH=src python -m jarvis.core --foreground` starts
the Core. It creates only `core.lock`, `core.sock`, and `core-runtime.json` under the application
runtime directory. `jarvis-config` then performs profile selection and mutation only through IPC;
logical aliases never create files. Use the internal client library or test support for protocol
checks. Clean shutdown removes the socket and metadata while the safe reusable lock file may remain.

Production runtime resolution never falls back to `/tmp`. A safe absolute `XDG_RUNTIME_DIR` or safe
existing `/run/user/<uid>` is required. `/tmp` is used above only as a disposable test container
whose explicitly created `runtime` child is supplied as `XDG_RUNTIME_DIR`.

Remove only the validated disposable root after verification. Do not reuse broad environment
variables or unvalidated paths as recursive deletion targets.

## Security reporting

Foundation diagnostics are local infrastructure evidence, not model memory. Producers minimize
payloads; centralized redaction is defense in depth and is not permission to collect arbitrary
secrets. Report a suspected security defect without attaching real credentials or private user data.

## Foundation and profile storage/recovery contracts

Migrations are consecutive, forward-only packaged SQL resources with SHA-256 checksums and no
migration-owned transaction-control statements. One `BEGIN IMMEDIATE` transaction owns the complete
pending set. Failure rolls the set back and preserves the database for inspection; the application
never downgrades, restores, or deletes a nonempty database automatically. Migration 0002 adds the
seven profile-domain tables documented in the M001 ExecPlan. Migration 0003 adds installation
runtime locations, durable read-only model records/path history, and profile-model associations.
Jarvis bootstrap follows migration and completes before initialization is published.

Foundation infrastructure diagnostics are stored only in XDG state. Defaults are 256 MiB total,
8 MiB per file, 64 KiB per event, 16 KiB per text value, depth 8, 100 entries per container, at most
32 closed files, and 30 days for eligible closed files. Only closed, unreserved files may be pruned.
Every append reserves capacity first. A partial write or ENOSPC attempt restores the prior offset
where possible, releases the reservation, and makes the sink unhealthy instead of recursively
logging the failure.

Active-installation assessment is three-state: `protected`, `unprotected`, or `ambiguous`.
Canonical path strings are not authorization. Roots, descendants, ancestors, symlink targets,
protected hardlink identities, changed targets, and special files are evaluated with current inode
evidence and component-aware traversal. `ambiguous` must be denied by later mutation policy, and an
`unprotected` result must still be revalidated at execution time. A genuinely separate clone remains
ordinary user data; the source/editable checkout currently supplying imported Jarvis code is active
and protected.

Initialization is staged because config/data/state/cache/runtime may be separate filesystems. A
private runtime lock serializes initialization, migrations and redacted evidence complete first, and
an atomic state marker is written last. A missing marker means initialization did not complete even
if recoverable directories, a migrated database, or closed diagnostic evidence remain. Rerunning is
the supported recovery action.

Redaction favors privacy and may produce false positives. It cannot prove discovery of every
unlabeled secret, so callers must minimize diagnostic fields. Diagnostics and the inspector expose
no model-context or memory interface. Registry diagnostics contain only bounded counters, reason
classes, durations, and explicitly permitted identifiers; never paths, metadata, configuration,
exception text, model bytes, or environment values.
