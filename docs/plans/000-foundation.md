# Milestone 000 — Repository and Security Foundation ExecPlan

Status: **NOT STARTED**
Last updated: 2026-08-10 America/Recife

## Purpose and user outcome

Milestone 000 establishes the smallest runnable, local-only Jarvis-CLI foundation required before any profile, model, chat, IPC, or host-capability work begins. It fixes the persistence, diagnostic, path, and installation-protection contracts that every later data-producing or security-sensitive subsystem will consume.

When complete, maintainers can safely initialize and inspect an empty user-local Jarvis environment under XDG paths, apply an idempotent empty-database migration, emit bounded redacted infrastructure diagnostics, account for foundation-owned storage, and evaluate active-installation protection through internal APIs and tests. Automated and manual verification use disposable state exclusively.

Milestone-specific terminology:

- **Product defaults version:** the version of centrally packaged reset/default values, independent of the database schema version.
- **Migration ledger:** the only initial production database table, recording applied immutable migrations.
- **File identity:** Linux filesystem metadata including device, inode, and file type, used with path ancestry rather than path strings alone.
- **Reservation:** capacity claimed before a bounded write and subsequently committed or released.
- **Active installation:** the code and metadata from which the running Jarvis process was loaded. A different clone is not protected merely because it has the same name.

No assistant or ordinary end-user command exists at this milestone.

## Scope

This plan implements exactly the Milestone 000 definition in `ROADMAP.md` and the applicable contracts in `AGENTS.md`, especially sections 3–7, 34, 41–44, 62–66, 94, 111, 129, and 136–145.

Included deliverables:

- Python package and controlled build metadata, GPL-3.0-only license text, README, and essential development documentation.
- Minimum CPython 3.12 support, with explicit completion testing on CPython 3.12 and 3.14 and CPython 3.13 when available.
- XDG config, data, state, cache, and runtime resolution with secure creation and test overrides.
- A central immutable product-default registry with explicit schema and defaults versions.
- SQLite connection and migration infrastructure with only the migration ledger.
- Typed internal errors and safe serialization-ready error representations.
- Injected UTC clock, random event/correlation identifiers, and deterministic test implementations.
- Generic quota, accounting, reservation, rotation-eligibility, and storage-failure primitives, with concrete limits only for foundation-owned storage.
- Recursive centralized secret redaction.
- Bounded deterministic JSON Lines infrastructure diagnostics stored locally.
- Active-installation and filesystem-identity primitives.
- A minimal internal maintainer entry point limited to `python -m jarvis.foundation initialize` and `python -m jarvis.foundation inspect`.
- Isolated unit, integration, migration, and security test infrastructure.

## Non-goals

Milestone 000 must not implement:

- Profiles, the permanent Jarvis profile, profile aliases, profile reset, profile settings, or `jarvis-config`.
- Public `jarvis`, `jarvis-help`, `jarvis-manage`, `jarvis-clear`, installer, updater, or daemon entry points.
- Permanent redaction-probe or installation-check production subcommands.
- Core IPC, sockets, client protocols, TUI, Wayland, desktop integration, or systemd services.
- GGUF discovery, llama.cpp, LLM providers, runtimes, chat, learning, memory, or context construction.
- Policy Engine, Tool Broker, approvals, audit persistence, filesystem tools, process execution, or web access.
- Update checks, remote configuration, telemetry, analytics, or crash upload.
- Profile/model/chat database tables or identifiers.
- A general-purpose safe filesystem mutation API.
- Concrete quota defaults for chat diagnostics, conversations, private notes, downloads, tool-created temporary artifacts, or later memory stores. The milestone introducing each writer must define and enforce its safe limits immediately.

An installation-protection result is not durable authorization. Later mutating tools must re-resolve targets descriptor-relatively and bind validation to execution.

The intentionally deferred Milestone 014 web-provider and Milestone 019B release-signing decisions remain undecided.

## Current progress

Milestone status: **NOT STARTED**

- **DONE:** none.
- **IN PROGRESS:** none.
- **NOT STARTED:** every implementation and verification item listed below.

| Work item | Status |
|---|---|
| Package metadata, licensing, and developer documentation | **NOT STARTED** |
| Typed errors, clock, and identifiers | **NOT STARTED** |
| XDG path resolution and secure initialization | **NOT STARTED** |
| Versioned product-default registry | **NOT STARTED** |
| SQLite connection and migration ledger | **NOT STARTED** |
| Generic quota and reservation primitives | **NOT STARTED** |
| Secret redaction | **NOT STARTED** |
| Structured infrastructure diagnostic sink | **NOT STARTED** |
| Filesystem and installation identity | **NOT STARTED** |
| Foundation initializer and inspector | **NOT STARTED** |
| Automated and manual verification | **NOT STARTED** |
| Final scope and contract reconciliation | **NOT STARTED** |

Progress log:

- 2026-08-10 America/Recife — Repository inspected and governing documents read in full. `ROADMAP.md` explicitly says Milestone 000 has not started. No implementation, package metadata, tests, license file, or earlier ExecPlan exists. The ExecPlan was prepared; no implementation work began.

## Repository state and prerequisites

Repository state verified before this plan was written:

```text
AGENTS.md
PLANS.md
ROADMAP.md
docs/architecture.md
```

There is no `pyproject.toml`, `LICENSE`, `README.md`, `src/`, or `tests/`. There is no previous application implementation to preserve.

Existing user changes that must be preserved:

```text
 M AGENTS.md
 M PLANS.md
 M ROADMAP.md
 M docs/architecture.md
```

The working copies of those documents are authoritative for this milestone. Do not overwrite, revert, format, or otherwise absorb their changes into implementation work.

`ROADMAP.md` explicitly states that Milestone 000 has not started and has no predecessor milestone.

Required implementation tools:

- Git.
- CPython 3.12 or newer. Completion verification must run under 3.12 and 3.14; run under 3.13 when available.
- `pip` with PEP 517 support.
- Hatchling, pytest, Ruff, and mypy from an approved local environment or an explicitly authorized dependency installation.

