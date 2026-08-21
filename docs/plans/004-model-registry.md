# Milestone 004 — Minimum Installation Management, Model Registry, and GGUF Discovery ExecPlan

Status: **DONE — independently reviewed; ready for final commit**  
Last updated: 2026-08-21 America/Sao_Paulo

## Purpose and user outcome

M004 gives Core one small installation-owned management surface: configured local GGUF search
directories and the configured `llama-server` executable path.  Through a thin `jarvis-manage`
client, a user can configure those values, explicitly refresh a read-only registry, inspect each
discovered model's safe metadata, size, and availability, and select it with independent
reasoning/context/runtime settings for each profile.  Creating a later profile clones Jarvis's
current selected-model association and its compatible settings atomically; it never clones
history or other private data.  A missing inherited selection is reported unavailable, never
replaced.

“Model registry” means Core-owned durable metadata about user-owned files, not a model store,
download manager, runtime, provider, or inference API.

## Scope

This is exactly ROADMAP M004 and AGENTS sections 45–57, 111, and Phase 3:

- installation-owned `RuntimeLocationConfig` for an ordered, bounded set of configured model
  directories and one optional `llama-server` path; both are managed only through the minimum
  `jarvis-manage` client/Core operations, never through `jarvis-config`;
- a Core-owned, read-only GGUF registry: bounded recursive discovery of `*.gguf`, canonical-path
  deduplication, safe lightweight metadata inspection, cached fingerprints, missing-state
  reconciliation, and stable local `model_id` records;
- persistent profile/model associations, one selected and last-valid model per profile, required
  conceptual reasoning level/context window, and the listed advanced runtime settings as
  validated structured values; and
- transactional participation in M001 profile creation so a new profile receives Jarvis's current
  model selection and applicable per-model configuration, but no model-private or historical
  state. Existing profiles are not backfilled.

## Non-goals

No model download, upload, modification, move, rename, deletion, content moderation, hidden
prompt, provider behavioral policy, runtime/process start, `llama.cpp` invocation, inference,
chat, queue, context, conversation, memory, learning, tool, Policy Engine, Tool Broker, network,
TUI, installer/PATH behavior, systemd, watcher, background indexer, hash-everything cache, or
generic provider framework belongs here. M005 owns runtime/provider and revalidates a selected
file before use; M006+ own chat and model-facing commands; M018A owns the full management client.

## Current progress

| Work item | Status |
|---|---|
| Authority and repository reconciliation | **DONE** |
| M004 implementation and tests | **DONE** |
| Final verification | **DONE** |
| Independent review | **DONE** |

Progress log: 2026-08-21 America/Sao_Paulo — independent review found and fixed four genuine
defects. **HIGH:** a regular candidate swapped to a FIFO could block in `open()` before type
validation; GGUF candidate opens now use `O_NONBLOCK`, so direct metadata reads and
descriptor-relative discovery reject non-regular files without blocking. **MEDIUM:** a directory
beyond the configured recursion limit was silently skipped while the scan was reported complete,
so known deeper records could be reconciled to missing; reaching the bound now returns the typed
`depth` partial reason and prevents unseen-record reconciliation. **HIGH:** a failed
`request.accepted` transport delivery occurred before the request worker was registered, leaving
an accepted request internally nonterminal; registration now precedes delivery, so it reaches a
replayable terminal after disconnect. **MEDIUM:** sampling input accepted noncanonical/exponent
spellings and integer wire values despite the v1 decimal-string contract, and malformed direct
runtime values could leak raw type/Unicode errors; the IPC parser now accepts a bounded canonical
decimal grammar only, normalizes negative zero, and domain validation is typed. Deterministic
regressions cover every finding.

