# Milestone 000 — Repository and Security Foundation ExecPlan

Status: **DONE**
Last updated: 2026-08-11 America/Sao_Paulo

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

Milestone status: **DONE**

- **DONE:** implementation sequence steps 1–11, documentation, the complete required CPython 3.12
  and CPython 3.14 verification matrices, manual verification, and final scope reconciliation.
- **IN PROGRESS:** none.
- **NOT STARTED:** none.

| Work item | Status |
|---|---|
| Package metadata, licensing, and developer documentation | **DONE** |
| Typed errors, clock, and identifiers | **DONE** |
| XDG path resolution and secure initialization | **DONE** |
| Versioned product-default registry | **DONE** |
| SQLite connection and migration ledger | **DONE** |
| Generic quota and reservation primitives | **DONE** |
| Secret redaction | **DONE** |
| Structured infrastructure diagnostic sink | **DONE** |
| Filesystem and installation identity | **DONE** |
| Foundation initializer and inspector | **DONE** |
| Automated and manual verification | **DONE** |
| Final scope and contract reconciliation | **DONE** |

Progress log:

- 2026-08-10 America/Recife — Repository inspected and governing documents read in full. `ROADMAP.md` explicitly says Milestone 000 has not started. No implementation, package metadata, tests, license file, or earlier ExecPlan exists. The ExecPlan was prepared; no implementation work began.
- 2026-08-10 America/Recife — Implementation authorization received. Re-read all five governing/plan files in full and independently confirmed every Milestone 000 item was `NOT STARTED`. Pre-implementation `git status --short` was clean. Contrary to the planning snapshot, a tracked 674-line GPLv3 `LICENSE` is already present; there is still no package metadata, source, or test tree. Step 1 marked `IN PROGRESS` before implementation.
- 2026-08-10 America/Recife — Revalidated planned dependency ranges against official PyPI metadata before writing `pyproject.toml`: Hatchling 1.31.0 (`Python >=3.10`, MIT), pytest 9.1.1 (MIT), Ruff 0.15.22 (published CPython-independent platform wheels and advertises Python 3.14 compatibility), and mypy 2.3.0 (`Python >=3.10`, MIT, CPython 3.12–3.14 classifiers/wheels) exist. The planned ranges remain suitable for CPython >=3.12, so no dependency deviation is required. No runtime dependency is authorized or planned.
- 2026-08-10 America/Recife — Step 1 `DONE`. Created `pyproject.toml`, `README.md`, `docs/development.md`, and the minimal `src/jarvis/__init__.py`; preserved the existing GPLv3 `LICENSE`. Installed only the authorized build/development tools into disposable `/tmp/jarvis-m000-venv` after explicit approval. `/tmp/jarvis-m000-venv/bin/python -m pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/jarvis-m000-wheel .` passed. Wheel inspection found only `jarvis/__init__.py` and distribution metadata/license; metadata reports GPL-3.0-only, `Requires-Python: >=3.12`, and only extra-guarded development requirements. Step 2 marked `IN PROGRESS`.
- 2026-08-10 America/Recife — Step 2 `DONE`. Added typed error bases and safe envelopes, UTC system/fake clocks with fixed RFC 3339 formatting, typed UUID4 event/correlation identifiers, and deterministic ID generation. `PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m unit tests/unit/test_errors.py tests/unit/test_clock_and_ids.py` passed 9 tests; `/tmp/jarvis-m000-venv/bin/mypy src/jarvis/foundation` passed. Step 3 marked `IN PROGRESS`.
- 2026-08-10 America/Recife — Step 3 `DONE`. Added side-effect-free XDG resolution, absolute persistent fallbacks, strict configured-runtime and injected `/run/user/<uid>` validation, secure mode-0700 application-directory initialization, rollback of identity-matching empty creations, and private-file validation. `PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m unit tests/unit/test_xdg.py` passed 12 tests; strict mypy passed for foundation/storage. No production `/tmp` fallback exists. Step 4 marked `IN PROGRESS`.
- 2026-08-10 America/Recife — Step 4 `DONE`. Added the packaged TOML defaults registry with independent schema/product version 1, frozen validated snapshots, explicit unsupported-transition failure, and only foundation diagnostic limits. `PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m unit tests/unit/test_defaults.py` passed 10 tests; strict mypy passed for config/foundation. Step 5 marked `IN PROGRESS`.
- 2026-08-10 America/Recife — Step 5 discovery recorded before migration files were created: the planned paths `src/jarvis/storage/migrations.py` and `src/jarvis/storage/migrations/0001_migration_ledger.sql` cannot coexist because a POSIX directory and regular file cannot share one pathname. The runner module remains `migrations.py`; packaged immutable SQL moves to `src/jarvis/storage/migration_files/`. This is a path-only deviation with no contract or milestone-scope change.
- 2026-08-10 America/Recife — Step 5 `DONE`. Added securely created mode-0600 SQLite connections, explicit lifecycle/transactions and required pragmas; immutable consecutive SQL resources; one-transaction `BEGIN IMMEDIATE` migration application; checksum/name/version validation; and schema inspection. Migration execution deliberately avoids `sqlite3.executescript` because it can implicitly commit and violate atomic rollback. `PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m migration tests/migration/test_migrations.py` passed 10 tests including concurrent initialization and full rollback; strict mypy passed for storage/foundation. No backup writer exists, so no backup category/default is introduced. Step 6 marked `IN PROGRESS`.
- 2026-08-10 America/Recife — Step 6 `DONE`. Added extensible stable quota categories, validated limits/snapshots, lock-linearized reservations, pending/committed/released transitions, authoritative reconciliation, and deterministic closed-record rotation eligibility. `PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m unit tests/unit/test_quota.py` passed 12 tests including the multi-thread capacity race; strict mypy passed for storage. Step 7 marked `IN PROGRESS`.
- 2026-08-10 America/Recife — Step 7 `DONE`. Added centralized recursive keyed/pattern redaction with fixed placeholders, explicit synthetic environment-name support, and pre-regex depth/item/UTF-8 text bounds with a discarded truncation overlap. `PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m unit tests/unit/test_redaction.py` passed 13 tests; strict mypy passed for diagnostics. Step 8 marked `IN PROGRESS`.
- 2026-08-10 America/Recife — Step 8 `DONE`. Added version-1 typed event validation and a local state-only diagnostic sink owning redaction, deterministic JSONL serialization, event/file/total reservations, rotation/retention, abandoned-active recovery, mode/ownership checks, and unhealthy failure behavior. Focused event tests passed 10; diagnostic integration tests passed 7, including simulated partial write and ENOSPC restoration; strict mypy passed for diagnostics. Step 9 marked `IN PROGRESS`.
- 2026-08-10 America/Recife — Step 9 `DONE`. Added separate lstat/followed stat snapshots, descriptor-relative no-follow ancestor inspection, versioned source/editable/wheel installation evidence, protected regular-file inode inventory, and three-state assessment. `PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m security tests/security/test_installation_protection.py` passed 10 tests; strict mypy passed for security. Step 10 marked `IN PROGRESS`.
- 2026-08-10 America/Recife — Step 10 `DONE`. Added the private runtime initialization lock, staged initializer, redacted initialization evidence, last-write atomic state marker, strictly read-only inspector, and only the two authorized maintainer module commands. `PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m integration tests/integration/test_initialization.py tests/integration/test_diagnostic_sink.py` passed 12 tests; strict mypy passed for foundation/diagnostics. Step 11 marked `IN PROGRESS`.
- 2026-08-10 America/Recife — Locally available Step 11 verification passed on CPython 3.14.4: unit 66, integration 14, migration 10, security 16, and complete suite 106 tests; Ruff lint and format checks passed; strict mypy passed 36 source/test files; the offline wheel build and metadata/resource inspection passed; `git diff --check` passed.
- 2026-08-10 America/Recife — Manual verification passed under `/tmp/jarvis-m000.5TI6QX` and the validated disposable root was removed. First initialization applied migration 1, second applied none, read-only inspection reported schema/default versions 1, all application directories were mode 0700 and files mode 0600, the synthetic-secret scan was empty, and unsafe runtime mode 0755 returned `xdg.unsafe_runtime_directory` with no traceback or `/tmp` runtime fallback. Optional `strace` could not run because this sandbox denies ptrace (`PTRACE_TRACEME: Operation not permitted`).
- 2026-08-10 America/Recife — Final re-read of all 3,570 lines of `AGENTS.md` and the Milestone 000 `ROADMAP.md` definition completed after implementation. Tree/schema/API review found no profiles, Core/IPC, model, chat, policy, broker, host tool, public command, installer/updater, TUI, network, telemetry, or other Milestone 001+ implementation. Step 11 remains `IN PROGRESS` solely because CPython 3.12 is unavailable locally; CPython 3.13 is also unavailable and is required only when available.
- 2026-08-10 America/Recife — A final repeated matrix run reopened Step 5 after its concurrent migration test exposed a WAL-negotiation race (`database is locked` / `disk I/O error`) before `BEGIN IMMEDIATE`. Earlier focused/full runs had passed, demonstrating the race was intermittent. Step 5 is temporarily `IN PROGRESS` alongside already-started Step 11 verification; connection initialization is being serialized in-process while migration ownership remains SQLite-transactional.
- 2026-08-10 America/Recife — Step 5 returned to `DONE`. A module-private reentrant lock now serializes only same-process database file creation and PRAGMA/WAL negotiation; connections do not share state and `BEGIN IMMEDIATE` remains the migration concurrency authority. The formerly flaky two-thread test passed 20 consecutive focused runs, then the complete 10-test migration suite passed; Ruff and mypy passed for the changed module.
- 2026-08-10 America/Recife — Final post-race-fix matrix passed on CPython 3.14.4: unit 66, integration 14, migration 10, security 16, and full 106; Ruff lint/format and strict mypy passed; final offline wheel build and resource/metadata assertions passed; `git diff --check` passed. Final status is one modified tracked ExecPlan plus new `README.md`, `docs/development.md`, `pyproject.toml`, `src/`, and `tests/`; the tracked `LICENSE` and all authoritative documents remain unchanged.
- 2026-08-11 America/Sao_Paulo — Independent completion review reproduced five foundation
  defects: abandoned diagnostic hardlinks could truncate an external file; first-open WAL
  negotiation was not serialized across processes; installed wheel/editable metadata was omitted
  from protected installation roots; diagnostic validation/materialization was not bounded before
  recursion/container traversal and composite/key-embedded secrets could persist; and private
  inspected/opened paths retained check/use races. Milestone 000 was reopened for narrow fixes; no
  Milestone 001 work began.
