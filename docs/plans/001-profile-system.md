# Milestone 001 — Profile Identity and Configuration Domain ExecPlan

Status: **DONE**
Last updated: 2026-08-13 America/Sao_Paulo

## Purpose and user outcome

Milestone 001 introduces the persistent profile identity and configuration domain required before
Core, IPC, models, clients, chat, permissions enforcement, or executable profile aliases exist.
When complete, service-level APIs expose a catalog that always contains the permanent Jarvis
profile and can inspect, create, rename, reset, and safely delete profiles while keeping ownership
bound to stable `profile_id` values.

Terms used by this plan:

- **Profile ID:** An opaque persisted UUID4 used for ownership and foreign keys. Rename and reset
  never change it.
- **Display name:** The validated, NFC-normalized user-facing name.
- **Command alias:** The deterministic lowercase ASCII/hyphen identifier derived from a display
  name. It is database data only in this milestone.
- **Configuration clone:** One transactionally consistent snapshot of the current Jarvis
  configuration owned by Milestone 001.
- **Product reset:** Restoration from centrally packaged defaults, never from mutable Jarvis data.
- **Destructive intent:** A short-lived single-use confirmation bound to the exact profile
  revisions, closed operation/scope type, and previewed database state.

## Scope

This plan implements only Milestone 001 in `ROADMAP.md` and the relevant `AGENTS.md` invariants,
especially sections 12–25, 29–31, 35, 48–51, 60, 71–83, 102–103, 125–129, 139, and 144–145.

Included:

- permanent Jarvis profile with display name `Jarvis` and canonical alias `jarvis`;
- typed stable `ProfileId`, display names, and separately stored command aliases;
- deterministic Unicode-to-ASCII alias normalization and reserved/collision checks;
- inspect, list, create, rename, configuration-update, reset, and non-Jarvis delete services;
- Jarvis deletion, kind, and canonical-alias protection at service and database layers;
- profile persona, context, appearance, waiting/goodbye messages, visible logging, startup desired
  state, and permission configuration;
- atomic creation-time cloning from current Jarvis configuration;
- field/section and whole-profile reset from centrally versioned defaults;
- exact destructive previews, expiring one-time confirmation intents, stale-preview rejection, and
  transactional execution;
- direct central coordination of the database-owned profile/configuration components that exist;
- typed alias-change results for later Milestone 003 filesystem reconciliation;
- migration from the completed Milestone 000 ledger-only database; and
- isolated unit, integration, migration, concurrency, and security tests.

The stable profile ID prepares the future `(profile_id, model_id)` ownership boundary, but no
`model_id`, model table, or profile/model record is introduced.

## Non-goals

Milestone 001 does not implement or create placeholders for:

- Core, IPC, Unix sockets, `jarvisd`, or client protocols;
- `jarvis-config`, public profile commands, help commands, or presentation;
- executable aliases, launchers, symlinks, registration status, or executable-path writes;
- model registry/selection/settings, profile/model associations, GGUF, or llama.cpp;
- chat, sessions, history, learning, memories, notes, or chat diagnostics;
- Policy Engine, Tool Broker, approvals, audit records, permission enforcement, or host tools;
- web, TUI, desktop, systemd, updater, installer, or installation-level configuration;
- limits for nonexistent future writers, fake history/model records, or placeholder cleanup stores;
- plugin discovery/registration or speculative filesystem/network/external-store coordination; or
- generic JSON settings blobs, pickle, or free-form runtime arguments.

Milestone 004 will extend creation to clone selected-model and applicable per-model settings for
profiles created after that feature exists. Existing profiles are not retroactively changed.

The two future decision gates remain deferred unchanged: Milestone 014 owns web-search provider,
credential, disclosure, and fallback choices; Milestone 019B owns signing technology and trusted
key/material lifecycle.

## Current progress

Milestone status: **DONE**

All nine implementation steps and completion criteria are done. M001 adds only the persistent
profile identity/configuration domain and preserves the completed foundation; M002 has not begun.

| Implementation item | Status |
|---|---|
| Defaults and typed configuration schemas | **DONE** |
| Identity, display-name validation, and alias normalization | **DONE** |
| Migration 0002 and database invariants | **DONE** |
| Repositories and Jarvis bootstrap | **DONE** |
| Inspect/create/rename/configuration services | **DONE** |
| Atomic clone behavior | **DONE** |
| Destructive previews and bounded intents | **DONE** |
| Section/profile reset and deletion | **DONE** |
| Automated and manual verification | **DONE** |

Progress log:

- 2026-08-11 America/Recife — Read `AGENTS.md`, `ROADMAP.md`, `PLANS.md`,
  `docs/architecture.md`, and `docs/plans/000-foundation.md` in full.
- 2026-08-11 America/Recife — Verified clean worktree at `cc81346`
  (`feat: complete milestone 000 foundation`), synchronized with `origin/new-jarvis`.
- 2026-08-11 America/Recife — Inspected the implemented defaults, errors, UTC clock, IDs, XDG
  paths, SQLite owner, migration runner, quotas, bootstrap, redaction, and test isolation.
- 2026-08-11 America/Recife — Re-ran the complete suite under CPython 3.14.4 with
  `PYTHONPATH=src`; all 124 tests passed. The committed M000 plan records the passing CPython
  3.12.13 matrix.
- 2026-08-11 America/Recife — Confirmed that no M001-or-later database/API surface exists and
  found no M000 bug or authoritative-document contradiction.
- 2026-08-11 America/Recife — Incorporated review corrections: defaults 2/2, strict display-name
  characters, closed destructive scopes, direct concrete coordination, and Recife plan timestamps.
- 2026-08-11 21:22:47 America/Recife — Implementation preflight re-read all required documents in
  full, confirmed HEAD `cc81346`, and found only this untracked M001 ExecPlan in the worktree.
  Verified every M001 item and completion criterion was `NOT STARTED`, M000 was `DONE`, migration
  0001 retained SHA-256 `9ae711fc0da6cb744516130e94ef545754decbd78628d5f2a78ffcd495722a7e`,
  and no profile or M002+ code/schema existed. Inspected the actual defaults, SQLite, migration,
  bootstrap, clock, identifier, error, and isolated-test APIs. The complete committed M000 suite
  passed on CPython 3.14.4: 124 tests. Step 1 marked `IN PROGRESS` before implementation.
- 2026-08-11 America/Recife — Step 1 initial focused run collected 60 tests: 57 passed and 3
  failed. One real boundary issue was found: an invalid packaged profile color escaped as
  `profile.configuration_invalid` instead of the defaults registry's established
  `defaults.invalid` error. Two failures were incorrect new-test assumptions: a 128-code-point CJK
  display name is within both documented display bounds (alias derivation, not display validation,
  rejects it), and a different valid lowercase hex appearance is permitted. The defaults boundary
  is being fixed and only those invalid assertions are being corrected.