Current environment discovery:

- CPython 3.14.4 and pytest are available.
- `python3.12`, Ruff, and mypy were not found on `PATH` during planning.
- Dependency acquisition must not be hidden inside tests or application startup.

## Implementation sequence

### 1. **NOT STARTED — Establish metadata and licensing**

- Create `pyproject.toml`, `LICENSE`, `README.md`, and `docs/development.md`.
- Configure a `src` layout, Hatchling backend, GPL-3.0-only metadata, `requires-python = ">=3.12"`, package data, and development extras.
- Document CPython 3.12 and 3.14 as required tested versions and 3.13 as tested when available. Newer versions are not claimed as tested until verification covers them, but metadata does not reject them solely for being newer.
- Declare no runtime dependencies and no console scripts.
- Use these exact `pyproject.toml` sections and policies:
  - `[build-system]`: `requires = ["hatchling>=1.31,<2"]` and `build-backend = "hatchling.build"`;
  - `[project]`: distribution name `jarvis-cli`, initial version `0.0.0`, English foundation description, `README.md`, `requires-python = ">=3.12"`, SPDX license expression `GPL-3.0-only`, the `LICENSE` file, Linux/Python classifiers, and an empty runtime dependency list;
  - omit author/maintainer and project URL values rather than inventing identities or release locations not established by the repository;
  - `[project.optional-dependencies]`: one `dev` extra containing the reviewed pytest, Ruff, and mypy ranges; do not add pytest-asyncio because this milestone has no asynchronous contract;
  - `[tool.hatch.build.targets.wheel]`: package only `src/jarvis`; include the defaults TOML and migration SQL as package data;
  - `[tool.pytest.ini_options]`: `tests` as the test path, strict marker/config behavior, and declared `unit`, `integration`, `migration`, and `security` markers;
  - `[tool.ruff]`: Python 3.12 target, 100-character line length, deterministic formatter settings, and the `E`, `F`, `I`, `UP`, `B`, and `SIM` lint families; any suppression must be narrow and documented;
  - `[tool.mypy]`: Python 3.12 target, strict checking, package-root discovery for the `src` layout, and no automatic third-party stub installation.
- Use compatible direct-version ranges in project metadata rather than adding a dependency-lock generator. A future release/distribution milestone may add reproducible release locking; tests in this milestone must run from a pre-provisioned environment without resolving dependencies over the network.
- Prerequisite: none.
- Validate with:

  ```bash
  python -m pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/jarvis-m000-wheel .
  ```

  Inspect wheel contents and metadata. No network is permitted.
- Rollback: remove only files created by this step if validation fails.

### 2. **NOT STARTED — Add typed common primitives**

- Create typed errors, `Clock`, `SystemClock`, `FakeClock`, identifier value types, random UUID4 generation, and deterministic test generation.
- Prerequisite: step 1.
- Validate with:

  ```bash
  pytest -m unit tests/unit/test_errors.py tests/unit/test_clock_and_ids.py
  mypy src/jarvis/foundation
  ```

- Rollback: no persistent user state is involved.

### 3. **NOT STARTED — Implement XDG semantics**

- Add side-effect-free resolution followed by explicit secure directory initialization.
- Reject relative XDG values. Use `$HOME/.config`, `$HOME/.local/share`, `$HOME/.local/state`, and `$HOME/.cache` when the corresponding config/data/state/cache variable is absent or invalid.
- If `HOME` is unavailable, use the current UID's passwd entry; fail if no absolute home can be established.
- Resolve runtime storage in this order:
  1. use `$XDG_RUNTIME_DIR` only when it is absolute, already exists, is a real directory, is owned by the current UID, and has no group/other permissions;
  2. when `XDG_RUNTIME_DIR` is absent, use `/run/user/<uid>` only when it already exists and passes the same type, ownership, and permission checks;
  3. otherwise fail closed with `xdg.runtime_directory_unavailable`.
- A set but unsafe `XDG_RUNTIME_DIR` fails closed. Never silently fall back to `/tmp`.
- Create the application child `jarvis-cli` securely beneath the validated runtime base. Application config/data/state/cache/runtime directories are mode `0700`; created files are mode `0600`. Verify ownership and type after creation.
- Tests inject a disposable valid `XDG_RUNTIME_DIR` and never use the real runtime directory.
- Prerequisite: step 2.
- Validate with XDG override, config/data/state/cache fallback, runtime absence, valid `/run/user/<uid>` fallback through an injected resolver, permissions, symlink, ownership, and unsafe-runtime tests.
- Recovery: delete only newly created empty paths whose recorded identities still match; never remove pre-existing content.

### 4. **NOT STARTED — Implement centralized versioned defaults**

- Package defaults in `src/jarvis/config/defaults.toml`.
- Represent `defaults_schema_version = 1` and `product_defaults_version = 1` independently.
- Parse using `tomllib`, validate into frozen dataclasses, and expose immutable snapshots through one `DefaultsRegistry`.
- Foundation defaults include only diagnostic event/text/file/total bounds, foundation diagnostic retention, and any backup bound actually consumed by the implemented migration infrastructure.
- Define stable quota-category identifiers without assigning values to future writers. The category representation must allow later milestones to add writer-owned categories without changing reservation semantics.
- Future persisted configuration must record its originating defaults version. Explicit adjacent-version transition functions evolve stored configuration; unsupported gaps or newer versions fail with typed errors.
- Profile creation/reset behavior remains unimplemented. Later reset services must read product defaults from this registry rather than scattered constants or mutable profile state.
- Prerequisite: steps 1–2.
- Validate with schema, immutability, missing/unknown key, unsupported-version, future-category-extension, and deterministic-load tests.
- Recovery: defaults are packaged immutable resources; no user file is mutated.

### 5. **NOT STARTED — Implement SQLite and migration infrastructure**