- 2026-08-11 America/Sao_Paulo — Review fixes completed. Private persistent files now reject
  multiple hardlinks and descriptor/path identities are compared; SQLite opens through the
  validated `/proc/self/fd` identity while an OS `flock` serializes cross-process WAL negotiation;
  diagnostic recovery/close is descriptor-bound and directory changes are fsynced; event
  validation and recursive sanitization are bounded without whole-container materialization;
  composite sensitive keys and unsafe error-envelope names/keys fail safely; installation capture
  includes active distribution metadata, validates the import anchor and ancestors, and detects
  in-place changes. Added `.gitignore` so generated bytecode/tool caches cannot enter the initial
  commit. The formerly failing two-process migration probe passed 50 consecutive trials.
- 2026-08-11 America/Sao_Paulo — Final independent matrix passed on CPython 3.14.4: unit 75,
  integration 17, migration 12, security 20, and full 124 tests; Ruff lint/format, strict mypy,
  `git diff --check`, offline wheel/resource/metadata inspection, installed-wheel protection, and
  disposable two-run manual verification all passed. CPython 3.12 remains unavailable and remains
  the only completion blocker.
- 2026-08-11 America/Sao_Paulo — CPython 3.12.13 became available at
  `/home/gabri/.local/bin/python3.12`, resolving to the uv-managed standalone interpreter at
  `/home/gabri/.local/share/uv/python/cpython-3.12.13-linux-x86_64-gnu/bin/python3.12`. Created the
  isolated `/tmp/jarvis-m000-py312-venv` and installed only the approved Hatchling 1.32.0, pytest
  9.1.1, Ruff 0.15.22, and mypy 2.3.0 tool ranges. The CPython 3.12 matrix passed unchanged: unit
  75, integration 17, migration 12, security 20, and full 124 tests; source imports, Ruff
  lint/format, strict mypy, wheel build, clean `--no-deps` wheel installation, installed imports,
  packaged defaults TOML and migration SQL, empty runtime dependencies, `pip check`, disposable
  XDG initialize twice/inspect, permissions, secret scan, and unsafe-runtime rejection all passed.
  The first wheel-metadata probe stopped on quoting in the verification command; the corrected
  probe passed and exposed no project defect. No compatibility bug or implementation/test change
  was required. Step 11 and every completion criterion are `DONE`; Milestone 001 remains
  **NOT STARTED**.