- 2026-08-11 21:27:44 America/Recife — Step 1 `DONE`. Added packaged defaults schema/product 2/2,
  exact profile defaults, immutable configuration values, domain-owned UUID profile IDs, closed
  configuration/permission/logging enums, the single display-name/alias implementation, commands,
  results, and typed safe errors. Corrected the defaults validation boundary found by the first
  run. Focused unit tests passed 58; Ruff passed; strict mypy passed 11 selected source/test files.
  Migration 0001 still hashes to the recorded M000 checksum. Step 2 marked `IN PROGRESS` before
  adding migration 0002.
- 2026-08-11 America/Recife — Step 2 first migration load failed before SQL execution because the
  M000 transaction-control regex treats the `BEGIN` required by every SQLite trigger body as a
  migration-owned transaction. This is a genuine M000 migration-validator defect blocking the
  narrow Jarvis defense-in-depth triggers required by M001. The validator will be corrected to
  reject transaction-control only at the start of complete SQL statements; a regression will prove
  real `BEGIN`/`COMMIT` remains forbidden while `CREATE TRIGGER ... BEGIN ... END` is accepted.
- 2026-08-11 21:31:19 America/Recife — Step 2 `DONE`. Added migration 0002 with exactly the seven
  M001 tables, closed constraints, indexes, cascades, and narrow permanent-Jarvis triggers. The
  schema-1 upgrade/apply-once, invalid SQL scope/alias defense, cascade, future-table absence, and
  M000 trigger-parser regression tests pass: 27 migration tests total. Ruff and strict mypy pass;
  migration 0001 remains byte-identical at the recorded checksum. Step 3 marked `IN PROGRESS`.
- 2026-08-11 21:35:19 America/Recife — Step 3 `DONE`. Added caller-transaction identity/config SQL
  repositories and integrated profile bootstrap after migrations but before the unchanged-shape
  foundation marker. Jarvis creation is atomic and complete; existing state is validated rather
  than repaired/replaced. Stable restart identity, concurrent two-process bootstrap, corrupted
  state fail-closed behavior, no-marker-on-failure, private permissions/origins, and injected
  rollback pass in 13 focused integration tests. Ruff and strict mypy pass. Step 4 marked
  `IN PROGRESS`.
- 2026-08-11 America/Recife — Step 4 first focused run failed 13/15 tests because a mechanical
  cleanup removed the local packaged-default snapshot from `ensure_jarvis`; all failures share the
  resulting `NameError` before configuration insertion. This is an implementation regression, not
  a contract deviation. Restoring the snapshot lookup preserves the already-passing bootstrap
  design and the run will be repeated before further work.
- 2026-08-11 21:37:48 America/Recife — Step 4 `DONE`. Implemented consistent catalog/get reads,
  validated atomic create, expected-revision rename, stable identity/config preservation, reserved
  and normalized collision handling, protected Jarvis rename, deterministic exact rename no-op,
  and data-only alias changes. After restoring the missing bootstrap defaults lookup, all 15
  focused service/bootstrap tests passed; Ruff and strict mypy passed. Step 5 marked `IN PROGRESS`.
- 2026-08-11 21:40:05 America/Recife — Step 5 `DONE`. Added ProfileId-scoped complete/section
  configuration reads and writes requiring expected identity/config revisions. Exact no-ops retain
  all revisions; changes increment the aggregate once and only changed sections once. Tests prove
  all current M001 fields/origins clone from one Jarvis snapshot, clone revisions start at one,
  later Jarvis changes are not retroactive, hostile SQL text remains data, and profiles remain
  isolated. Fifteen focused tests, Ruff, and strict mypy pass. Step 6 marked `IN PROGRESS`.
- 2026-08-11 21:45:13 America/Recife — Step 6 `DONE`. Added closed typed destructive targets,
  exact reset/delete preview items, five-minute one-time raw tokens excluded from representations,
  SHA-256-only token/state persistence, same-tuple replacement, and deterministic expiry pruning
  capped at 100. Tests cover invalid/unknown combinations, raw-token absence, whole/section reset
  truthfulness, exact delete counts, Jarvis protection, replacement, and bounded ordered pruning:
  10 focused tests pass; Ruff and strict mypy pass. Step 7 marked `IN PROGRESS`.
- 2026-08-11 America/Recife — The first Step 7 regression run passed all five unit tests but failed
  three of five preview integrations because the new intent lookup was inserted between
  `replace()`'s delete and insert, leaving the insert unreachable after `consume()` returned. No
  persisted intent survived a preview. This is a local implementation-order bug, not a design
  deviation; the insert is restored inside `replace()` and preview tests will pass again before
  confirmation tests proceed.
- 2026-08-11 America/Recife — The first eight-test confirmation run passed seven and exposed one
  incorrect assertion: a persona section changed once by customization and once by reset correctly
  reaches revision 3, not 2. Aggregate and unaffected-section behavior were correct. The assertion
  is corrected to the ExecPlan's exactly-once-per-committed-change semantics.
- 2026-08-11 21:49:38 America/Recife — Step 7 `DONE`. Implemented direct current-store destructive
  coordination with constant-time token comparison, expiry, exact target/profile/revision/state
  validation, packaged-v2 section/whole reset, non-Jarvis cascade deletion, same-transaction
  consumption, and typed alias reconciliation. Tests prove no-op semantics, identity preservation,
  reset independence from mutable Jarvis, replay/forgery/expiry/replacement/staleness failure,
  direct-SQL digest detection, and rollback preserving valid intents. Thirteen focused destructive
  integration tests, Ruff, and strict mypy pass. Step 8 marked `IN PROGRESS`.
- 2026-08-11 America/Recife — The first eight-case cross-process suite passed six races. Both
  confirmation races reported `profile.confirmation_expired` from every child because previews
  used the injected 12:00 UTC fake clock while child services defaulted to the later system clock.
  The product expiry behavior was correct; the race fixture mixed clock domains. Child confirmers
  will use the same injected UTC instant and the matrix will be repeated.
- 2026-08-11 America/Recife — The first complete-suite collection found 247 tests but stopped
  before execution because unit and integration preview test modules shared the basename
  `test_destructive_previews.py` in non-package directories. Python imported the integration module
  for the unit path. The integration file is renamed uniquely; no test or product behavior changes.
- 2026-08-11 21:55:47 America/Recife — Step 8 `DONE`. All eight required cross-process race cases
  pass and the complete race module passed 10 consecutive runs (80 cases). Security tests cover
  injection/Unicode/identity confusion/isolation/private-data/token/direct-SQL/schema boundaries.
  After the unique test-module rename, the formatted repository passes the complete CPython 3.14
  suite (252 tests), Ruff lint/format, and strict mypy over 56 files. Step 9 marked `IN PROGRESS`.
- 2026-08-11 America/Recife — The disposable temporary-XDG walkthrough passed end to end: schema
  1 upgraded to 2, Jarvis remained stable, current-Jarvis cloning was exact, rename retained ID,
  packaged-v2 reset diverged from customized Jarvis, protected deletion and secondary cascade
  behaved correctly, the exact schema/FK/file modes were clean, and the temporary root was removed.