- Store the database at `$XDG_DATA_HOME/jarvis-cli/jarvis.sqlite3`.
- Add migration `0001_migration_ledger.sql`, creating only `schema_migrations`.
- Open connections through one owner object with explicit close/context-manager lifecycle, `foreign_keys=ON`, bounded `busy_timeout`, `journal_mode=WAL`, `synchronous=FULL`, and explicit transactions.
- Apply all pending migrations under one `BEGIN IMMEDIATE` transaction. Migration SQL must not contain transaction-control statements.
- Record integer version, stable name, SHA-256 checksum, and injected UTC application time.
- Existing matching migrations are skipped. Changed checksums, gaps, unknown higher versions, and downgrade attempts fail closed.
- On failure, roll back the complete pending set and preserve the pre-migration database. A newly created empty failed database may be removed only when its identity still matches.
- Before a future migration changes an existing nonempty application schema, the runner contract requires a consistent SQLite backup created via the SQLite backup API, mode `0600`, and atomically named under the XDG data root. Milestone 000 does not create speculative backups of an empty ledger-only database. If no foundation backup writer exists after implementation review, no concrete backup quota is defined in this milestone.
- Never automatically downgrade, delete, or restore a database after failure. Return the typed failure and preserve recovery evidence.
- Prerequisites: steps 2–4.
- Validate with apply, second-run no-op, concurrent initialization, rollback, checksum mismatch, version gap, newer schema, transaction, connection lifecycle, and file-permission tests.

### 6. **NOT STARTED — Implement generic quotas and accounting**

- Define an extensible `QuotaCategory` value type and generic `QuotaLimit`, `QuotaSnapshot`, `QuotaAccountant`, and `QuotaReservation` contracts.
- Milestone 000 registers and assigns concrete defaults only for `foundation_diagnostics` and, if actually used by step 5, `foundation_database_backups`.
- Reserve future stable category names in documentation—not configured defaults—for chat diagnostics, audit, conversations, private notes, downloads, tool temporary artifacts, cache, and memory. Their milestones own their concrete limits.
- Implement integer byte accounting, overflow/negative validation, thread-safe reservations, and reservation states `pending`, `committed`, and `released`.
- A reservation reduces available capacity immediately. Commit records actual bytes and releases unused capacity. Actual bytes above the reservation require another successful reservation. Release is idempotent; commit-after-release and double-commit fail deterministically.
- Capacity exhaustion permits one reconciliation/rotation attempt supplied by the owning writer. Only closed, unreserved records are eligible, ordered by `(closed_at_utc, stable_record_id)`. Active files and pending reservations are never pruned.
- The foundation diagnostic writer uses authoritative file sizes plus in-process reservations; no quota database table is introduced.
- Initial foundation diagnostic defaults:
  - total infrastructure diagnostics: 256 MiB;
  - per diagnostic file: 8 MiB;
  - per event: 64 KiB;
  - bounded text field: 16 KiB;
  - maximum structured depth: 8;
  - maximum mapping or sequence entries per container: 100;
  - maximum 32 closed files and 30 days of closed-file retention, still subject to the total-byte limit.
- Every later writer must define and enforce safe defaults from the moment that subsystem is introduced.
- Prerequisites: steps 2 and 4.
- Validate with exact-boundary, exhaustion, release, over-commit, unknown category, reconciliation, deterministic rotation eligibility, and multi-thread reservation-race tests.
- Recovery: reconcile from authoritative closed-file sizes after crashes; never infer that an active partial write was committed.

### 7. **NOT STARTED — Implement centralized redaction**

- Expose reusable `Redactor.redact_value()` and `Redactor.redact_text()` APIs returning sanitized values plus redaction/truncation metadata.
- Recursively handle mappings and sequences with bounded depth, item count, and string length.
- Replace sensitive keyed values wholesale for normalized keys such as password/passwd, secret, token, API key, authorization, proxy authorization, cookie/set-cookie, private key, and explicitly supplied sensitive environment-variable names.
- Detect bearer/basic credentials, common API-key assignments, JWT-like tokens, PEM private-key blocks, cookie headers, URL userinfo, and sensitive URL query parameters.
- Never hash or preserve secret length; use stable typed placeholders.
- Bound arbitrary text before expensive matching and discard an overlap region at a truncation boundary so partial token fragments are not persisted.
- Document that false positives favor privacy, while regex redaction cannot guarantee discovery of every unlabeled secret. Callers must minimize payloads instead of treating redaction as permission to log arbitrary content.
- Never enumerate or log the real process environment. Tests supply explicit synthetic sensitive-variable names and values.
- Prerequisites: steps 2 and 4.
- Validate using synthetic nested secrets, URL credentials, private-key material, boundary-straddling values, and oversized/adversarial text.

### 8. **NOT STARTED — Implement structured infrastructure diagnostics**

- Define structured event envelope version 1 with:
  - `schema_version`;
  - `event_id`;
  - RFC 3339 UTC timestamp with six fractional digits and `Z`;
  - optional `correlation_id`;
  - dotted lowercase `event_type`;
  - dotted lowercase `subsystem`;
  - severity enum;
  - sanitized structured `fields`;
  - explicit redaction/truncation metadata.
- Accept only JSON-compatible finite values and string mapping keys.
- Redact and bound before persistence or future rendering.
- Serialize UTF-8 JSON Lines using sorted keys, compact separators, no NaN/Infinity, and one trailing newline.
- Persist under `$XDG_STATE_HOME/jarvis-cli/diagnostics/` only.
- Use a mode-`0600` active `.open` file and atomically rename it when closed. Rotate before exceeding the configured file bound. Apply the foundation diagnostic total/file-count/age limits by pruning only closed eligible files.
- On startup, validate an abandoned `.open` file, truncate an incomplete final line when possible, close it as recovered, and reconcile accounting.
- Reserve the maximum encoded event before append. On `ENOSPC` or partial write, truncate back to the previous offset when safe, release the reservation, mark the sink unhealthy, and raise a typed persistence error without recursively logging the failure.
- Provide `ensure_evidence_capacity()` for later diagnostic/audit producers. Required work must fail before beginning when its owning milestone's minimum evidence reservation cannot be obtained.
- This is infrastructure diagnostics only; chat diagnostics and audit persistence remain later work.
- Prerequisites: steps 3, 6, and 7.
- Validate with deterministic serialization, bounds, rotation, stale-active recovery, quota exhaustion, partial write, and ENOSPC tests.