## Repository state and prerequisites

Repository state verified before this plan was written:

```text
AGENTS.md
PLANS.md
ROADMAP.md
docs/architecture.md
```

There is no `pyproject.toml`, `README.md`, `src/`, or `tests/`. A complete tracked GPLv3
`LICENSE` already exists. There is no previous application implementation to preserve.

Existing user changes observed during the original planning session were:

```text
 M AGENTS.md
 M PLANS.md
 M ROADMAP.md
 M docs/architecture.md
```

At the implementation preflight, `git status --short` was clean. The working copies remain
authoritative and must not be modified unless an actual contradiction is discovered.

At the original planning snapshot, `ROADMAP.md` stated that Milestone 000 had not started and had no
predecessor milestone. Its stale current-status sentence is corrected by the independent review.

Required implementation tools:

- Git.
- CPython 3.12 or newer. Completion verification must run under 3.12 and 3.14; run under 3.13 when available.
- `pip` with PEP 517 support.
- Hatchling, pytest, Ruff, and mypy from an approved local environment or an explicitly authorized dependency installation.

Current environment discovery:

- CPython 3.14.4 and pytest 9.0.2 are available through `python3`.
- `python` is not on `PATH`; commands use `python3` locally without changing the documented
  portable command spelling.
- `python3.12`, `python3.13`, Hatchling, Ruff, and mypy were not found on `PATH` or as installed
  Python 3.14 distributions during implementation preflight.