Progress log: 2026-08-21 America/Sao_Paulo — post-review CPython 3.12.13 and 3.14.4 each pass
222 unit, 100 integration, 39 migration, 63 security, and 424 full tests. The exact committed
M000–M003 test-file selection passes 372 tests on both. CPython 3.13 is unavailable. Twenty
repetitions of the focused scanner, real IPC terminal, model lifecycle, and IPC-security matrix
passed (56 tests per repetition). Ruff check, Ruff format check, strict mypy, and `git diff --check`
pass. A fresh CPython-3.12 wheel clean-installs with `pip check`; its runtime dependencies are none,
its resources include defaults 3/3, migrations 0001–0003, model and management packages, and its
only console scripts are `jarvisd`, `jarvis-config`, `jarvis-help`, and `jarvis-manage`.

Progress log: 2026-08-21 America/Sao_Paulo — independent disposable-XDG walkthrough used six
mode-0700 roots and the freshly built wheel. Real `jarvisd`, `jarvis-manage`, real IPC, and an
interactive `jarvis-config` session configured/refresh-listed a fixture, selected it for Jarvis,
created a cloned `walkthrough` profile, independently updated its config, replaced the fixture,
and verified old selected identity `missing/replaced`, new available identity, and restart
persistence. Pre-replacement hash/mode/mtime were unchanged by discovery; only the explicit
replacement changed the fixture. No TCP listener, llama-server process, network behavior,
telemetry, physical alias artifact, symlink, inference, or model-directory mutation was observed.
Only the validated temporary walkthrough root was removed.

Progress log: 2026-08-21 America/Sao_Paulo — completed the takeover. The final frozen-code
matrix passes on CPython 3.12 and 3.14 (207 unit, 98 integration, 39 migration, 63 security, 407
full on each); CPython 3.13 is not installed. The M000–M003 selection passes 370 tests on each
supported interpreter. The real IPC regression passed 25 consecutive runs and the focused
scanner/lifecycle concurrency matrix passed 20. Ruff, Ruff format, strict mypy, and diff checks
pass. A clean CPython-3.12 wheel and disposable-XDG evidence are recorded below.

Progress log: 2026-08-21 America/Sao_Paulo — the adversarial scanner/parser, diagnostic sentinel,
real-Core route/capability/error/restart, destructive lifecycle, and concurrent profile-model
matrices are complete. One additional reconciliation defect was found: a scan stopped by a
configured bound could mark unvisited known records missing. Partial scans now report their
bounded reason and do not perform authoritative unseen-record reconciliation; the permanent test
retains two known available records after a one-candidate partial scan.

Progress log: 2026-08-21 America/Sao_Paulo — takeover reproduced the reported
`profiles.models.select` failure with a permanent two-second-bounded
`JarvisIpcClient -> Unix socket -> Core` integration test. Instrumented evidence proved the
SQLite selection committed and the association read returned; Core then created
`request.completed`, but protocol-v1 encoding rejected floating-point sampling defaults in the
terminal payload. Because terminal arbitration had already committed `COMPLETED`, the send
exception could not arbitrate an error and the client remained after `request.accepted` and
`request.started`. M004 decimal settings now use protocol-v1 decimal strings at the IPC boundary,
and Core validates the exact completion envelope before terminal arbitration. The real-Core
regression and a narrow unencodable-handler lifecycle regression pass. Remaining M004 matrices
and final verification are still in progress.

Progress log: 2026-08-21 America/Sao_Paulo — inspected authoritative documents and M000–M003
implementation; created this planning-only ExecPlan. No production/test/migration/dependency
change has been made. The local full suite reached 336 passes; 30 existing Unix-socket Core/IPC
tests fail in this container because AF_UNIX `bind`/`connect` return `EPERM`, not because of M004.

Progress log: 2026-08-21 America/Sao_Paulo — began implementation. Added defaults v3, immutable
`0003_model_registry.sql`, model identity/configuration types, a descriptor-based bounded GGUF
metadata reader, registry persistence/scanner, profile-creation clone hook, Core capability/router
work, and minimal `jarvis-manage`. Verified the authoritative ggml GGUF specification: header is
magic/version/uint64 tensor count/uint64 KV count and each KV is key/string + uint32 type + encoded
value; parser deliberately stops after KV records. Focused CPython 3.14 unit+migration baseline:
219 passed. The IPC and complete integration wiring remains in progress.