### 9. **NOT STARTED — Implement installation and filesystem identity**

- Define immutable `FileIdentity`, `PathSnapshot`, `InstallationIdentity`, and `ProtectionDecision` types.
- Capture `lstat` and followed `stat` separately, including device, inode, file type, mode, ownership, size, and modification time where useful for change detection.
- Installation identity version 1 records distribution/version evidence, active import anchor, installation mode (`wheel`, `editable`, `source`, or `ambiguous`), canonical protected roots with ancestor identities, and identities of protected regular files.
- Discover the active package from its loaded module anchor and `importlib.metadata`/PEP 610 evidence where available. The executing editable/source checkout is protected because it is active; a separate clone with different roots and inode identities remains ordinary.
- A candidate is protected when it is a protected root or descendant, an ancestor whose mutation could replace/remove a protected root, resolves through a symlink into one, or is hardlinked to a known protected file.
- Use component-aware ancestry and descriptor-relative traversal with `dir_fd`, `O_DIRECTORY`, and `O_NOFOLLOW` where supported. Never use string-prefix comparison as authority.
- Broken links, special files, inaccessible components, identity changes, incomplete installation evidence, and link swaps produce `AMBIGUOUS`, which later mutation policy must treat as denial.
- A result of `UNPROTECTED` is an assessment, not an execution token. Future tools must repeat descriptor-bound checks immediately before mutation.
- No mutation tool is implemented.
- Prerequisites: steps 2–3.
- Validate with root, child, ancestor, sibling-prefix, separate-clone, symlink, broken-symlink, hardlink, changed-target, special-file, and concurrent link-swap tests.

### 10. **NOT STARTED — Add crash-safe initialization and inspection**

- Implement only `python -m jarvis.foundation initialize` and `python -m jarvis.foundation inspect`.
- Acquire a foundation initialization lock in the secure runtime directory.
- Resolve and validate all XDG paths, create secure directories, apply database migrations, recover infrastructure diagnostics, reserve diagnostic evidence, emit a sanitized initialization event, and atomically write a state marker last.
- The marker contains only foundation/default/database schema versions and a completion timestamp.
- Initialization across separate filesystems is crash-safe and idempotent rather than falsely described as one filesystem transaction: success is visible only after the final marker; a rerun repairs or verifies incomplete prior initialization.
- `inspect` reports resolved paths, directory safety, defaults version, database schema version, migration state, foundation diagnostic health/usage, and active-installation identity state without mutating anything except unavoidable diagnostic evidence explicitly documented by the implementation. Prefer a strictly read-only inspector.
- Output machine-readable JSON suitable for maintainers, without raw exception details or user-facing product prose.
- Redaction and installation behavior are tested through pytest and test-only helpers, not permanent production subcommands.
- Prerequisites: steps 3–9.
- Validate by initializing twice under temporary XDG roots and comparing paths, schema version, permissions, migration rows, and stable state.

### 11. **NOT STARTED — Complete documentation and verification**

- Document architecture ownership, dependency review, commands, XDG behavior, quota limits, migration recovery, and security limitations.
- Run all automated and manual checks.
- Reconcile implementation against the working copies of `AGENTS.md`, `ROADMAP.md`, `PLANS.md`, and `docs/architecture.md`.
- Confirm no later-milestone functionality or empty placeholder package was introduced.
- Prerequisites: all previous steps.
- Rollback: fix implementation or revert only Milestone 000 files; never rewrite authoritative user-modified documents to conceal a deviation.

## Exact files and components affected

Expected new files:

```text
LICENSE
README.md
pyproject.toml
docs/development.md
docs/plans/000-foundation.md

src/jarvis/__init__.py
src/jarvis/foundation/__init__.py
src/jarvis/foundation/__main__.py
src/jarvis/foundation/bootstrap.py
src/jarvis/foundation/clock.py
src/jarvis/foundation/errors.py
src/jarvis/foundation/identifiers.py

src/jarvis/config/__init__.py
src/jarvis/config/defaults.py
src/jarvis/config/defaults.toml

src/jarvis/storage/__init__.py
src/jarvis/storage/xdg.py
src/jarvis/storage/database.py
src/jarvis/storage/migrations.py
src/jarvis/storage/quota.py
src/jarvis/storage/migrations/0001_migration_ledger.sql

src/jarvis/diagnostics/__init__.py
src/jarvis/diagnostics/events.py
src/jarvis/diagnostics/redaction.py
src/jarvis/diagnostics/sink.py

src/jarvis/security/__init__.py
src/jarvis/security/filesystem_identity.py
src/jarvis/security/installation.py

tests/conftest.py
tests/unit/test_clock_and_ids.py
tests/unit/test_defaults.py
tests/unit/test_errors.py
tests/unit/test_events.py
tests/unit/test_quota.py
tests/unit/test_redaction.py
tests/unit/test_xdg.py
tests/integration/test_diagnostic_sink.py
tests/integration/test_initialization.py
tests/migration/test_migrations.py
tests/security/test_installation_protection.py
tests/security/test_no_network_or_telemetry.py
tests/security/test_storage_failures.py
```

Do not create empty CLI, Core, IPC, profile, LLM, runtime, tool, policy, memory, TUI, network, desktop, updater, installer, or packaging directories.

Files deliberately left untouched unless a discovered contradiction requires user-authorized correction:

```text
AGENTS.md
ROADMAP.md
PLANS.md
docs/architecture.md
```

The active ExecPlan itself must be updated throughout implementation as required by `PLANS.md`.

## Contracts and interfaces

### Errors