- Dependency acquisition must not be hidden inside tests or application startup.
- Completion verification found CPython 3.12.13 at `/home/gabri/.local/bin/python3.12` and used
  only `/tmp/jarvis-m000-py312-venv` plus the clean installed-wheel environment
  `/tmp/jarvis-m000-py312-wheelverify.haP41M/install-venv`. CPython 3.13 remains unavailable, so
  its explicitly conditional run was not required.

## Implementation sequence

### 1. **DONE — Establish metadata and licensing**

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

### 2. **DONE — Add typed common primitives**

- Create typed errors, `Clock`, `SystemClock`, `FakeClock`, identifier value types, random UUID4 generation, and deterministic test generation.
- Prerequisite: step 1.
- Validate with:

  ```bash
  pytest -m unit tests/unit/test_errors.py tests/unit/test_clock_and_ids.py
  mypy src/jarvis/foundation
  ```

- Rollback: no persistent user state is involved.

### 3. **DONE — Implement XDG semantics**

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

### 4. **DONE — Implement centralized versioned defaults**

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

### 5. **DONE — Implement SQLite and migration infrastructure**

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

### 6. **DONE — Implement generic quotas and accounting**

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

### 7. **DONE — Implement centralized redaction**

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

### 8. **DONE — Implement structured infrastructure diagnostics**

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

### 9. **DONE — Implement installation and filesystem identity**

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

### 10. **DONE — Add crash-safe initialization and inspection**

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

### 11. **DONE — Complete documentation and verification**

- Document architecture ownership, dependency review, commands, XDG behavior, quota limits, migration recovery, and security limitations.
- Run all automated and manual checks.
- Reconcile implementation against the working copies of `AGENTS.md`, `ROADMAP.md`, `PLANS.md`, and `docs/architecture.md`.
- Confirm no later-milestone functionality or empty placeholder package was introduced.
- Prerequisites: all previous steps.
- Rollback: fix implementation or revert only Milestone 000 files; never rewrite authoritative user-modified documents to conceal a deviation.