Progress log: 2026-08-21 America/Sao_Paulo — added four generated-fixture GGUF unit tests; they
pass on CPython 3.14. Full suite is not green: 329 passed / 41 failed. Thirty-plus failures are
the pre-existing container AF_UNIX `EPERM` limitation; remaining predecessor assertions still
name M003 schema/default/script values and need the authorized M004 expectation updates. Strict
`mypy` cannot run because this environment has no `mypy` module. `git diff --check` passes.

Progress log: 2026-08-21 America/Sao_Paulo — continuation reconciled the live diff, replaced the
path-walk discovery route with descriptor-relative candidate opens and descriptor-based GGUF
parsing, added profile-model configuration IPC routes and typed ModelError IPC projection, and
made whole-profile reset/delete account for profile-model associations. Updated predecessor
expectations only for M004's v3 defaults/schema and the new `jarvis-manage` entry point. CPython
3.14 full suite currently passes (370). M004 remains IN PROGRESS: scanner adversarial coverage,
registry diagnostics, clean-wheel audit, lint/type tooling, AF_UNIX Core walkthrough, and required
cross-version evidence are not yet complete.

Progress log: 2026-08-21 America/Sao_Paulo — hardened discovery to retain typed invalid and
unreadable candidates rather than silently dropping them; completed `models.get` and the thin
management profile-model routes; added bounded registry diagnostics containing counts, reason
classes and durations only; and added focused scanner/reconciliation coverage. Python 3.12 and
3.14 each pass the full suite (373), Ruff and strict mypy pass, and a fresh Python-3.12 wheel
installs cleanly with defaults v3 and migrations 1–3. M004 is still IN PROGRESS because the
complete hostile-race/real-Core M004 IPC matrix and the required disposable-XDG walkthrough are
not yet recorded.

## Repository state and prerequisites

- Branch `new-jarvis`, HEAD `4d5916f340d00eb75c52c7a5e1a5a3356661ca22` (`feat: complete
  milestone 003 profile configuration client`); working tree was clean before this plan.
- M000 supplies XDG roots, SQLite migration runner, quotas, safe typed errors, redaction,
  installation identity/protection, and test isolation. M001 supplies UUID4 `ProfileId`, profile
  transactions/revisions and destructive-operation coordination. M002 supplies the sole Core and
  protocol-v1 streaming IPC. M003 supplies `profile-management-v1`, thin profile configuration
  presentation, and logical aliases only.
- Packaged schema is version 2, migrations are exactly `0001_migration_ledger.sql` and
  `0002_profile_system.sql`; defaults schema/product versions are 2/2; production dependencies
  are empty; scripts are only `jarvisd`, `jarvis-config`, and `jarvis-help`.
- No `llm`, GGUF, model catalog, model manager, `jarvis-manage`, model migration/table, or M004
  test code exists. `profiles.models` is the profile-domain type module, not model-registry code.

## Contracts and interfaces

### Ownership and persistence

Core is authoritative. Clients use only IPC and never receive database paths or repositories.
`ModelId` is a new opaque UUID4 typed identifier; it is neither a filename nor a profile key.
`ModelRecord` contains `model_id`, canonical path, device/inode identity, size, mtime-ns, parsed
safe metadata, fingerprint, availability (`available`/`missing`/`unreadable`/`invalid`), and
last scan timestamp. A model remains one logical record while the same canonical path has the
same file identity/fingerprint; replacement at that path creates a new `ModelId` and marks the
old record missing/replaced. A moved file is a new record in M004: no cross-path move inference.

Fingerprint = SHA-256 over a bounded identity serialization: canonical path, `(st_dev, st_ino)`,
regular-file size, mtime-ns, and a digest of the bounded parsed GGUF header/metadata bytes. It is
not a whole-file content hash. This gives deterministic cache invalidation without multi-GB reads;
M005 must restat/open the file and compare this fingerprint immediately before runtime use.