- 2026-08-11 America/Recife — Final service-boundary review found destructive preview/confirmation
  delegates could expose a raw SQLite busy exception although CRUD/configuration calls translated
  it. Added the same typed `database.busy` translation and extended the busy-timeout regression;
  all eight concurrency tests pass. This is a consistency/security fix within the planned API.
- 2026-08-11 22:04:16 America/Recife — Step 9 and M001 `DONE`. Final CPython 3.14.4 and 3.12.13
  matrices each pass: unit 129, integration 58, migration 27, security 38, full 252. The original
  M000 test-file set passes 130 tests under each interpreter, including six updated schema/default
  expectations. The eight-race module previously passed 10 consecutive runs (80 cases). Ruff and
  formatting pass 56 files; strict mypy passes 56 files. The offline wheel builds, installs under
  CPython 3.12 with no broken requirements, imports profile code/resources, retains zero runtime
  dependencies, and includes both migrations/defaults. Exact schema audit found only the migration
  ledger plus seven M001 tables, migrations 1/2, one Jarvis row, and clean foreign keys. CPython
  3.13 is unavailable and remains conditional. Migration 0001 retains its recorded checksum;
  final scope, authoritative-document, whitespace, diff, and worktree-status reviews pass.
- 2026-08-13 America/Sao_Paulo — An independent post-completion implementation review reproduced
  two boundary violations before changing code. SQLite `INSERT OR REPLACE` could replace the
  permanent Jarvis profile because REPLACE conflict deletion does not run delete triggers when
  recursive triggers are disabled. The M000 migration parser also missed transaction-control
  statements preceded by comments/BOMs or placed after another statement on the same line. Narrow
  trigger and complete-SQL-statement parser fixes now close both paths, with adversarial direct-SQL
  and parser regressions.
- 2026-08-13 America/Sao_Paulo — The same review found and corrected typed-boundary and fail-closed
  defects: malformed Unicode confirmation tokens and exhausted busy timeouts in direct destructive
  services could leak raw exceptions; corrupt SQLite scalar/display-alias/default-origin state
  could be coerced or hidden; generated profile-ID collision reporting was misleading; and several
  hostile iterables or oversized Unicode values were materialized before their bounds were
  enforced. Reset preview comparison now also includes defaults-origin metadata.
- 2026-08-13 America/Sao_Paulo — Post-review verification passes on CPython 3.14.4 and 3.12.13:
  unit 139, integration 60, migration 36, security 40, full 275. The original M000 test-file set
  passes 138 tests on each interpreter. The eight-race profile module passed 20 consecutive runs
  (160 cases), and concurrent migration/bootstrap tests passed 20 consecutive combined runs (40
  cases). Ruff lint/format and strict mypy pass 56 files. A fresh installed wheel contains both
  migrations, defaults v2, and all profile modules, has no runtime dependency, and initializes
  outside the checkout. The temporary-XDG walkthrough and exact schema/foreign-key audit pass.

## Repository state and prerequisites

Verified baseline:

- branch `new-jarvis`, HEAD `cc8134668ecff5fb49d741e9185d3248e5edc2ca`;
- upstream divergence `+0/-0` and clean worktree before this plan was added;
- schema version 1 with only `schema_migrations`;
- defaults schema/product versions 1/1;
- no runtime dependencies; and
- 124 passing tests on local CPython 3.14.4.

CPython 3.12.13 is present, but its previous disposable test environment no longer exists. Its
successful M000 completion matrix is recorded in the committed M000 ExecPlan.

Reuse these M000 contracts without weakening them:

- `XdgPaths` and `$XDG_DATA_HOME/jarvis-cli/jarvis.sqlite3`;
- descriptor-bound private SQLite open, WAL, foreign keys, `synchronous=FULL`, bounded
  `busy_timeout`, explicit ownership, and `BEGIN IMMEDIATE` transactions;
- immutable consecutive checksummed migrations;
- `JarvisError` safe envelopes and localization-ready keys;
- injected aware UTC clocks and fixed RFC 3339 UTC persistence;
- UUID4/deterministic-ID conventions;
- the packaged exact-key defaults registry;
- centralized redaction before diagnostics;
- disposable HOME/all-five-XDG test fixtures and no-network guard; and
- no telemetry, cloud dependency, sudo, or active-installation mutation.

No new dependency is required.

## Implementation sequence

### 1. **DONE — Extend defaults and define domain values**

- Extend `src/jarvis/config/defaults.py` and `defaults.toml` with typed profile defaults.
- Set `defaults_schema_version = 2` because the resource structure changes.
- Set `product_defaults_version = 2` because resettable profile product defaults are added.
- Do not fabricate a version-1 profile snapshot or 1-to-2 profile-value transition; no profile
  configuration existed under product-default version 1.
- Define profile IDs, names, aliases, sections, configuration snapshots, revisions, commands,
  results, and typed errors with focused unit tests.
- Prerequisite: M000.
- Validate with the defaults/profile-name/profile-config/profile-error unit tests and strict mypy.
- Recovery: no user state is involved.

### 2. **DONE — Add migration 0002**

- Add `src/jarvis/storage/migration_files/0002_profile_system.sql` with the exact schema below.
- Preserve migration 0001 byte-for-byte.
- Test schema-1 upgrade, complete rollback, checksums, second-run no-op, constraints, and indexes.
- Prerequisite: step 1.
- Recovery: the migration runner rolls back the complete pending set. Never edit an applied
  migration or automatically downgrade/restore. No backup is needed for a ledger-only M000 DB.

### 3. **DONE — Implement repositories and Jarvis bootstrap**

- Add parameterized-SQL repositories whose methods use the coordinator/service-owned connection.
- In one immediate transaction, create Jarvis, alias, configuration, section metadata,
  permissions, and messages when absent.
- When Jarvis exists, verify its complete invariant set and fail closed on corruption instead of
  replacing identity or configuration.
- Invoke profile bootstrap from `initialize_foundation()` after migrations and before the final
  marker. Keep `FOUNDATION_STATE_VERSION` unchanged because marker shape is unchanged.
- Prerequisite: steps 1–2.
- Recovery: bootstrap is all-or-nothing. If it fails after schema migration, no completion marker
  is published and the next initialization retries safely.

### 4. **DONE — Implement inspect, create, and rename**

- Address profiles by `ProfileId`, never alias strings.
- Creation validates/NFC-normalizes the display name, derives the alias, checks reservations and
  collisions, then reads Jarvis and inserts the clone in one `BEGIN IMMEDIATE` transaction.
- Rename requires `profile_id` and `expected_identity_revision`, atomically replaces display/alias,
  and preserves identity/data.
- Reject every Jarvis rename. Return typed alias-change data but perform no filesystem action.
- Prerequisite: step 3.
- Recovery: rollback leaves no partial alias/profile/configuration rows.

### 5. **DONE — Implement configuration and cloning**

- Return complete and section-scoped typed snapshots.
- Validate before starting a write, then recheck expected identity/configuration revisions inside
  the transaction.
- Increment the configuration revision and affected section revisions once per committed change.
- Prove the clone allowlist copies all and only current M001 configuration.
- Prerequisite: steps 3–4.
- Recovery: a failed write restores the complete prior snapshot through SQLite rollback.