## Exact files and components affected

Expected new files:

```text
.gitignore
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
src/jarvis/storage/migration_files/0001_migration_ledger.sql

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

Files deliberately left untouched unless a discovered contradiction requires correction:

```text
AGENTS.md
ROADMAP.md
PLANS.md
docs/architecture.md
```

The active ExecPlan itself must be updated throughout implementation as required by `PLANS.md`.
Independent review corrected only the stale Milestone 000 status sentence in `ROADMAP.md`; no
roadmap scope, sequence, dependency, or Milestone 001 content changed.

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
- At the original planning snapshot, `ROADMAP.md` stated that Milestone 000 had not started.
- All four authoritative documents have existing uncommitted user changes.
- No earlier ExecPlan exists.
- The architecture and roadmap agree that the initial database contains migration infrastructure only.
- CPython 3.14.4 and pytest are available locally; Python 3.12, Ruff, and mypy were not on `PATH` during planning.
- No contradiction requiring an authoritative documentation correction was found.
- The implementation preflight worktree is clean, so the earlier planning-session record of four
  modified authoritative files is historical rather than current.
- `LICENSE` is a pre-existing tracked 674-line copy of GNU GPL version 3 and requires no rewrite.
- Official package-index evidence on 2026-08-10 confirms all planned development dependency
  ranges exist and remain suitable for CPython >=3.12. No range is stale.
- Python's `sqlite3.Connection.executescript()` may implicitly commit before executing its script,
  which would violate the migration transaction contract. The runner instead splits only complete
  SQLite statements and executes each through `Connection.execute()` inside the owned transaction.
- The foundation migration changes an empty ledger-only database and creates no backup. Therefore
  `foundation_database_backups` is not registered and has no concrete default in Milestone 000.
- The local execution sandbox rejects creation of AF_INET/AF_INET6 sockets with `EPERM` before a
  connection guard can run. The automated no-network test therefore verifies all foundation module
  imports while its patched `socket.create_connection` rejects attempts, and static import/metadata
  checks supplement that runtime guard. No product code attempted network access.
- Full test-tree type checking showed that mypy's `no_site_packages = true` hides the explicitly
  provisioned pytest package; it does not implement the intended "no automatic stub installation"
  rule. Configuration now uses `install_types = false`, so mypy may inspect authorized local
  development packages but can never acquire missing stubs itself.
- Optional manual syscall tracing is unavailable in this sandbox because ptrace is denied. This is
  not a completion blocker because the ExecPlan defines `strace` as supplemental; the autouse
  AF_INET/AF_INET6 guard, all-module import probe, zero-runtime-dependency assertion, and static
  telemetry/network integration scan passed.
- Independent review found the module-private connection lock did not cover separate processes;
  a 50-round two-process probe failed 41 times before the fix. A Linux `flock` on the validated
  database identity now serializes only file creation/WAL PRAGMA negotiation across processes;
  SQLite `BEGIN IMMEDIATE` remains the migration transaction authority.
- A mode-0600 hardlink accepted as an abandoned `.open` diagnostic was truncated during recovery,
  modifying its external inode. Private persistent-file validation now requires link count one and
  recovery/close compares the opened descriptor identity with the path immediately before mutation.
- Wheel inspection showed the package root was protected but `jarvis_cli-*.dist-info` was not.
  Installed and editable discovery now includes the active distribution metadata root and becomes
  ambiguous if that evidence cannot be located.
- Diagnostic fields could raise an untyped `RecursionError`, whole containers were materialized
  before output bounds, and composite/key-embedded secret names bypassed keyed redaction. Typed
  complexity caps, bounded iteration, key-pattern redaction and privacy-favoring composite-key
  detection now precede persistence.

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
| 2026-08-10 | **Accepted:** serialize same-process SQLite connection initialization | Concurrent connections can race during initial WAL negotiation before migration transactions exist. Retrying broad `disk I/O error` failures would risk masking real storage faults. | A module-private lock covers secure creation and PRAGMA negotiation only; connections remain independently owned and cross-process migration serialization remains `BEGIN IMMEDIATE`. | Yes, if a later connection factory provides an equivalent stronger contract. |
| 2026-08-11 | **Accepted; supersedes the same-process-only decision above:** serialize SQLite file creation and WAL negotiation across processes with a Linux `flock` on the already validated database descriptor | Independent testing showed the in-process lock failed in 41/50 two-process trials. A broad retry loop could hide storage faults, while a separate speculative schema lock was unnecessary. | SQLite is opened through `/proc/self/fd/<fd>` so validation and open use one inode. The lock ends after PRAGMA negotiation; migration ownership remains `BEGIN IMMEDIATE`. Linux is the declared platform target. | Yes, if a later connection factory provides an equivalent descriptor-bound cross-process contract. |

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

- 2026-08-10, implementation-authorized technical correction: the original ExecPlan assigned both
  a regular module and a directory to `src/jarvis/storage/migrations`. POSIX cannot represent both.
  SQL package resources use `src/jarvis/storage/migration_files/` while the public runner remains
  `src/jarvis/storage/migrations.py`. Affected files are the runner, wheel-content expectations, and
  migration tests. Security behavior, resource immutability, roadmap scope, and authoritative
  documents are unchanged.
- 2026-08-11, independent-review security corrections: private-file validation now rejects
  hardlinks; SQLite open/WAL negotiation is descriptor-bound and cross-process serialized;
  diagnostics use bounded pre-persistence traversal and descriptor-bound recovery/close;
  installation discovery protects wheel/editable distribution metadata and verifies active anchor,
  ancestors and changed metadata; safe error envelopes reject unstable or secret-identifying keys;
  and `.gitignore` is included in repository metadata. These changes correct violated existing
  ExecPlan contracts rather than changing product scope. Affected implementation files are
  `foundation/errors.py`, `foundation/bootstrap.py`, `storage/xdg.py`, `storage/database.py`,
  `diagnostics/events.py`, `diagnostics/redaction.py`, `diagnostics/sink.py`, and
  `security/installation.py`, with corresponding unit/integration/migration/security tests.
  The stale `ROADMAP.md` status sentence was corrected from “not started” to **IN PROGRESS**;
  `AGENTS.md` and `docs/architecture.md` require no contract amendment.

## Unresolved issues

No known technical or product issue blocks or remains open for Milestone 000. CPython 3.13 is
unavailable; its verification was explicitly conditional and is not a completion blocker.

If `/run/user/<uid>` cannot be safely simulated for a unit test without touching the host, use an injected runtime-base resolver. Production resolution must still inspect the real fixed path and retain fail-closed behavior.

## Completion criteria and evidence

Every mandatory criterion is **DONE**.

| Criterion | Status | Required evidence |
|---|---|---|
| Foundation contracts documented and implemented | **DONE** | Independent source/docs review, 124 tests, and strict mypy |
| GPL-3.0-only package metadata and license present | **DONE** | Wheel metadata/resource inspection and preserved 674-line GPLv3 license |
| Initialization deterministic and idempotent | **DONE** | Integration/CLI tests and two-run manual verification |
| XDG semantics and secure permissions enforced | **DONE** | 12 unit tests, security coverage, and temporary-root inspection |
| Missing/unsafe runtime conditions fail closed without `/tmp` fallback | **DONE** | Resolver matrix and manual mode-0755 rejection |
| Defaults centralized and versioned | **DONE** | 10 defaults tests and packaged TOML review |
| Migration ledger only; apply/rollback/idempotency pass | **DONE** | 12 migration tests, 50-round cross-process stress probe, and manual schema inspection |
| Typed errors and safe serialization pass | **DONE** | Error tests and safe CLI failure output |
| Generic quota reservations and foundation limits pass | **DONE** | Unit/security race, exhaustion, partial-write, and ENOSPC tests |
| No future-writer concrete limits were introduced | **DONE** | Defaults and source review; diagnostics only, no backup writer/default |
| Diagnostics are bounded, redacted, rotated, and local | **DONE** | Unit/integration/security suites, hardlink/identity regressions, and manual secret scan |
| Active installation protected without blocking separate clone | **DONE** | 14-case link/inode/ancestry/source/wheel/editable security matrix and installed-wheel probe |
| No intentional network or telemetry exists | **DONE** | Empty runtime dependencies, socket guard, import/static scan; optional strace unavailable due ptrace denial |
| Tests never touch real Jarvis/user state | **DONE** | Autouse isolated HOME and all five XDG roots plus explicit path assertions |
| CPython support verified | **DONE** | Full 124-test suite and marker suites passed on 3.12.13 and 3.14.4; 3.13 unavailable/conditional |
| No later milestone functionality exists | **DONE** | Final tree, API, schema, command-surface, AGENTS/ROADMAP review |
| Full repository checks pass | **DONE** | 124 pytest on 3.12.13 and 3.14.4; Ruff lint/format; strict mypy; wheel build/install/resource/import/dependency checks; `git diff --check` |
| Manual verification completed in temporary state | **DONE** | Two-run/inspect/permissions/secrets/unsafe-runtime procedure recorded above |
| Final repository status reconciled | **DONE** | Final `git status --short` shows only `ROADMAP.md` and this ExecPlan modified for completion evidence |

Milestone 000 is **DONE**. All mandatory completion criteria are satisfied, and no compatibility
defect or unresolved issue remains.

Final locally executed command evidence (CPython 3.14.4):

```text
PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m unit
  75 passed, 49 deselected
PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m integration
  17 passed, 107 deselected
PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m migration
  12 passed, 112 deselected
PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest -m security
  20 passed, 104 deselected
PYTHONPATH=src /tmp/jarvis-m000-venv/bin/pytest
  124 passed
/tmp/jarvis-m000-venv/bin/ruff check .
  All checks passed
/tmp/jarvis-m000-venv/bin/ruff format --check .
  36 files already formatted
/tmp/jarvis-m000-venv/bin/mypy src tests
  Success: no issues found in 36 source files
/tmp/jarvis-m000-venv/bin/python -m pip wheel --no-deps --no-build-isolation \
  --wheel-dir /tmp/jarvis-m000-wheel-final3 .
  Successfully built jarvis-cli; final wheel contract assertions passed
git diff --check
  passed with no output
```

Final CPython 3.12.13 verification used `/tmp/jarvis-m000-py312-venv` and the clean installed-wheel
environment `/tmp/jarvis-m000-py312-wheelverify.haP41M/install-venv`:

```text
/home/gabri/.local/bin/python3.12 --version
  Python 3.12.13
/home/gabri/.local/bin/python3.12 -m venv /tmp/jarvis-m000-py312-venv
/tmp/jarvis-m000-py312-venv/bin/python -m pip install \
  'hatchling>=1.31,<2' 'pytest>=9.1,<10' 'ruff>=0.15,<0.16' 'mypy>=2.3,<3'
  installed Hatchling 1.32.0, pytest 9.1.1, Ruff 0.15.22, and mypy 2.3.0