- `JarvisError` is the internal root exception.
- Domain bases are `ConfigurationError`, `StorageError`, `DiagnosticError`, and `SecurityBoundaryError`.
- Initial stable lowercase machine-readable codes are limited to foundation concerns:
  - `xdg.invalid_path`;
  - `xdg.unsafe_runtime_directory`;
  - `xdg.runtime_directory_unavailable`;
  - `defaults.invalid`;
  - `defaults.unsupported_version`;
  - `database.open_failed`;
  - `database.migration_failed`;
  - `database.incompatible_schema`;
  - `storage.limit_exceeded`;
  - `storage.io_failed`;
  - `diagnostics.invalid_event`;
  - `diagnostics.persistence_failed`;
  - `installation.ambiguous_identity`;
  - `installation.protected_target`;
  - `filesystem.identity_changed`.
- Internal messages, causes, tracebacks, and arbitrary context remain internal.
- `to_safe_dict()` returns envelope version, code, localization-ready message key, optional correlation ID, and an allowlisted sanitized details object suitable for future structured IPC. It is not an IPC implementation.

### Clock and identifiers

- Internal time is a timezone-aware `datetime` normalized to UTC.
- Persisted time is fixed RFC 3339 UTC text with microseconds and `Z`.
- Project planning timestamps use America/Recife; this does not change persistence semantics.
- IDs use typed wrappers around `uuid.UUID`.
- `RandomIdGenerator` uses UUID4 from the standard library.
- `DeterministicIdGenerator` returns a supplied sequence and fails when exhausted.
- Milestone 000 defines only event and correlation IDs; it does not define chat request/session/turn identifiers.

### XDG paths

`XdgPaths` contains absolute application paths for config, data, state, cache, and runtime. Resolution is side-effect free. Creation is explicit and verifies permissions, ownership, file type, and post-creation identity.

Semantic placement:

- Configuration: future user-authored configuration only.
- Data: SQLite and durable backups if any are actually created.
- State: diagnostics and initialization state.
- Cache: rebuildable content only.
- Runtime: locks and other session-lifetime artifacts only.

The runtime resolver never uses `/tmp`. It accepts a safe configured `XDG_RUNTIME_DIR`, or a safe existing `/run/user/<uid>` only when the environment variable is absent, and otherwise fails closed.

### Defaults

`DefaultsRegistry.current()` returns an immutable validated `DefaultsSnapshot`. Database schema version and product-default version are separate integers. Later reset implementations must obtain values from this registry rather than module constants or mutable Jarvis-profile state.

### Migrations

Migrations are immutable, forward-only, consecutively numbered, checksummed package resources. One migration runner owns transaction and ledger writes. Application code never creates schema ad hoc.

### Quotas

Quota categories are extensible stable values rather than a closed enum containing speculative subsystems. The reservation state machine and accounting rules are generic. Each writer owns its category registration, concrete default, reconciliation, and retention policy when introduced.

### Diagnostics

Producers construct typed events; the sink exclusively owns sanitization, bounds, serialization, reservation, file lifecycle, and retention. Raw diagnostic stores expose no context or memory interface.

### Installation protection

`ProtectionDecision` is `PROTECTED`, `UNPROTECTED`, or `AMBIGUOUS`. Only `UNPROTECTED` may be considered by a later mutation system, and it still requires execution-time revalidation.

## Database, migrations, and storage

Initial database location:

```text
$XDG_DATA_HOME/jarvis-cli/jarvis.sqlite3
```

Initial schema:

```sql
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version > 0),
    name TEXT NOT NULL UNIQUE,
    checksum_sha256 TEXT NOT NULL,
    applied_at_utc TEXT NOT NULL
);
```

No profile, model, settings, quota, diagnostic, audit, or history tables are created.

The initial migration creates the ledger and records itself in the same transaction. Migration files are package resources named `NNNN_short_name.sql`. Applied migrations must form a contiguous prefix of packaged migrations and retain matching checksums.

The database owner creates no global connection. Each bootstrap or unit of work owns a connection and closes it deterministically. Sharing a connection across threads is prohibited.

Test databases always reside under a temporary XDG data root. Tests assert that no database, WAL, SHM, backup, diagnostic, or marker file appears beneath real home/XDG locations.

Foundation diagnostics reside in XDG state and use authoritative file-size accounting. Runtime locks reside only in the validated XDG runtime application directory. No future subsystem storage is created.

## Security and privacy considerations

Primary abuse cases and controls:

| Abuse case | Control |
|---|---|
| Relative or attacker-controlled XDG path | Absolute-path validation, ownership/type checks, no-follow creation |
| Missing runtime directory | Safe existing `/run/user/<uid>` fallback only; otherwise typed fail-closed error |
| Set but unsafe runtime path | Reject it; do not fall back to `/run/user/<uid>` or `/tmp` |
| Secret persisted through nested metadata | Central recursive redaction before bounding and serialization |
| Oversized diagnostic denial of service | Depth, item, text, event, file, and total limits plus reservations |
| Unlogged operation after exhaustion | Mandatory evidence reservation before work |
| Concurrent reservations exceed quota | One lock-protected linearizable accounting operation |
| Active log pruned during write | Only closed, unreserved records are eligible |
| Partial or ENOSPC diagnostic write | Restore previous offset or quarantine; unhealthy sink and typed failure |
| Database partially migrated | One explicit transaction and immutable checksum ledger |
| Old/new incompatible database | Refuse downgrade or unknown higher schema |
| Installation matched by misleading prefix | Component and inode identity checks, not prefix strings |
| Symlink or hardlink bypass | `lstat`/`stat`, protected inode inventory, and no-follow traversal |
| TOCTOU or link swap | Changed identity becomes ambiguous; later execution must revalidate descriptor-relatively |
| Development clone falsely protected | Protection follows active roots/inodes, not repository name |
| Active editable clone treated as unrelated | The executing editable source remains protected |
| Hidden network or telemetry | Zero runtime dependencies, socket-denial tests, metadata and static checks |
| Model accesses diagnostics | No model, context builder, model API, or chat subsystem exists |
| Privilege escalation | User-local files only; no sudo or system-path mutation |

Redaction is defense in depth, not permission to collect sensitive material. The foundation records minimal metadata and never reads the real process environment for diagnostics.

Profile and profile/model isolation are not yet applicable because those entities do not exist. Their schema must not be anticipated. Policy, broker, approval, and destructive-operation semantics are likewise deferred because no host capability exists.