### 6. **DONE — Implement previews and bounded confirmation intents**

- Preview section reset, whole-profile reset, and deletion exactly.
- Persist only hashes of the raw token and state, never token/configuration values.
- Bind each intent to typed operation/scope, profile ID, revisions, state digest, and expiry.
- Enforce one pending row per `(profile_id, operation_kind, scope)`.
- Reject unknown/mismatched operation scopes before SQL and through DB checks.
- Prune expired rows in deterministic `(expires_at_utc, operation_id)` order in bounded batches.
- Prerequisite: steps 3–5.
- Recovery: replacement previews affect only pending intent metadata; failed execution rolls back
  token consumption and domain work together.

### 7. **DONE — Implement central reset/delete coordination**

- `ProfileDestructiveCoordinator` directly coordinates the real database repositories.
- Verify token in constant time, expiry, revisions, operation/scope, and recomputed state digest
  inside one immediate transaction.
- Reset from packaged defaults version 2, never mutable Jarvis configuration.
- Preserve profile ID/display/alias during reset; delete only non-Jarvis profiles.
- Return alias reconciliation information without touching executable paths.
- Prerequisite: step 6.
- Recovery: all current state shares one SQLite transaction, so partial success cannot commit.

### 8. **DONE — Prove concurrency and security**

- Use separate connections/processes for create collisions, rename races, rename/delete,
  reset/delete, replay, and Jarvis-update-versus-clone snapshot consistency.
- Retain the M000 five-second busy timeout. Do not add broad retry or rely on process locks.
- Assert forbidden M002+ tables, APIs, files, and imports remain absent.
- Prerequisite: steps 4–7.
- Recovery: all stress work uses disposable databases.

### 9. **DONE — Complete verification and handoff**

- Run marker suites, full regression, Ruff, format, strict mypy, offline wheel/resource checks,
  manual temporary-XDG verification, `git diff --check`, and status reconciliation.
- Update this plan continuously with evidence, discoveries, decisions, deviations, and handoff.
- Prerequisite: all preceding steps.

Validation commands for completion:

```bash
PYTHONPATH=src python -m pytest -m unit
PYTHONPATH=src python -m pytest -m integration
PYTHONPATH=src python -m pytest -m migration
PYTHONPATH=src python -m pytest -m security
PYTHONPATH=src python -m pytest
ruff check .
ruff format --check .
mypy src tests
python -m pip wheel --no-deps --no-build-isolation \
  --wheel-dir /tmp/jarvis-m001-wheel .
git diff --check
git status --short
```

## Exact files and components affected

Expected new files:

```text
docs/plans/001-profile-system.md
src/jarvis/profiles/__init__.py
src/jarvis/profiles/errors.py
src/jarvis/profiles/models.py
src/jarvis/profiles/names.py
src/jarvis/profiles/repository.py
src/jarvis/profiles/configuration.py
src/jarvis/profiles/destructive.py
src/jarvis/profiles/service.py
src/jarvis/storage/migration_files/0002_profile_system.sql
tests/unit/test_profile_errors.py
tests/unit/test_profile_names.py
tests/unit/test_profile_config.py
tests/unit/test_destructive_previews.py
tests/integration/test_profile_bootstrap.py
tests/integration/test_profile_service.py
tests/integration/test_profile_configuration.py
tests/integration/test_profile_destructive_previews.py
tests/integration/test_destructive_operations.py
tests/integration/test_profile_concurrency.py
tests/migration/test_profile_migration.py
tests/security/test_profile_security.py
```

Expected modifications:

```text
README.md
ROADMAP.md
docs/development.md
src/jarvis/config/__init__.py
src/jarvis/config/defaults.py
src/jarvis/config/defaults.toml
src/jarvis/foundation/bootstrap.py
src/jarvis/storage/migrations.py
tests/unit/test_defaults.py
tests/integration/test_initialization.py
tests/integration/test_foundation_cli.py
tests/migration/test_migrations.py
```

Deliberately untouched unless an implementation discovery proves an authoritative contradiction:

```text
AGENTS.md
PLANS.md
docs/architecture.md
src/jarvis/diagnostics/
src/jarvis/security/
src/jarvis/storage/migration_files/0001_migration_ledger.sql
```

No empty CLI, Core, IPC, model, runtime, policy, tool, memory, client, installer, updater, desktop,
or systemd package is created.

## Contracts and interfaces

### Identity and display names

`ProfileId` is a frozen typed UUID wrapper. Injected UUID4 generation creates new IDs. Jarvis gets
one ID at first profile bootstrap and retains it across restart, reset, and rejected rename/delete
attempts. Purging the entire database starts a new installation state and may generate a new ID.

Display-name policy:

- accept only Unicode letters, valid combining marks associated with a preceding letter, Unicode
  decimal digits, and ASCII space (`U+0020`);
- require at least one Unicode letter or decimal digit;
- normalize to NFC and trim leading/trailing ASCII spaces;
- preserve internal capitalization and ASCII-space multiplicity;
- limit to 128 code points and 512 UTF-8 bytes;
- reject a combining mark at the start or after a space/digit;
- reject ASCII hyphens, all other punctuation, path separators, shell metacharacters, tabs,
  newlines, non-ASCII whitespace, control/format characters, and bidi controls.

Alias normalization remains:

1. casefold;
2. NFKD normalization;
3. discard combining marks;
4. turn ASCII-space runs into `-`;
5. discard unsupported/non-ASCII characters;
6. retain `a-z`, `0-9`, and `-` only;
7. collapse hyphens and strip leading/trailing hyphens;
8. require 1–63 characters matching `[a-z0-9]+(?:-[a-z0-9]+)*`.

Required examples:

```text
João Trabalho -> joao-trabalho
MY AI 2       -> my-ai-2
```

No general transliteration dependency is added. A name whose alias becomes empty is invalid.
Uniqueness applies to canonical ASCII aliases, so case/accent/space variants collide.

Reserved aliases are exactly the current protected set:

```text
jarvis
jarvis-config
jarvis-update
jarvis-clear
jarvis-manage
jarvis-help
jarvisd
```

M003 may add actual executable-registration collisions without changing this normalization.

### Configuration fields

All fields are profile-owned, cloned from current Jarvis on creation, and reset from packaged
product defaults version 2:

| Field | Type/validation | Default | Persistence |
|---|---|---|---|
| `persona.text` | UTF-8, no NUL, max 32 KiB | Default persona below | `TEXT` |
| `profile_context.text` | UTF-8, no NUL, max 64 KiB | empty | `TEXT` |
| `appearance.accent_color` | lowercase `#rrggbb` | `#4fc3f7` | `TEXT` |
| `appearance.foreground_color` | lowercase `#rrggbb` | `#e6edf3` | `TEXT` |
| `appearance.background_color` | lowercase `#rrggbb` | `#0d1117` | `TEXT` |
| `waiting_messages` | ordered 0–16 single-line NFC strings; each 1–256 code points and max 1 KiB | empty override | rows |
| `goodbye_messages` | same | empty override | rows |
| `visible_logging_mode` | `full`, `server-essential`, `essential`, `essential-minimum`, `none` | `essential-minimum` | constrained text |
| `start_with_computer` | exact boolean | `false` | constrained integer |
| permissions `create/copy/read/screen/internet/execute` | `allow/ask/deny` | `allow` | constrained rows |
| permissions `delete/modify/move` | `allow/ask/deny` | `ask` | constrained rows |