PYTHONPATH=src /tmp/jarvis-m000-py312-venv/bin/pytest -m unit
  75 passed, 49 deselected
PYTHONPATH=src /tmp/jarvis-m000-py312-venv/bin/pytest -m integration
  17 passed, 107 deselected
PYTHONPATH=src /tmp/jarvis-m000-py312-venv/bin/pytest -m migration
  12 passed, 112 deselected
PYTHONPATH=src /tmp/jarvis-m000-py312-venv/bin/pytest -m security
  20 passed, 104 deselected
PYTHONPATH=src /tmp/jarvis-m000-py312-venv/bin/pytest
  124 passed
PYTHONPATH=src /tmp/jarvis-m000-py312-venv/bin/python -c '<all package source imports>'
  source import smoke: passed
/tmp/jarvis-m000-py312-venv/bin/ruff check .
  All checks passed
/tmp/jarvis-m000-py312-venv/bin/ruff format --check .
  36 files already formatted
/tmp/jarvis-m000-py312-venv/bin/mypy src tests
  Success: no issues found in 36 source files
/tmp/jarvis-m000-py312-venv/bin/python -m pip wheel --no-deps --no-build-isolation \
  --wheel-dir /tmp/jarvis-m000-py312-wheelverify.haP41M/wheel .
  Successfully built jarvis-cli; 27-entry archive/resource/metadata assertions passed