Persist `installation_runtime_config`, `models`, `model_paths` (one canonical path per record in
M004 is sufficient but path is deliberately separate for future reconciliation), and
`profile_models`. `profile_models` has composite primary key `(profile_id, model_id)`, per-pair
revision, selected flag/configuration, and last-valid marker. A partial unique index enforces at
most one selected and at most one last-valid association per profile. Foreign keys cascade only
from profile deletion; model-record rows are retained so missing selections remain descriptive.

### Core and IPC

Add optional capability `model-registry-v1`; retain protocol version 1. Require it for new
operations. Operations are single-result streams under existing request/terminal semantics:

| Operation | Profile ID | Payload/result |
|---|---:|---|
| `installation.runtime.get/update` | forbidden | validated directory list and optional runtime path |
| `models.refresh` / `models.list` / `models.get` | forbidden | scan summary or sanitized model records |
| `profiles.models.list` | required | profile associations/configuration/availability |
| `profiles.models.select` | required | `{model_id, expected_profile_model_revision}` and selected association |
| `profiles.models.config.get/update` | required | `{model_id}` / validated structured config + revision |

`jarvis-manage` requires `request-stream-v1` and `model-registry-v1`; it presents only model
directories/runtime path, refresh/list/detail, and selection/configuration. It must not expose
profile persona/preferences, a free-form command line, or M018A health/update/repair features.
`jarvis-config` stays profile-first and unchanged in M004.

`ModelRuntimeConfig` is data only: reasoning `{off,low,medium,high,max}`, positive bounded
context window, temperature/top-p/top-k/min-p/repeat penalty within documented numeric ranges,
nonnegative bounded GPU layers/threads/batch size, boolean flash attention, positive bounded
startup/generation/tool/network/shutdown timeouts, and a bounded array of individual
`llama-server` argument tokens. It rejects NUL, shell syntax is not interpreted, and the M005
adapter decides the provider-specific mapping. No arbitrary argument string is accepted.

### GGUF reader and discovery

Use a standard-library-only `jarvis.models.gguf` reader. It opens a descriptor read-only with
`O_NOFOLLOW|O_CLOEXEC` where available, requires a regular file (`fstat`), parses little-endian
GGUF magic/version/header and only metadata key/value records needed for safe display:
`general.name`, `general.architecture`, `general.description`, `general.file_type`,
`general.quantization_version`, `general.size_label`, `general.basename`, and
`tokenizer.ggml.model` when present. Unknown metadata types are skipped only after their bounded
encoded length is validated; tensor descriptors/data are never read. Values returned are bounded
UTF-8 text/scalars; invalid UTF-8 is unavailable metadata, never a raw exception.

Set constants in the implementation and test their boundaries: max configured directories 32,
canonical directory path 4096 bytes, recursion depth 16, 100,000 directory entries per refresh,
100,000 candidate files, 16 MiB metadata/header read budget, 8,192 metadata entries, 256-byte
key, 16 KiB displayed string, 64 KiB individual array payload, and 16 MiB total metadata payload.
Exhaustion ends the scan with a typed partial/limit result and leaves previously known records
intact. Discovery is explicitly user-requested, synchronous within one Core request, and takes no
filesystem lock beyond its descriptors; concurrent refreshes serialize through one registry lock.

Directories are canonicalized at configuration update, must exist and be directories, and must
be distinct after canonicalization. Discovery walks descriptors depth-first, skips symlinked
directories/files and all non-regular entries, never follows links, and deduplicates candidate
files by canonical path plus `(dev,inode)` before parsing. Hard links therefore yield one model
record; duplicate configured roots/canonical paths yield one candidate. Every descriptor is
`fstat`-checked before and after bounded parsing; identity/size/mtime change makes that candidate
`unreadable` with reason `changed_during_scan`, not a partially trusted record. Model directories
and files are never opened writable and discovery creates no files within them.

## Database, migrations, defaults, diagnostics, errors, concurrency

Add immutable migration `0003_model_registry.sql`; no backfill is needed because schema-2 has no
model state. The migration creates the tables/indexes/foreign keys above and updates M001's
profile-creation transaction through a model-clone participant executing on the same SQLite
connection. A schema-2 database upgrades atomically; failure leaves schema 2. Reset/delete
participants preview profile-model configuration as configuration and remove associations on
full reset/delete only; no private model data exists yet. Section reset for M001 remains unchanged.