Default persona:

```text
You are Jarvis, a polite, composed, professional, competent, and respectful local assistant. Be concise when appropriate, subtly sophisticated, and proactive without being intrusive. Match the language currently used by the user unless the profile context explicitly directs otherwise. Do not imitate or quote copyrighted fictional dialogue.
```

Empty message lists mean no profile override; future localized clients may supply catalog defaults.
No sudo setting is persisted: sudo remains absolutely denied until a separately authorized design.
No model, reasoning, context-window, sampling, timeout, runtime, or per-model field exists.

### Service and repository boundaries

Internal, future-Core-consumable operations:

```python
ProfileService.ensure_jarvis() -> Profile
ProfileService.list_profiles() -> tuple[Profile, ...]
ProfileService.get_profile(profile_id: ProfileId) -> ProfileAggregate
ProfileService.create_profile(command: CreateProfile) -> ProfileAggregate
ProfileService.rename_profile(command: RenameProfile) -> RenameResult
ProfileService.preview_delete(profile_id: ProfileId) -> DestructivePreview
ProfileService.confirm_delete(command: ConfirmDestructiveOperation) -> DeleteProfileResult

ProfileConfigService.get_configuration(profile_id: ProfileId) -> ProfileConfiguration
ProfileConfigService.update_configuration(command: UpdateProfileConfiguration) -> ProfileConfiguration
ProfileConfigService.preview_reset(profile_id: ProfileId, scope: ResetScope) -> DestructivePreview
ProfileConfigService.confirm_reset(command: ConfirmDestructiveOperation) -> ResetProfileResult
```

Repositories own SQL only, accept typed IDs, and participate in a caller-owned transaction. They
do not emit client prose. Rename/config update require expected revisions.

Rename/delete results include `profile_id`, old alias, optional new alias, and typed
`renamed|removed` change. This is reconciliation data, not a claim of filesystem success.

### Clone allowlist and versions

One creation transaction copies persona, context, appearance, message overrides, visible logging,
startup desired state, nine permission decisions, config schema version, and each section's
defaults-origin metadata. It never copies or creates models, sessions, history, learning, notes,
memories, chat diagnostics, runtimes, tools, approvals, or audit data.

Jarvis bootstrap and resets record product defaults version 2 for affected sections. Creation
copies each source section's origin version so it faithfully clones current Jarvis configuration.
No profile configuration ever existed at product defaults version 1.

### Destructive operations

Preview contains operation ID/kind, profile ID, typed scope, identity/config revisions, created and
expiry UTC times, exact ordered items/counts, `has_changes`, and a one-time token.

Closed operation/scope matrix:

```text
delete-profile -> whole-profile

reset-configuration -> persona
reset-configuration -> profile-context
reset-configuration -> appearance
reset-configuration -> waiting-messages
reset-configuration -> goodbye-messages
reset-configuration -> visible-logging
reset-configuration -> startup
reset-configuration -> permissions
reset-configuration -> whole-profile
```

Unknown scopes and invalid combinations are rejected by typed constructors/repository validation
before persistence and by narrow SQL checks.

Delete previews report exact counts for identity, alias, configuration, permission, waiting, and
goodbye data, including zero counts. Reset previews list every in-scope field, whether it changes,
message removals/replacements, permission changes, and target defaults version 2. They do not
pretend model/history data exists. Reset preserves profile ID, display name, and alias.

Confirmation tokens use `secrets.token_urlsafe(32)`, persist only SHA-256, compare with
`hmac.compare_digest`, expire after five minutes, and are single-use. They bind operation, scope,
profile, revisions, and a recomputed database state digest. A replacement preview invalidates the
older same-tuple intent. At most one intent exists per `(profile_id, operation_kind, scope)`.
Expired rows prune deterministically by `(expires_at_utc, operation_id)` in bounded batches;
unexpired rows are not pruned for convenience. A rolled-back execution leaves an otherwise valid
intent retryable.

`ProfileDestructiveCoordinator` directly coordinates the current identity, alias, configuration,
section, message, permission, and intent repositories in one SQLite transaction. There is no
generic plugin discovery/registration. A narrow module-private protocol is permitted only if two
or more real M001 components require the same preview/apply shape; it may not expose filesystem,
network, external-store, or hypothetical participant semantics. The first milestone adding an
independent/external profile store may refine the contract with prepare/reconcile behavior based
on that store's real failure model.

### Typed errors

Profile errors extend `JarvisError` with safe codes:

```text
profile.not_found
profile.invalid_name
profile.name_conflict
profile.protected
profile.invariant_violation
profile.concurrent_modification
profile.configuration_invalid
profile.confirmation_required
profile.confirmation_invalid
profile.confirmation_expired
profile.confirmation_stale
profile.operation_failed
database.busy
```

Safe details exclude SQLite internals, tracebacks, tokens, raw display names, persona, and context.

### Concurrency

- Every write uses a separately owned connection and `BEGIN IMMEDIATE`; no process-local lock is
  correctness authority.
- Existing five-second busy timeout remains. Exhaustion becomes typed `database.busy`; no broad
  retry hides storage faults.
- Unique alias constraints select one winner for colliding creates/renames.
- Expected revisions make concurrent rename/update losers deterministic.
- Rename/delete, reset/delete, and replay races revalidate intent/revisions after acquiring the
  write transaction.
- Creation reads all Jarvis config tables and inserts the clone in the same write transaction, so a
  concurrent Jarvis change is wholly before or after the snapshot.
- Partial repository/coordinator failure rolls back every current-domain change.
- Multi-table reads use one consistent DB snapshot.

## Database, migrations, and storage

Database remains `$XDG_DATA_HOME/jarvis-cli/jarvis.sqlite3`. Migration 0002 adds:

### `profiles`

```text
profile_id TEXT PRIMARY KEY
profile_kind TEXT NOT NULL CHECK IN ('jarvis', 'standard')
display_name TEXT NOT NULL
identity_revision INTEGER NOT NULL CHECK > 0
created_at_utc TEXT NOT NULL
updated_at_utc TEXT NOT NULL
```

A partial unique index permits at most one Jarvis kind. Narrow triggers prevent deleting Jarvis or
changing any row into/out of Jarvis kind. Service validation owns full UUID/Unicode checks; SQL
adds practical length/shape defense.

### `profile_aliases`

```text
profile_id TEXT PRIMARY KEY REFERENCES profiles(profile_id) ON DELETE CASCADE
command_alias TEXT NOT NULL UNIQUE
created_at_utc TEXT NOT NULL
updated_at_utc TEXT NOT NULL
```

SQL checks enforce 1–63 lowercase ASCII/digit/hyphen shape without edge/consecutive hyphens.
Triggers require Jarvis alias `jarvis`, protect it from update/delete, and prevent non-Jarvis use.