/home/gabri/.local/bin/python3.12 -m venv \
  /tmp/jarvis-m000-py312-wheelverify.haP41M/install-venv
/tmp/jarvis-m000-py312-wheelverify.haP41M/install-venv/bin/python -m pip install \
  --no-deps /tmp/jarvis-m000-py312-wheelverify.haP41M/wheel/jarvis_cli-0.0.0-py3-none-any.whl
  Successfully installed jarvis-cli-0.0.0
/tmp/jarvis-m000-py312-wheelverify.haP41M/install-venv/bin/python -c \
  '<all installed imports; metadata runtime-dependency assertion>'
  installed-wheel imports: passed; runtime dependencies: none
/tmp/jarvis-m000-py312-wheelverify.haP41M/install-venv/bin/python -c \
  '<importlib.resources defaults TOML and migration SQL assertions>'
  installed package resources: passed
/tmp/jarvis-m000-py312-wheelverify.haP41M/install-venv/bin/python -m pip check
  No broken requirements found
env '<disposable HOME and all five XDG roots>' \
  /tmp/jarvis-m000-py312-wheelverify.haP41M/install-venv/bin/python \
  -m jarvis.foundation initialize --json
  passed twice; first applied migration 1 and second applied none
env '<same disposable HOME and XDG roots>' \
  /tmp/jarvis-m000-py312-wheelverify.haP41M/install-venv/bin/python \
  -m jarvis.foundation inspect --json
  schema/defaults version 1; safe directories; complete wheel installation identity
find /tmp/jarvis-m000-py312-wheelverify.haP41M/xdg -printf '%m %p\n' | sort
  application directories 0700; files 0600
rg -n '<synthetic secret corpus>' /tmp/jarvis-m000-py312-wheelverify.haP41M/xdg
  no matches
chmod 755 /tmp/jarvis-m000-py312-wheelverify.haP41M/xdg/runtime
env '<same disposable HOME and XDG roots>' \
  /tmp/jarvis-m000-py312-wheelverify.haP41M/install-venv/bin/python \
  -m jarvis.foundation initialize --json
  exit 1 with xdg.unsafe_runtime_directory and no traceback; runtime mode restored to 0700
git diff --check
  passed with no output
git status --short
  M ROADMAP.md
  M docs/plans/000-foundation.md
```

## Handoff summary

Milestone 000 is complete and ready for its final commit. Do not begin or plan Milestone 001 without
separate authorization.

Current failing tests: none. All 124 tests and each marker suite pass on CPython 3.12.13 and CPython
3.14.4. No Python 3.12 compatibility bug was found, so no implementation or regression-test change
was required.

Important local state:

- Milestone 000 and Steps 1–11 are **DONE**; every mandatory criterion is reconciled.
- `AGENTS.md`, `PLANS.md`, and `docs/architecture.md` remain unmodified. `ROADMAP.md` records
  Milestone 000 as **DONE**, and this ExecPlan contains the completion evidence.
- Python 3.12 verification tooling exists only in `/tmp/jarvis-m000-py312-venv`; the clean installed
  wheel and disposable XDG state are under `/tmp/jarvis-m000-py312-wheelverify.haP41M`. No system
  Python was modified, no sudo was used, and the package has no runtime dependencies.
- CPython 3.13 remains unavailable and was conditional, not blocking.

Final `git status --short`:

```text
 M ROADMAP.md
 M docs/plans/000-foundation.md
```

Hazards:

- Never use `/tmp` as a production runtime-directory fallback.
- Never assign concrete quotas to future writers in this milestone.
- Never expose test probes as permanent production commands without a production requirement.
- Never treat a canonical path string or prior protection decision as mutation authority.
- Never persist before centralized redaction and quota reservation.
- Never let tests resolve or initialize the user's real XDG state.

The plan is complete and self-contained. No unresolved product decision, implementation failure, or
verification blocker remains. Milestone 001 is **NOT STARTED**.