No foundation code intentionally opens an internet socket, uploads data, checks for updates, loads remote configuration, or includes analytics/crash-upload SDKs.

## Tests

Test categories and commands:

```bash
pytest -m unit
pytest -m integration
pytest -m migration
pytest -m security
pytest
ruff check .
ruff format --check .
mypy src tests
```

Run the complete suite under CPython 3.12 and 3.14 before completion. Run it under CPython 3.13 when available. Package metadata remains `>=3.12`; passing only on 3.12–3.14 does not claim later versions as tested.

Reusable fixtures:

- `isolated_xdg`: five independent roots under `tmp_path`, all exported explicitly, including a valid mode-`0700` runtime base.
- `temporary_database`: database inside the isolated data root.
- `fake_clock`: controlled UTC timestamps.
- `deterministic_ids`: fixed UUID sequence.
- `temporary_installation`: captured active-root fixture.
- `separate_development_clone`: different path and inode tree.
- Real temporary-filesystem cases for symlinks, hardlinks, special files, changed inodes, and link swaps.
- Thread barrier and fake accountant for quota races.
- Faulting writer raising synthetic `OSError(errno.ENOSPC)`; use a real constrained filesystem only when safely available.
- Synthetic secret corpus; never the process environment.
- Autouse network guard rejecting AF_INET and AF_INET6 socket connection attempts.

Required test coverage:

- **Unit tests:** pure XDG resolution; missing and unsafe runtime behavior; defaults; errors; UTC time and IDs; event validation; nested/bounded redaction; quota state machine; filesystem identity.
- **Integration tests:** secure initialization; second-run idempotency; path separation; diagnostics; rotation/recovery; permissions; state marker behavior after injected failure.
- **Migration tests:** initial apply; rollback; checksum enforcement; idempotency; concurrent runner; version gap; newer schema; failed creation recovery.
- **Security tests:**
  - XDG path isolation and proof that real user state is untouched;
  - unsafe, missing, symlinked, misowned, and wrongly permissioned runtime directories;
  - migration rollback and idempotency;
  - secret redaction and no-secret structured persistence;
  - protected root, child, ancestor, and sibling-prefix behavior;
  - separate development clone allowed while active installation is protected;
  - symlink into/out of the protected tree and link-swap cases;
  - hardlinks to protected files where supported;
  - changed target identity and special files;
  - quota reservation races and capacity exhaustion;
  - simulated ENOSPC and partial writes;
  - diagnostic depth, collection, text, event, file, and total bounds;
  - no intentional network, telemetry, analytics SDK, crash uploader, or remote configuration.
- **End-to-end foundation test:** initialize and inspect under temporary XDG paths only.

The no-network test patches connection primitives before importing/running foundation initialization and fails on any AF_INET/AF_INET6 attempt. A static dependency test confirms that project runtime dependencies are empty and scans imports/configuration for telemetry or remote-service integrations. Optional `strace` verification supplements but does not replace automated tests.

No fake LLM provider is introduced because Milestone 000 has no LLM-facing contract.

## Manual verification

Prerequisites: repository root, a supported Python interpreter, and already available approved development dependencies. These commands do not install anything or use the network.

1. Run focused automated security probes that cover behavior intentionally excluded from the production maintainer CLI:

   ```bash
   pytest -m security \
     tests/security/test_installation_protection.py \
     tests/security/test_no_network_or_telemetry.py \
     tests/security/test_storage_failures.py
   pytest -m unit tests/unit/test_redaction.py
   ```

   Expected: all tests pass using temporary filesystem roots and synthetic secrets.

2. Create disposable XDG roots:

   ```bash
   verification_root="$(mktemp -d /tmp/jarvis-m000.XXXXXX)"
   install -d -m 700 \
     "$verification_root/home" \
     "$verification_root/config" \
     "$verification_root/data" \
     "$verification_root/state" \
     "$verification_root/cache" \
     "$verification_root/runtime"
   export HOME="$verification_root/home"
   export XDG_CONFIG_HOME="$verification_root/config"
   export XDG_DATA_HOME="$verification_root/data"
   export XDG_STATE_HOME="$verification_root/state"
   export XDG_CACHE_HOME="$verification_root/cache"
   export XDG_RUNTIME_DIR="$verification_root/runtime"
   export PYTHONPATH="$PWD/src"
   ```

3. Initialize twice:

   ```bash
   python -m jarvis.foundation initialize --json
   python -m jarvis.foundation initialize --json
   ```

   Expected: both commands succeed; the second reports no new migration; all reported paths remain beneath `verification_root`.

4. Inspect state and permissions:

   ```bash
   python -m jarvis.foundation inspect --json
   find "$verification_root" -printf '%m %p\n' | sort
   ```

   Expected: defaults version 1, database schema version 1, one applied migration, application directories mode `0700`, files mode `0600`, and no profile/application feature state.

5. Confirm no synthetic test secret persisted by the focused tests or initialization:

   ```bash
   if rg -n 'synthetic-password|synthetic-bearer|synthetic-api-key|BEGIN PRIVATE KEY' "$verification_root"; then
     echo 'unexpected synthetic secret found' >&2
     exit 1
   fi
   ```

   Expected: no matches.

6. Verify unsafe runtime rejection:

   ```bash
   chmod 755 "$verification_root/runtime"
   python -m jarvis.foundation initialize --json
   ```

   Expected: nonzero exit with safe code `xdg.unsafe_runtime_directory`; no traceback or secret appears. The command must not create a `/tmp/jarvis-cli-runtime-*` fallback.

7. Optionally verify system calls when `strace` is installed:

   ```bash
   chmod 700 "$verification_root/runtime"
   strace -f -e trace=network python -m jarvis.foundation inspect --json
   ```

   Expected: no AF_INET or AF_INET6 connection attempt.