### `profile_configurations`

```text
profile_id TEXT PRIMARY KEY REFERENCES profiles(profile_id) ON DELETE CASCADE
config_schema_version INTEGER NOT NULL CHECK > 0
configuration_revision INTEGER NOT NULL CHECK > 0
persona_text TEXT NOT NULL
profile_context_text TEXT NOT NULL
accent_color TEXT NOT NULL
foreground_color TEXT NOT NULL
background_color TEXT NOT NULL
visible_logging_mode TEXT NOT NULL
start_with_computer INTEGER NOT NULL CHECK IN (0, 1)
created_at_utc TEXT NOT NULL
updated_at_utc TEXT NOT NULL
```

Profile config schema starts at 1. SQL duplicates practical enum/color/length constraints; typed
service validation remains authoritative.

### `profile_configuration_sections`

```text
profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE
section_name TEXT NOT NULL
defaults_version INTEGER NOT NULL CHECK >= 2
section_revision INTEGER NOT NULL CHECK > 0
PRIMARY KEY(profile_id, section_name)
```

Closed sections are `persona`, `profile-context`, `appearance`, `waiting-messages`,
`goodbye-messages`, `visible-logging`, `startup`, and `permissions`. All eight rows are required.
Profile defaults begin at product version 2, so SQL rejects invented version-1 origins. The
application accepts exactly its current packaged defaults version and fails closed on future
origins it cannot interpret. Bootstrap/reset write defaults version 2; cloning copies source
origins.

### `profile_messages`

```text
profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE
message_kind TEXT NOT NULL CHECK IN ('waiting', 'goodbye')
ordinal INTEGER NOT NULL CHECK >= 0 AND < 16
message_text TEXT NOT NULL
PRIMARY KEY(profile_id, message_kind, ordinal)
```

Ordinals must be contiguous, enforced by repository invariant validation.

### `profile_permissions`

```text
profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE
capability TEXT NOT NULL
decision TEXT NOT NULL CHECK IN ('allow', 'ask', 'deny')
PRIMARY KEY(profile_id, capability)
```

SQL permits exactly the nine M001 capability names; every profile must have one of each.

### `profile_operation_intents`

```text
operation_id TEXT PRIMARY KEY
profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE
operation_kind TEXT NOT NULL CHECK IN ('delete-profile', 'reset-configuration')
scope TEXT NOT NULL
expected_identity_revision INTEGER NOT NULL
expected_configuration_revision INTEGER NOT NULL
state_digest_sha256 TEXT NOT NULL
token_digest_sha256 TEXT NOT NULL
created_at_utc TEXT NOT NULL
expires_at_utc TEXT NOT NULL
UNIQUE(profile_id, operation_kind, scope)
```

An index on `(expires_at_utc, operation_id)` supports deterministic pruning. Checks restrict scope
to the nine reset scopes/whole-profile union and enforce the exact valid kind/scope combinations.
Digests are lowercase SHA-256 hex. No raw token or serialized preview/configuration is stored.

Non-Jarvis deletion cascades all current owned rows. Jarvis is protected by service plus triggers.
No executable alias, audit/history tombstone, or external cleanup is assumed.

Migration/default behavior:

- migration 0001 stays immutable;
- 0002 upgrades the ledger-only schema in the existing migration transaction;
- no application data is backfilled and no pre-change application backup is required;
- defaults advance directly from 1/1 to schema/product 2/2;
- no profile-value 1-to-2 migration exists because no version-1 profile config existed;
- Jarvis bootstrap then writes version-2 defaults in its own immediate transaction;
- repeated bootstrap retains Jarvis ID and validates completeness; and
- forward-only/no-automatic-downgrade recovery remains unchanged.

All persistence remains in the existing mode-0600 XDG-data SQLite file. Nothing writes XDG config,
state, cache, runtime, executable paths, or installation files. Structural field/count bounds limit
each profile; no quota category is added because no independent blob/file/retention writer exists.
SQLite failures including ENOSPC must roll back without partial profile state.

## Security and privacy considerations

| Threat | Required control |
|---|---|
| Alias/path/command injection | Alias is strict data only; no path/argv/shell use |
| Display-name injection | Closed Unicode character policy and parameterized SQL |
| Unicode/case/accent confusion | NFC storage, one casefold+NFKD alias algorithm, ASCII uniqueness |
| Reserved-name spoofing | Canonical reserved set plus DB Jarvis guards |
| Alias used as ownership | Typed `ProfileId` required for all owned access |
| Cross-profile access | Mandatory profile predicates and isolation tests |
| Clone leakage | Explicit allowlist; forbidden stores/tables/APIs absent |
| Torn clone | Jarvis read and clone insertion share one immediate transaction |
| Reset copies Jarvis | Reset reads packaged defaults version 2 only |
| Jarvis deletion/rename | Service denial plus narrow database triggers |
| Token replay/staleness | Hash, constant-time compare, expiry, revisions, state digest, one-use |
| Arbitrary persistent scopes | Closed typed/SQL matrix and one bounded row per tuple |
| Concurrent races | SQLite serialization and optimistic revisions, not Python locks |
| SQL injection | Parameters and allowlisted query structure only |
| Unsafe serialization | No pickle/generic settings JSON; typed values and digests |
| Secret leakage | No credential field; persona/context/token excluded from logs/safe errors |
| Writes outside XDG ownership | Existing database owner is the only persistence path |
| Installation mutation | No host tool or mutation path exists |
| Network/telemetry | No dependency/network behavior; retain guards/static tests |
| Model authority | No model, Agent Engine, IPC, or client mutation entry exists |

Permissions are stored preferences only; they authorize nothing until the Policy Engine exists.
Persisted application timestamps remain UTC using the M000 fixed RFC 3339 format. Regional time
zones are used only for plan/progress timestamps.

## Tests

Unit tests cover:

- typed profile IDs and invalid UUIDs;
- valid letters/associated combining marks/decimal digits/ASCII spaces;
- rejection of hyphens, invalid marks, empty/oversized names, path/shell punctuation,
  control/format/bidi characters, and non-ASCII whitespace;
- `João Trabalho -> joao-trabalho` and `MY AI 2 -> my-ai-2`;
- case/accent/repeated-space behavior, empty normalization, reserved names, and collisions;
- every configuration type, validation, bound, default, clone, and reset rule;
- defaults schema/product 2/2 and section-origin 2;
- no fabricated version-1 profile transition;
- typed safe errors and deterministic preview/state digests; and
- rejection of unknown/mismatched destructive kinds/scopes before persistence.

Integration tests cover:

- idempotent Jarvis bootstrap and stable ID across restart;
- corruption/incomplete-Jarvis fail-closed behavior;
- create/list/get/rename/restart and duplicate/reserved collisions;
- Jarvis rename/delete/alias protection;
- exact current-Jarvis clone and no retroactive changes;
- reset to v2 product defaults instead of mutable Jarvis;
- each section reset, origin version, and identity preservation;
- exact previews and one intent per profile/kind/scope;
- deterministic bounded expiry pruning preserving unexpired intents;
- delete cascades and injected reset/delete rollback;
- profile isolation and persistence; and
- proof no executable alias path is touched.