Add defaults schema/product 3/3 only because M004 introduces resettable per-model defaults and
scanner limits. Defaults include no model directory and no runtime path, reasoning `medium`, a
safe positive context default, structured advanced defaults, and all limits above. M001 default
upgrade must preserve existing profile fields and introduce no selected association; its versioned
reset uses v3 values only after migration support is in place.

Registry diagnostics are infrastructure diagnostics: event type, counts, durations, stable IDs,
availability/reason class, and bounded sizes only. Never persist raw model metadata strings,
paths, user configuration values, GGUF bytes, exception text, or runtime argument values in
diagnostics. Central redaction remains mandatory. No network/telemetry is added.

Define typed, sanitized `ModelError` subclasses: not found, unavailable, invalid GGUF, unreadable
model, invalid runtime location/configuration, scan limit exceeded, concurrent modification, and
database busy/conflict. Safe details are enums/counts/IDs only. Selection fails closed unless the
current record is `available`; a record becoming unavailable later remains selected but reports
unavailable and M005 cannot start it. No fallback selection exists.

Core serializes refreshes and uses immediate SQLite transactions only for reconcile/configuration
commits. Parsing happens outside the write transaction; commit rechecks current scan generation
and retries/reports a typed concurrent-refresh conflict. Profile creation begins one immediate
transaction, snapshots Jarvis configuration plus selected available-or-unavailable association
and settings once, and commits both new profile and clone atomically. Concurrent changes use
M001 revisions plus profile-model revision; no model file is held open after scan.

## Security and privacy considerations

Threat controls: hostile paths/links/special files are skipped; directory/file swaps are detected
with descriptor identity checks; hardlinks are deduplicated without trusting names; sparse/huge
files cannot trigger whole-file reads; malformed/truncated/overlong/recursive GGUF structures are
bounded and typed; concurrent truncation/replacement is not trusted; no parser writes, executes,
maps tensors, allocates attacker-sized structures, follows links, exposes raw errors, or accesses
outside configured roots. Runtime path is only a validated stored location in M004, never
executed. The registry has no model-generated-content path, prompt construction, moderation,
topic restrictions, response filtering, policy/broker decision, network access, sudo, or
installation mutation.

## Implementation sequence

1. **DONE — Reconcile defaults/types/errors.** Added `ModelId`, records/configuration,
   installation config, limits, defaults v3 migration function, typed errors, and serializer
   validators. Validate exact boundary/unit tests and defaults compatibility.
2. **DONE — Add migration and repositories.** Created immutable `0003`, model/association
   repositories, atomic reconciliation and revision-checked profile association writes. Validate
   schema-2 upgrade, constraints, FKs, rollback, and no schema/data leakage.
3. **DONE — Add safe scanner/GGUF reader.** Implemented the descriptor parser and scanner;
   fingerprinting, refresh/missing reconciliation. Validate fixture and adversarial tests before
   wiring it to Core.
4. **DONE — Integrate Core/profile creation.** Core composition, capability/router, clone,
   reset/delete, capability/error/cancellation/concurrency/restart, and client-boundary audits pass.
5. **DONE — Add minimum `jarvis-manage` presenter.** The thin presenter, module, and console entry
   point provide local help and typed safe errors; `jarvis-config` has no installation operations.
6. **DONE — Complete verification/documentation.** Updated architecture/protocol/README and
   this plan; completed all checks, the wheel audit, and disposable-XDG walkthrough. Rollback of a failed
   code deployment is ordinary package rollback; migration is forward-only and migration failure
   leaves the prior schema transactionally intact.

## Exact files and components affected

Expected production additions: `src/jarvis/models/{__init__,errors,models,gguf,scanner,repository,
service}.py`, `src/jarvis/management/{__init__,models,service}.py`, and a dedicated minimal
`src/jarvis/manage` presenter. Expected modifications: defaults TOML/loader, migration resources,
Core composition, IPC models/server/client, profile service/destructive coordinator/repository,
`pyproject.toml`, README, architecture and IPC documentation. Do not add provider/runtime/chat
packages or dependencies.