8. Clean up only the validated temporary root:

   ```bash
   test -n "$verification_root"
   test "${verification_root#/tmp/jarvis-m000.}" != "$verification_root"
   rm -rf -- "$verification_root"
   unset verification_root HOME XDG_CONFIG_HOME XDG_DATA_HOME XDG_STATE_HOME
   unset XDG_CACHE_HOME XDG_RUNTIME_DIR PYTHONPATH
   ```

Manual verification supplements the automated installation-identity, redaction, quota-race, and ENOSPC tests; it does not add production probe commands merely for test convenience.

## Discoveries

- The repository contains specifications only; there is no application implementation to preserve.
- `ROADMAP.md` explicitly states that Milestone 000 has not started.
- All four authoritative documents have existing uncommitted user changes.
- No earlier ExecPlan exists.
- The architecture and roadmap agree that the initial database contains migration infrastructure only.
- CPython 3.14.4 and pytest are available locally; Python 3.12, Ruff, and mypy were not on `PATH` during planning.
- No contradiction requiring an authoritative documentation correction was found.

## Architectural decisions

All decisions below are accepted technical choices for Milestone 000. None selects the deferred Milestone 014 or Milestone 019B product gates.

| Date | Decision and status | Alternatives and rationale | Implications | Reversible |
|---|---|---|---|---|
| 2026-08-10 | **Accepted:** minimum CPython 3.12; package metadata `>=3.12`; completion tests on 3.12 and 3.14, plus 3.13 when available | Python 3.11 conflicts with the stated 3.12+ preference. An artificial upper metadata bound would reject future interpreters without evidence of incompatibility. | Later versions are permitted by metadata but not described as tested until CI verifies them. | Yes, through metadata and compatibility testing. |
| 2026-08-10 | **Accepted:** Hatchling build backend | Preferred over legacy setuptools configuration and custom build scripts; supports the `src` layout and packaged TOML/SQL with small configuration. | Build-only dependency; no runtime behavior. | Yes; wheel metadata is standards-based. |
| 2026-08-10 | **Accepted:** pytest test runner | `unittest` is possible but materially less suitable for parametrized security matrices and reusable isolated fixtures. | Development-only dependency. | Yes. |
| 2026-08-10 | **Accepted:** Ruff and mypy | The standard library provides neither deterministic formatting/lint enforcement nor static type checking. | Development-only; no product runtime impact. | Yes. |
| 2026-08-10 | **Accepted:** no runtime dependencies | Dataclasses, TOML parsing, SQLite, JSON, UUID, paths, threading, and redaction are available in Python 3.12. | Pydantic, Rich, Textual, HTTP clients, and async test plugins remain deferred. | Yes when a later milestone proves need. |
| 2026-08-10 | **Accepted:** safe XDG runtime or existing `/run/user/<uid>`, never `/tmp` | A predictable `/tmp` fallback cannot provide the XDG runtime lifecycle/security contract reliably. Failing closed is safer than broadening runtime placement. | Systems without either safe location cannot initialize until the environment supplies a valid XDG runtime directory. | No for the fail-closed invariant; platform adapters may be added deliberately. |
| 2026-08-10 | **Accepted:** packaged TOML plus frozen dataclasses for defaults | Python constants scatter ownership; JSON is less maintainable; Pydantic would add an unnecessary runtime dependency. | One authoritative resource and typed loader. | Yes through explicit defaults transitions. |
| 2026-08-10 | **Accepted:** standard-library `sqlite3` and explicit SQL migrations | An ORM or migration framework adds dependency and abstraction burden before an application schema exists. | Forward-only immutable SQL and explicit transaction ownership. | Moderately; later layers can wrap this contract. |
| 2026-08-10 | **Accepted:** generic quota state machine, writer-owned concrete defaults | Foundation-wide speculative values would decide later subsystem policy without writer requirements. | Milestone 000 limits only its infrastructure diagnostics and any backup it actually writes. Every later writer must add limits immediately. | No for writer ownership; individual defaults are versioned and reversible. |
| 2026-08-10 | **Accepted:** compact sorted JSON Lines diagnostics | Pickle is unsafe; SQLite logging couples operational evidence to application data; binary formats require dependencies. | Human-inspectable, deterministic, streamable local files. | Yes with envelope-version transitions. |
| 2026-08-10 | **Accepted:** UUID4 IDs | UUID7 is unavailable in the minimum interpreter without custom code or another dependency; counters risk collision. | IDs are opaque and not chronological. | Yes for new identifier classes; persisted formats remain versioned. |
| 2026-08-10 | **Accepted:** aware UTC datetime and fixed RFC 3339 persistence | Floating epoch seconds lose readability/precision; local persisted time is ambiguous. | Fake-clock tests are deterministic. Plan progress timestamps use America/Recife only. | Yes through schema versioning. |
| 2026-08-10 | **Accepted:** migration ledger with SHA-256 checksums | `PRAGMA user_version` alone cannot identify changed migrations; a third-party framework is unnecessary. | Applied migration files become immutable. | Moderately; the ledger can support later runners. |
| 2026-08-10 | **Accepted:** three-state installation protection using roots plus inode identity | Canonical strings alone miss hardlinks and races; hashing whole trees is costly and still does not bind execution. | Ambiguity denies mutation; later tools must revalidate descriptor-relatively. | No for the fail-closed invariant; representation can evolve by version. |
| 2026-08-10 | **Accepted:** only `initialize` and `inspect` in the maintainer module | Permanent security-test probe commands would unnecessarily enlarge production surface. | Redaction and installation protection use focused automated tests/test-only helpers. | Yes if a production requirement later appears. |
| 2026-08-10 | **Accepted:** crash-safe staged initialization with a final marker | Cross-XDG-root atomic transactions are impossible; claiming one would be misleading. | Partial physical creation is recoverable and success is declared only after the marker. | Yes while preserving idempotency. |
| 2026-08-10 | **Accepted:** GPL-3.0-only SPDX expression | This is the conservative exact interpretation of mandated GPL-3.0; “or later” would grant broader terms not stated by the contract. | Include complete GPLv3 text and compatible dependency metadata. | A licensing change requires user/product authority. |

Direct dependency policy and justification:

- **Hatchling `>=1.31,<2`** — required only because the Python standard library is not a PEP 517 build backend. Reviewed during planning as production/stable, actively maintained, and MIT-licensed. It has no product-runtime telemetry or network behavior. Installation burden is confined to the build environment.
- **pytest `>=9.1,<10`** — required for reusable isolated fixtures, parametrized security matrices, and strong failure reporting. `unittest` is possible but materially less effective for this suite. Reviewed as actively maintained and MIT-licensed. It is development-only and has no application telemetry/network role.
- **Ruff `>=0.15,<0.16`** — required for deterministic formatting and consolidated lint/import checks unavailable in the standard library. Reviewed as actively maintained and MIT-licensed. It is development-only; binary wheels increase development installation size but do not affect users.
- **mypy `>=2.3,<3`** — required to validate typed subsystem boundaries because annotations alone are not checked by the standard library. Reviewed as production/stable, actively maintained, and MIT-licensed. It is development-only and has no application telemetry/network role.

All four licenses are compatible with GPL-3.0-only. Before changing bounds, review direct and transitive licenses, maintenance, telemetry/network behavior, and installation burden again. Dependency tools must never self-update or download during tests or application startup.

## Deviations from the original plan

The initial proposed ExecPlan was corrected before repository creation:

- Removed the artificial `<3.15` Python metadata bound while retaining explicit 3.12/3.14 completion tests.
- Removed `/tmp/jarvis-cli-runtime-<uid>` fallback and replaced it with safe existing `/run/user/<uid>` fallback or typed fail-closed behavior.
- Removed speculative concrete quotas for later writers.
- Removed permanent `redaction-probe` and `installation-check` maintainer subcommands.
- Changed project planning timestamps from America/Sao_Paulo to America/Recife; UTC persistence remains unchanged.

These are pre-implementation review corrections. No roadmap or product-scope deviation occurred.

Any later deviation must record the date and authority, original and replacement behavior, reason and security effect, files/tests affected, and whether `AGENTS.md`, `ROADMAP.md`, or architecture documentation requires an authorized amendment.

## Unresolved issues

No known technical or product issue blocks implementation of Milestone 000.

The local absence of CPython 3.12, Ruff, and mypy is an environment prerequisite, not authorization to install dependencies automatically. Before milestone completion, provide approved local tooling and execute the required version/tool checks.

If `/run/user/<uid>` cannot be safely simulated for a unit test without touching the host, use an injected runtime-base resolver. Production resolution must still inspect the real fixed path and retain fail-closed behavior.

## Completion criteria and evidence

Every criterion remains **NOT STARTED** until implementation and verification.

| Criterion | Status | Required evidence |
|---|---|---|
| Foundation contracts documented and implemented | **NOT STARTED** | Source/docs review plus mypy and focused tests |
| GPL-3.0-only package metadata and license present | **NOT STARTED** | Wheel metadata and license-content inspection |
| Initialization deterministic and idempotent | **NOT STARTED** | Integration test and two-run manual verification |
| XDG semantics and secure permissions enforced | **NOT STARTED** | Unit/security tests and temporary-root inspection |
| Missing/unsafe runtime conditions fail closed without `/tmp` fallback | **NOT STARTED** | Runtime resolver security matrix |
| Defaults centralized and versioned | **NOT STARTED** | Defaults tests and no duplicate default constants |
| Migration ledger only; apply/rollback/idempotency pass | **NOT STARTED** | Migration suite and schema inspection |
| Typed errors and safe serialization pass | **NOT STARTED** | Unit tests proving no traceback/internal cause leaks |
| Generic quota reservations and foundation limits pass | **NOT STARTED** | Race, exhaustion, partial-write, and ENOSPC tests |
| No future-writer concrete limits were introduced | **NOT STARTED** | Defaults/configuration and source review |
| Diagnostics are bounded, redacted, rotated, and local | **NOT STARTED** | Diagnostic/security suites and synthetic fixtures |
| Active installation protected without blocking separate clone | **NOT STARTED** | Symlink/hardlink/ancestry/change security matrix |
| No intentional network or telemetry exists | **NOT STARTED** | Zero runtime dependencies, socket guard, static review, optional `strace` |
| Tests never touch real Jarvis/user state | **NOT STARTED** | Autouse isolated-XDG assertions |
| CPython support verified | **NOT STARTED** | Full suite on 3.12 and 3.14; 3.13 when available |
| No later milestone functionality exists | **NOT STARTED** | Tree, API, schema, and command-surface review |
| Full repository checks pass | **NOT STARTED** | pytest, Ruff, mypy, wheel build, and `git diff --check` |
| Manual verification completed in temporary state | **NOT STARTED** | Commands and summarized output recorded here |
| Final repository status reconciled | **NOT STARTED** | `git status --short` with pre-existing user changes preserved |

Milestone 000 remains **NOT STARTED** until all criteria become **DONE** with recorded evidence and no unresolved issue blocks its objective.

## Handoff summary

Exact next action: independently review this ExecPlan against the working copies of `AGENTS.md`, `ROADMAP.md`, `PLANS.md`, and `docs/architecture.md`. Do not begin implementation without explicit authorization. When implementation is authorized, mark only the first sequence item **IN PROGRESS**, update the progress log with an America/Recife timestamp, and add its tests alongside its behavior.

Current failing tests: none have been run because no implementation or test suite exists.

Important local state:

- Milestone 000 is **NOT STARTED**.
- Every implementation item is **NOT STARTED**.
- The authoritative documents contain pre-existing uncommitted user changes that must be preserved.
- No dependencies have been installed.
- No application source, project metadata, license, README, or tests have been created.

Hazards:

- Never use `/tmp` as a production runtime-directory fallback.
- Never assign concrete quotas to future writers in this milestone.
- Never expose test probes as permanent production commands without a production requirement.
- Never treat a canonical path string or prior protection decision as mutation authority.
- Never persist before centralized redaction and quota reservation.
- Never let tests resolve or initialize the user's real XDG state.

The plan is self-contained and ready for independent review. No unresolved product decision blocks Milestone 000.