Migration tests cover schema-1-to-2 upgrade, apply-once, rollback, checksums/gaps/newer-schema,
keys/FKs/indexes/checks/cascades/triggers, direct invalid-scope SQL, and absence of model/session/
history/memory/note/tool/approval/runtime/IPC tables.

Concurrency tests use distinct connections and subprocesses for colliding creates, rename/rename,
rename/create collision, rename/delete, reset/delete, token replay, stale previews, Jarvis config
change versus creation, busy timeout, and partial failure. A clone must equal either the complete
pre-update or post-update Jarvis snapshot, never a mixture.

Security tests cover injection, Unicode spoofing, hyphen rejection, ID/alias confusion,
cross-profile access, direct Jarvis invariant attacks, forged/expired/replaced/replayed tokens,
arbitrary scopes, hostile private text through parameterized SQL, no private/token diagnostics,
temporary-XDG-only writes, and no network/telemetry/dependency/client/model/tool expansion.

All tests inherit isolated HOME and all five XDG roots plus network denial. Run the full matrix on
CPython 3.12 and 3.14; run 3.13 when available.

## Manual verification

1. Create one `mktemp -d /tmp/jarvis-m001.XXXXXX` root with mode-0700 home/config/data/state/
   cache/runtime children; export HOME, all five XDG variables, and `PYTHONPATH="$PWD/src"`.
2. In one Python heredoc using internal APIs only, create/apply M000 migration 0001, verify schema
   1/no profiles, then apply current migrations and verify schema 2.
3. Bootstrap profiles; inspect Jarvis, record its ID, and assert defaults schema/product 2/2 plus
   section origin 2.
4. Change Jarvis accent and visible logging through `ProfileConfigService`.
5. Create `João Trabalho`; verify alias `joao-trabalho` and exact current Jarvis config clone.
6. Record its ID, rename it to `Work Profile`, verify alias `work-profile`, stable ID, and removal of
   the old alias.
7. Reject `WORK PROFILE` as a collision and reject a display name containing ASCII `-`.
8. Preview/confirm reset; verify packaged v2 defaults, origin 2, divergence from customized Jarvis,
   preserved identity/name/alias, and no fake history/model category.
9. Reject an unknown destructive scope before persistence; replace a same-tuple preview and verify
   one row; expire/prune test intents and verify deterministic order/unexpired preservation.
10. Reject Jarvis deletion, then preview/confirm secondary deletion and verify exact cascades.
11. Reopen the DB/services; verify original Jarvis ID/config persists and deleted data stays absent.
12. Inspect schema for absence of all excluded tables.
13. Validate the temp-root prefix and remove only that root; unset exported variables.

No public CLI is added for manual convenience, and no real user state is touched.

## Discoveries

- M000 matches its final ExecPlan and is committed at `cc81346`; the pre-plan worktree was clean.
- The DB contains only its migration ledger, so 0002 needs no application-data backfill/backup.
- M000 already supplies descriptor-bound SQLite opening, cross-process WAL negotiation locking,
  busy timeout, foreign keys, WAL/full sync, and immediate transactions.
- The runner owns one transaction for pending immutable migrations and forbids SQL transaction
  statements.
- Adding profile defaults changes both the defaults resource schema and material resettable
  product-default set; both versions must advance to 2.
- Foundation `IdGenerator` only exposes event/correlation IDs; profile IDs should be domain-owned
  instead of breaking that protocol.
- Correctly invoked CPython 3.14 tests pass 124; the vanished old `/tmp` venvs are expected
  disposable state, not a product defect.
- Although the M001 roadmap summary says “model-setting schemas,” the established cloning decision
  and explicit authorization defer all model records/settings to M004.
- Authoritative display-name rules do not grant hyphens; hyphens remain alias separators only.
- All current destructive state is database-owned, so a general participant/plugin framework
  would be premature.
- No authoritative contradiction or M000 bug was found.
- The first Step 1 focused test run showed that reusing profile-value validation from the defaults
  loader requires translating domain validation failures back to the registry's stable
  `defaults.invalid` boundary. It also confirmed the UTF-8 byte bound is not exceeded by 128 valid
  Unicode code points in the tested CJK case and that appearance colors are configurable, not
  fixed to the packaged palette.
- M000's migration transaction-control regex scans keywords without SQL-statement context and
  therefore rejects valid SQLite trigger bodies. M001 needs narrow triggers for permanent Jarvis
  invariants, so statement-start detection is necessary; migration transaction ownership remains
  unchanged.
- The initial statement-start correction remained line-oriented. It allowed migration-owned
  transaction control after leading comments/BOMs or a prior same-line statement. Executing each
  complete SQLite statement separately and inspecting its comment/BOM-stripped leading token
  preserves valid trigger bodies while rejecting `BEGIN`, `COMMIT`, `END TRANSACTION`, `ROLLBACK`,
  `SAVEPOINT`, and `RELEASE` in all adversarial placements tested.
- SQLite `INSERT OR REPLACE` performs conflict deletion without invoking delete triggers under the
  connection's default non-recursive-trigger mode. Permanent Jarvis therefore also needs narrow
  pre-insert/pre-update guards; delete/update guards and uniqueness alone are insufficient.
- Persisted profile configuration origins cannot use product version 1 because profile defaults
  begin at version 2. Future versions must fail closed until the running product understands them.
- Public/internal profile service boundaries require the same safe SQLite translation, including
  destructive-intent helpers used directly by tests or future callers. Validation must reject
  non-UTF-8 confirmation/display/configuration values without leaking codec exceptions.

## Architectural decisions

| Date | Decision and status | Rationale and consequence |
|---|---|---|
| 2026-08-11 | **Accepted for plan:** defaults schema/product 2/2 | Structure and resettable product set both change; new/reset origins are 2, with no fake profile v1 migration |
| 2026-08-11 | **Accepted:** persisted random UUID4 IDs | Identity is alias-independent and stable within the DB; full purge may create a new Jarvis ID |
| 2026-08-11 | **Accepted for plan:** display characters are letters, associated marks, decimal digits, ASCII spaces | Preserves the authoritative set; display-name hyphens are rejected |
| 2026-08-11 | **Accepted:** NFC display plus casefold/NFKD alias | Deterministic accent/case collisions without a transliteration dependency |
| 2026-08-11 | **Accepted:** aliases are DB data only | M003 owns registration; results provide reconciliation facts only |
| 2026-08-11 | **Accepted:** explicit relational config tables | Avoids unsafe/opaque blobs and enables constraints/atomic clone/reset |
| 2026-08-11 | **Accepted:** per-section defaults origin | Partial reset records accurate default provenance |
| 2026-08-11 | **Accepted:** clone every current M001 field | Matches configuration cloning; all model fields wait for M004 |
| 2026-08-11 | **Accepted:** reset preserves identity/name/alias | Rename and delete remain separate explicit operations |
| 2026-08-11 | **Accepted:** hashed intents with closed scopes and five-minute TTL | Cross-process replay safety with bounded persistent operational state |
| 2026-08-11 | **Accepted for plan:** direct current-store destructive coordinator | One SQLite transaction covers real M001 stores; no generic plugin/discovery/external semantics |
| 2026-08-11 | **Accepted:** immediate transactions plus revisions | Cross-process correctness does not rely on local locks |
| 2026-08-11 | **Accepted:** narrow Jarvis DB triggers | Defense in depth without duplicating broad business policy in SQL |
| 2026-08-11 | **Accepted:** no config quota category | Rows are structurally bounded and there is no independent writer/retention store |
| 2026-08-11 | **Accepted:** no new dependency | The standard library covers the complete milestone |