Expected tests/support: small programmatically generated valid/minimal GGUF byte fixtures and
unit tests for reader/scanner/configuration; migration tests; Core IPC/profile clone integration;
security filesystem/race/limits tests; cross-process refresh/profile-clone tests; disposable-XDG
management walkthrough. Fixtures must be tiny and temporary; never inspect a real model directory.

## Tests and verification

Unit: metadata primitives across supported GGUF versions; malformed magic/version, truncation,
overflow, hostile lengths/counts, unknown types, huge/sparse files, invalid UTF-8; metadata and
directory limits; fingerprint changes; canonical duplicate/symlink/hardlink/special-file handling;
structured runtime validation; error sanitization.

Integration: migration 2→3/idempotency/rollback; explicit refresh/list/get/missing transitions;
same model selected with different settings in two profiles; unavailable selection/no fallback;
atomic Jarvis selected-model clone, no backfill, no history namespaces; M003 boundary/no direct DB;
Core restart persistence and capability negotiation.

Security/concurrency: directory/file replacement between walk/open/parse and before association;
symlink swap; concurrent truncation; duplicate roots; parser CPU/memory/read-budget limits; model
file bytes/mtime unchanged; two refreshes and refresh versus selection/profile creation; malformed
IPC; no network/telemetry/raw paths/metadata in diagnostics; runtime path never executed.

Run marker suites and full pytest on CPython 3.12 and 3.14. Run 3.13 only if installed; record
unavailability without failing the milestone. Run `ruff check .`, `ruff format --check .`, strict
`mypy src tests`, `git diff --check`, and clean wheel build/install under 3.12. Wheel audit must
prove packaged defaults and migrations 0001–0003, no unintended dependencies, and exactly
`jarvisd`, `jarvis-config`, `jarvis-help`, and new `jarvis-manage` scripts.

## Manual verification

1. Make disposable mode-0700 HOME/XDG roots and a tiny fixture tree with nested valid GGUF,
   duplicate root/hardlink/symlink, malformed file, and unrelated file; record fixture hashes.
2. Start Core; use `jarvis-manage` to add the fixture root/runtime path, refresh, inspect the one
   deduplicated valid record and typed invalid result, and confirm hashes/tree are unchanged.
3. Select/configure the model for Jarvis; create a profile through `jarvis-config`; verify the
   same selection/settings and a distinct profile ID, with no history/private data.
4. Configure different settings for a second profile sharing the record. Remove/replace the
   GGUF, refresh, and verify missing/unavailable state with no substitution.
5. Restart Core and verify persisted registry/configuration, schema/defaults v3, no network,
   no PATH/launcher artifact, no model-process start, and no model directory mutation; remove only
   the validated temporary root.

## Discoveries and architectural decisions

- **Accepted, 2026-08-21:** M004 is not discovery-only. ROADMAP and architecture agree it also
  owns minimum installation configuration, profile-model associations/settings, and clone
  extension. No authoritative contradiction was found.
- **Accepted:** persistence/migration is necessary: required selection, profile settings, cached
  fingerprint, and missing-state must survive Core restart; rebuild-only state cannot meet the
  stated user outcome.
- **Accepted:** no whole-file hash, watcher, background scan, cache layer, or provider abstraction.
  Explicit refresh plus durable bounded fingerprint is the smallest compliant design.
- **Accepted:** moves are not recognized in M004; replacement/move inference would require a
  content identity policy beyond the stated lightweight fingerprint requirement.
- **Accepted, 2026-08-21:** protocol v1 deliberately excludes floating-point JSON scalars, while
  M004 sampling settings require decimals. `model-registry-v1` therefore represents those four
  decimal fields as bounded decimal strings on the wire and converts them only at Core's typed
  model boundary. This preserves protocol-v1 validation rather than silently widening it.