None of these decisions resolves the M014 web-provider or M019B signing/trust gates.

## Deviations from the original plan

No roadmap-scope deviation exists. Pre-implementation review changed the initial draft by:

- advancing defaults schema/product versions to 2/2;
- removing display-name hyphen acceptance/example;
- replacing a potentially generic participant design with direct real-component coordination,
  permitting only a narrow private shared shape if concrete duplication warrants it;
- closing/bounding destructive operation/scope persistence and expiry pruning; and
- using America/Recife for plan timestamps.

These are plan corrections only. Necessary implementation deviations are recorded below with their
authority, behavior, security impact, files, tests, and documentation consequence.

- 2026-08-11, implementation-authorized M000 defect correction required by M001: replace the broad
  migration transaction-control keyword search with complete-statement-start detection so SQLite
  trigger bodies are permitted while actual `BEGIN`, `COMMIT`, `ROLLBACK`, `SAVEPOINT`, `RELEASE`,
  and `END TRANSACTION` statements remain prohibited. This changes only
  `src/jarvis/storage/migrations.py` and migration regression tests; it preserves caller-owned
  `BEGIN IMMEDIATE`, immutable migration resources, and every M000 transaction contract.
- 2026-08-13, independent-review correction to that M000 defect fix: replace the remaining
  line-oriented detection/execution with complete SQLite statement splitting plus leading
  comment/BOM inspection. This closes comment, same-line, and BOM transaction escapes without
  interpreting strings or trigger-body `BEGIN ... END` as transaction ownership. Migration 0001
  remains byte-identical and keeps its recorded checksum.
- 2026-08-13, M001 defense-in-depth correction: extend migration 0002's narrow permanent-Jarvis
  triggers to cover SQLite replacement inserts, primary-identity updates, alias reassignment, and
  kind replacement paths. This changes no general business logic and adds no later-milestone
  schema or behavior.
- 2026-08-13, M001 correctness/security hardening: centralize safe SQLite error translation for
  every transactional profile path; validate confirmation-token encoding and size; reject corrupt
  persisted scalar, alias/display, and unsupported defaults-origin state; enforce input bounds
  before materialization; and report generated UUID collision as an invariant failure. These are
  narrow contract fixes with regression coverage, not scope expansion.

## Unresolved issues

No known technical or product issue blocks implementation.

No unresolved blocker remains. CPython 3.13 was unavailable and is conditional under the roadmap;
required CPython 3.12 and 3.14 verification passed without modifying system Python or using sudo.

## Completion criteria and evidence

| Criterion | Status | Evidence required |
|---|---|---|
| Schema-1 M000 database upgrades safely | **DONE** | 36 migration tests and temporary-XDG walkthrough |
| Defaults and section origins use 2/2 and origin 2 | **DONE** | Unit/defaults, bootstrap, clone, and reset tests |
| Jarvis bootstrap is idempotent with stable ID | **DONE** | Restart and two-process bootstrap integration tests |
| Jarvis cannot be renamed/deleted/lose `jarvis` | **DONE** | Service and direct-SQL DELETE/UPDATE/REPLACE/UPSERT security tests |
| Display/alias rules including hyphen rejection are exact | **DONE** | Unit/security Unicode and injection corpus |
| Reserved/colliding aliases fail deterministically | **DONE** | Unit, integration, and subprocess race tests |
| Rename preserves identity/data | **DONE** | Integration/restart/configuration tests |
| Creation clones one consistent current Jarvis snapshot | **DONE** | Clone tests and pre-or-post subprocess race |
| Forbidden history/model/private state is absent | **DONE** | Exact schema, tree, API, wheel, and security assertions |
| Configuration is profile-ID isolated | **DONE** | Cross-profile isolation/security tests |
| Section/profile reset uses packaged defaults | **DONE** | Customized-Jarvis section/whole reset tests |
| Intent scopes are closed/bounded and replay-safe | **DONE** | Unit/repository/SQL/token/replay tests |
| Reset/delete are centrally coordinated/transactional | **DONE** | Injected-failure rollback and cascade tests |
| Cross-process outcomes are deterministic | **DONE** | 8 required races; 20 repeated module runs/160 cases plus 20 migration/bootstrap runs/40 cases |
| No M002+ capability is introduced | **DONE** | Package/schema/import/source/resource review |
| M000 regressions and all new tests pass | **DONE** | 138 original-file and 275 full tests on 3.12/3.14 |
| Manual verification touches only temporary XDG state | **DONE** | Auto-cleaned `/tmp` five-XDG walkthrough |
| Ruff/format/mypy/wheel/diff/status pass | **DONE** | 56-file tooling, installed wheel, and final Git checks |

M001 is complete only when every criterion is **DONE**, every implementation step is reconciled,
and no unresolved issue blocks the objective.

## Handoff summary

ExecPlan path: `docs/plans/001-profile-system.md`.

Implementation order: defaults/types; migration; repositories/bootstrap; inspect/create/rename;
configuration/clone; previews/intents; reset/delete; concurrency/security; complete verification.

Schema additions: `profiles`, `profile_aliases`, `profile_configurations`,
`profile_configuration_sections`, `profile_messages`, `profile_permissions`, and
`profile_operation_intents`, with migration 0002, constraints, indexes, cascades, and narrow Jarvis
triggers.

New contracts: profile IDs/records/aggregates; name validation and alias normalization;
profile/config repositories and services; typed snapshots/patches; clone allowlist;
`ProfileDestructiveCoordinator`; closed preview/confirmation operation/scope types; typed profile
errors; and alias reconciliation results for M003.

Concurrency: immediate transactions, expected revisions, DB uniqueness, exact snapshot cloning,
state-bound one-use confirmations, inherited busy timeout, no broad retry, and no process-local
correctness lock.

Security: aliases are non-executable data; display names use the closed authoritative character
set; ownership always uses `ProfileId`; Jarvis has service/DB protection; tokens are hashed; intent
scopes are closed and bounded; reset reads packaged defaults 2; no generic serialization, external
writes, model/client/tool/network authority, or participant plugin framework is introduced.

Tests cover unit, integration, migration, subprocess concurrency, security, full M000 regression,
tooling/wheel checks, and a temporary-XDG manual walkthrough.

Unresolved issues: none blocking.

Independent-review readiness: **Yes.** This ExecPlan is decision-complete, incorporates the review
corrections, preserves M000 contracts, and contains no M002-or-later implementation.