- **Discovery, 2026-08-21:** terminal results were registered before their exact IPC envelope was
  validated. Any handler result rejected by the codec could become an undeliverable recorded
  terminal. Core now validates the exact completion envelope first, allowing the normal
  exactly-one error arbitration path to remain available.

## Deviations from the original plan

No scope expansion was accepted. Migration `0003` uses `model_id` as the `model_paths` primary key
and a non-unique canonical-path index, instead of making canonical path unique. This is required by
the authoritative replacement contract: the old missing/replaced record and the new available
record must both retain descriptive path history and remain addressable by stable ID. The migration
is still uncommitted and immutable once accepted. The originally described scan-generation recheck
was unnecessary: the service's process-local refresh lock serializes parsing and reconciliation,
while SQLite immediate transactions serialize the short commit against profile operations.

Independent review made no product or scope deviation. Its four corrections preserve the existing
M004 contracts for hostile filesystem handling, bounded partial reconciliation, protocol-v1 wire
format, and accepted-request ownership.

## Unresolved issues

None for M004. CPython 3.13 was not installed and is conditional. The exact numeric parser/scan
limits above are implementation defaults selected for safe, testable boundedness; they are not
user-facing product choices. Future GGUF incompatibility work must not add a parser dependency
without its license, privacy, and telemetry review.

## Completion criteria and evidence

M004 is complete only when installation settings remain outside `jarvis-config`; the Core-owned
registry safely and deterministically scans/refreshes user-owned GGUF without mutation; stable
IDs and profile-specific settings persist; profile creation atomically clones exact selected-model
configuration without private/history data or fallback; missing/replaced files fail descriptively;
all stated verification, wheel, manual, privacy, race, and cross-version evidence is recorded;
and M005+ behavior is absent.

Evidence: real AF_UNIX Core tests prove accepted/started/exactly-one-terminal semantics for all
M004 routes, typed errors, cancellation, replay, independent requests, capability negotiation,
and restart. Descriptor-race tests deterministically cover configured/candidate symlinks,
directory and candidate replacement/disappearance, path/descriptor mismatch, non-regular swaps,
concurrent truncation, hardlinks, invalid paths, configured bounds, partial reconciliation, and
read-only bytes/mtime preservation. GGUF tests cover versions 1–3, invalid/truncated/overlong
headers and metadata, UTF-8, value/count/tensor/array limits, unsupported types, non-finite values,
and non-regular descriptors. Sentinel diagnostics contain only allowlisted counts/classes/duration.
The disposable mode-0700 XDG walkthrough used `jarvisd`, `jarvis-manage`, and interactive
`jarvis-config`; proved selection/config clone, isolation, reset/delete, missing/replaced state,
restart persistence, schema/defaults 3, no network listener, no model process, no alias artifact,
and no pre-replacement fixture hash/mtime mutation; then removed only its validated `/tmp` root.
A newly built CPython-3.12 wheel installs into a clean virtual environment with `pip check` clean,
no runtime dependencies, importable model resources, defaults 3/3, exactly migrations 0001–0003,
and exactly `jarvisd`, `jarvis-config`, `jarvis-help`, and `jarvis-manage` console scripts.

Independent review update: the four verified corrections above have permanent tests for FIFO
substitution, depth-bound reconciliation, accepted-delivery failure/replay, canonical decimal and
nonfinite input, negative-zero normalization, and malformed runtime-domain values. The post-review
matrix is unit 222, integration 100, migration 39, security 63, full 424 on each CPython 3.12.13
and 3.14.4; the exact M000–M003 committed test-file selection is 372 on both. The focused 56-test
scanner/terminal/lifecycle/security selection passed 20/20 times. Schema remains 3; migration
filenames are exactly `0001_migration_ledger.sql`, `0002_profile_system.sql`, and
`0003_model_registry.sql`; defaults schema/product remain 3/3. No model-content governance or
moderation, provider-policy prompt, runtime/inference, network, telemetry, or physical
profile-command behavior exists in M004.

## Handoff summary

M004 is independently reviewed and ready for final commit. The worktree intentionally remains
uncommitted. Do not begin M005 before the user authorizes the normal final-commit step.
