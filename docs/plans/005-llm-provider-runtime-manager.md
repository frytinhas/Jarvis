# Milestone 005 — LLM Provider and Per-Profile Runtime Manager ExecPlan

Status: **DONE — independently adversarially reviewed; ready for final commit**
Last updated: 2026-08-21 America/Sao_Paulo

## Purpose and user outcome

M005 gives Core, rather than a terminal client or chat layer, ownership of local `llama-server`
processes.  A user can use the thin `jarvis-manage` client to start the selected available GGUF
for a profile, inspect its health/state, stop it, and switch it to another available GGUF.  Two
profiles may independently run the same GGUF.  There is exactly one active runtime per profile.

This is runtime verification, not a chat UX: a runtime reaches `READY` only after Core verifies its
owned loopback endpoint.  No prompt, conversation, response text, learning state, host tool, or
Policy Engine behavior is introduced.

## Scope

- Add the implementation-neutral `LLMProvider` boundary, `LlamaCppProvider`, deterministic fake
  provider, and Core-owned `RuntimeManager`.
- Start native `llama-server` with a revalidated selected M004 model, structured argv, a filtered
  environment, `/dev/null` stdin, bounded output drains, dedicated process group, and only
  `127.0.0.1` HTTP transport.
- Implement `STARTING`, `READY`, `BUSY`, `ERROR`, `STOPPING`, and `STOPPED` runtime states,
  health, start/stop/switch lifecycle, runtime-state events, and `runtime-manager-v1` IPC.
- Enforce profile isolation, one runtime per profile, an installation-configurable concurrent-load
  limit (default two active/starting runtimes), deterministic FIFO pending-start admission, and
  independent same-GGUF processes for different profiles.
- Persist metadata-only runtime event history and last-ready runtime/model evidence; use secure,
  ephemeral XDG-runtime locks, metadata, API-key files, and process artifacts.
- Integrate runtime quiescence with whole-profile reset/delete and Core shutdown; recover only
  conclusively identified stale/orphaned owned processes.

## Non-goals

- Agent prompts, Context Builder, persona/context injection, conversations, sessions, messages,
  user chat, streamed model text, learning activation, private notes, memory, or M006A/M006B CLI
  semantics.
- Tool calling, Policy Engine, Tool Broker, host capabilities, approvals, web access, external
  providers, TCP listeners beyond the owned loopback llama endpoint, autostart/systemd install,
  detached/background-task UX, physical commands/PATH work, downloads, or model-file mutation.
- No hidden provider policy, content classification, refusal injection, prompt rewrite, output
  filter, or model-purpose restriction.  The M005 provider sends any future typed chat payload
  verbatim; no Core chat operation invokes it in this milestone.

## Current progress

| Work item | Status |
|---|---|
| Authority/repository reconciliation and this ExecPlan | **DONE** |
| Schema/defaults and runtime domain | **DONE** |
| Provider/process and artifact boundary | **DONE** |
| Runtime manager, Core lifecycle, and destructive coordination | **DONE** |
| IPC and `jarvis-manage` operations | **DONE** |
| Tests, wheel audit, and manual verification | **DONE** |

Progress log: 2026-08-21 America/Sao_Paulo — planning-only investigation confirmed clean branch
`new-jarvis`, committed M004 HEAD `d770058`, schema/defaults 3/3, and migrations exactly
0001–0003.  No implementation/test/default/migration change was made.  The user selected a
configurable installation-wide concurrent-runtime limit, conservatively defaulted to two; it is
not an architectural maximum.

Progress log: 2026-08-21 America/Sao_Paulo — implementation session reconstructed the clean
committed M004 baseline.  The only pre-existing worktree item is this untracked accepted ExecPlan;
migrations 0001–0003 retain their recorded hashes and defaults/schema are 3/3.  No authority
conflict or unrelated user edit was found.  Implementation sequence step 1 is now in progress.

Progress log: 2026-08-21 America/Sao_Paulo — schema/domain step completed.  Added forward-only
`0004_runtime_manager.sql`, defaults/schema/product 4/4, runtime policy/event/last-valid domain and
repository, lazy default-capacity seed (2), revision checking, retention and reset/delete cleanup.
Focused defaults+migration tests pass (39); focused new runtime migration/provider/manager tests
pass (10), and the post-version-update full CPython 3.14 suite passes (424 predecessor tests before
the new M005 tests).  Process/artifact implementation is now in progress.

Progress log: 2026-08-21 America/Sao_Paulo — implementation steps 2–5 completed and the final
adversarial audit is in progress.  Added the implementation-neutral provider and native
`LlamaCppProvider`, descriptor-bound model execution, private authenticated loopback runtime,
process identity/owned-listener recovery, bounded output drains, deterministic fake provider,
per-profile manager/capacity queue, start/status/stop/switch/health monitoring, Core lifecycle,
reset/delete quiescence, `runtime-manager-v1` IPC, and IPC-only `jarvis-manage` controls.  Focused
runtime unit/migration/integration/security tests pass (19), Ruff passes, and strict mypy passes.
The audit tightened dual-capability negotiation, startup deadline enforcement, typed stale
metadata validation, and post-SIGKILL identity confirmation.  Full-version, wheel, and isolated
walkthrough evidence remains before DONE.

Progress log: 2026-08-21 America/Sao_Paulo — M005 verification completed.  Final CPython 3.12.13
and 3.14.4 full suites each pass 454 tests.  On each interpreter the separate marker suites pass:
unit 227, integration 117, migration 42, and security 68.  CPython 3.13 is not installed locally.
The explicit M000–M004 regression selection passes 424 tests.  The final race/ownership selection
passes 20 consecutive repetitions (120 test executions), and the authenticated native-process
security test separately passed 10 consecutive repetitions.  Ruff, Ruff format check (128 files),
strict mypy (67 source files plus the installed walkthrough), and `git diff --check` pass.

Progress log: 2026-08-21 America/Sao_Paulo — a fresh wheel built and installed into a clean
CPython 3.12 virtual environment with no runtime dependencies; `pip check` passed.  Installed entry
points are exactly `jarvis-config`, `jarvis-help`, `jarvis-manage`, and `jarvisd`.  Packaged
resources contain defaults v4 and migrations exactly 0001–0004.  The installed-wheel disposable-
XDG walkthrough passed same-GGUF isolation, capacity queuing, switch rollback, reset/delete
quiescence, authenticated loopback ownership, exact orphan recovery after Core SIGKILL, ambiguous
process non-signalling, raw-output exclusion, no orphan process, unchanged model bytes/mtime, and
schema/defaults 4.  Its validated temporary roots were deleted; real user state was untouched.

Progress log: 2026-08-21 America/Sao_Paulo — independent adversarial review found and fixed four
in-scope defects. **HIGH:** the API-key filename was passed to the child and could be replaced
between artifact validation and llama-server open; the secret is now reopened with descriptor
identity checks and passed only as a private inherited descriptor through `/proc/self/fd`, while
cleanup never unlinks a substitution. **HIGH:** cancellation could leave an owned runtime in
`STOPPING`, and stop/reset/delete could not cancel an active startup; starts are now addressable,
an active startup is cancelled before stop, and stop completes protected cleanup before propagating
cancellation. **HIGH:** reset/delete quiesced before, rather than atomically with, destructive DB
confirmation; the Core lifecycle coordinator now holds a per-profile runtime guard through the
mutation. **HIGH:** an already-exited child whose asyncio return code had not yet been observed was
mistaken for ambiguous PID reuse, retaining capacity/artifacts after a failed switch; provider stop
now briefly reaps its known child first, while a genuinely live identity mismatch remains
unsignalled and capacity/evidence remain retained.

Progress log: 2026-08-21 America/Sao_Paulo — permanent regressions cover descriptor-bound secret
substitution, active-start cancellation, cancellation-safe stop cleanup, destructive lifecycle
guard exclusion, ambiguous-start retention, unproven process-group non-signalling, and immediate
child exit/reap. Final CPython 3.12.13 and 3.14.4 matrices each pass unit 227, integration 121,
migration 42, security 71, and full 461. The exact committed M000–M004 test-file regression passes
424 on 3.12. A focused five-test native/race/lifecycle selection passed 10 consecutive times.
Ruff, format, strict mypy, and `git diff --check` pass. A newly built CPython-3.12 wheel installs
cleanly with no runtime dependencies and `pip check`; packaged defaults are v4 and migrations are
exactly 0001–0004. The installed-wheel disposable-XDG walkthrough passed after the immediate-exit
stop correction and its validated temporary roots were removed.

## Repository state and prerequisites

- M000 provides private XDG roots, SQLite migrations, quota primitives, redaction, diagnostics,
  protected-installation identity, and test isolation.  M001 provides stable `ProfileId`, reset/
  delete confirmation and persistent destructive previews.  M002 provides protocol-v1 streaming,
  replay, cancellation, and disconnect-does-not-cancel ownership.  M003 provides Core-only clients
  and logical aliases.  M004 provides `ModelId`, read-only GGUF discovery, selected associations,
  per-profile `ModelRuntimeConfig`, `RuntimeLocationConfig`, and `model-registry-v1`.
- M004 is committed, despite an older historical handoff sentence in its ExecPlan saying it was
  ready to commit.  Git HEAD and its commit message are authoritative current-state evidence.
- Current source has no runtime/provider package.  `ModelRuntimeConfig` already supplies startup,
  loopback/network-health, shutdown, resource, and structured-extra-argument values.  It remains
  M004-owned data; this milestone must not alter migrations 0001–0003 or redesign it.
- Local inspection found `/usr/bin/llama-server` (Debian build 8681) supports `--model`,
  `--host`, `--port`, `--api-key-file`, and `--no-webui`; implementation tests must use a fake,
  not this machine's executable or model library.

## Architectural contracts and decisions

### Provider and process contract

`src/jarvis/llm/provider.py` defines typed `LLMProvider`, `RuntimeHandle`, `RuntimeHealth`,
`RuntimeState`, `ProviderChatRequest`, and provider errors.  `start`, `health`, `stop`, and a
future-facing `chat`/stream primitive are provider methods.  `ProviderChatRequest` is opaque
transport data: `LlamaCppProvider` may serialize it only when M006 calls it, and must not prepend,
remove, classify, moderate, or rewrite content.  M005 exposes no chat IPC operation and performs
no inference.

`LlamaCppProvider` receives an already resolved runtime specification, not profile repositories,
IPC clients, tools, or policy.  It executes only the revalidated configured native executable with
`asyncio.create_subprocess_exec`; it never uses a shell.  The managed argv is exactly the absolute
executable plus `--model /proc/self/fd/<inherited-model-fd>`, `--host 127.0.0.1`, allocated
`--port`, managed context/resource/sampling flags, `--offline`, `--no-webui`,
`--no-webui-mcp-proxy`, and a private `--api-key-file`. `close_fds=True`; `pass_fds` contains the
validated model and API-key descriptors, and `--api-key-file` is the child's
`/proc/self/fd/<inherited-key-fd>` reference. stdin is `DEVNULL`, stdout/stderr are pipes, cwd is the private
per-runtime XDG-runtime directory, and `start_new_session=True` creates the owned process group.
The environment is exactly an allowlist (`LANG`, `LC_ALL`, `TZ`, `NO_COLOR`, `LLAMA_OFFLINE`) with
controlled values; it inherits no HOME, PATH, proxy, credential, token, or secret environment.

M005 maps only existing typed fields to managed flags.  It does **not** execute nonempty M004
`llama_server_arguments`: return typed `runtime.unsupported_extra_arguments` before spawn.  This
preserves M004's structured configuration while avoiding a generic server-option, download,
proxy, tool, TLS, listener, or log-file escape hatch.  A later explicitly authorized milestone may
add a documented per-token allowlist; it must not silently reinterpret stored tokens.

Before spawn the manager opens the model with `O_RDONLY|O_NOFOLLOW|O_CLOEXEC`, requires a regular
file, and compares device/inode/size/mtime and M004 fingerprint to the selected `ModelRecord`.
It passes that descriptor to the child, so a path swap after validation cannot substitute weights.
It separately opens/revalidates the configured executable as a regular executable; after spawn,
`/proc/<pid>/exe`, boot ID, process start ticks, and executable device/inode must match the expected
identity or the just-created process group is terminated and startup fails.  Script wrappers are
unsupported in M005 because their `/proc/<pid>/exe` identity is not the configured executable.

### Endpoint, identity, and recovery contract

The only M005 network socket is one provider-local HTTP listener at `127.0.0.1:<ephemeral-port>`.
It is not a Core API, never binds `0.0.0.0`, `::`, a hostname, or a user-configurable interface,
and makes no outbound connection.  A Core-private port allocator serializes allocation under the
runtime registry lock, probes ephemeral loopback candidates, and immediately starts the child.
It retries a bounded number of `EADDRINUSE` races; exhaustion is `runtime.endpoint_unavailable`.
This prevents Jarvis-versus-Jarvis races.  It cannot prevent a non-Jarvis process from taking a
released ephemeral port, so READY additionally requires all of: the exact child process evidence,
an owned listener socket inode found in that process's `/proc/<pid>/fd` and mapped to the expected
loopback port, and a bounded authenticated `GET /health` response using the in-memory random API
key.  A foreign listener can therefore never be accepted as this runtime.

Each profile has a 0700 `XDG_RUNTIME_DIR/jarvis/runtimes/<profile-id>/` directory, a held 0600
`runtime.lock`, and bounded 0600 JSON metadata.  Metadata carries runtime/profile/model IDs,
boot ID, PID/start ticks, process-group ID, executable identity, model identity, endpoint, and
state—never the API key, prompt, response, paths, raw argv, or server output.  PID alone is never
authority.  On Core startup and before a start, the manager enumerates database profiles rather
than trusting directory names, acquires each lock descriptor-relatively, and treats unlocked
artifacts as stale.  It signals an orphan only when persisted evidence exactly matches the live
process (including boot ID, start ticks, executable, process group, model descriptor evidence,
and owned endpoint where available).  Ambiguous, modified, linked, oversized, or non-private
artifacts are not unlinked or signalled; startup fails safely with a typed artifact error.  Exact
owned children stop with SIGTERM to their process group, wait the configured shutdown timeout,
then SIGKILL only that still-matching group.  Cleanup unlinks only descriptor-identity-matching
artifacts and fsyncs their directory.

Health is bounded by the selected per-profile model `network_timeout_seconds`; startup is bounded
by `startup_timeout_seconds`; graceful shutdown by `shutdown_timeout_seconds`.  Process exit,
health failure, malformed/non-200 health data, output-drain failure, and timeout transition to
`ERROR`, persist a safe event, release capacity, and clean only safe artifacts.  There is no
automatic restart in M005; an explicit start may recover an ERROR runtime.  `stop` is idempotent.

Server stdout/stderr are continuously drained so pipes cannot deadlock, but no raw bytes, lines,
exceptions, paths, tokens, argv, model configuration, prompts, or responses are persisted or
rendered.  Each stream has a default-bounded in-memory byte counter; only allowlisted aggregate
metadata (stream, byte count, truncation/drop count, state, reason class, duration, and runtime
ID) reaches the existing centralized redacted infrastructure sink.  This is the required bounded
sanitized server-log capture; raw stderr is never a diagnostic payload.

### Runtime manager, persistence, and profile lifecycle

`RuntimeManager` is constructed once in `CoreResources`, is the sole owner of provider instances,
and is passed to `IpcServer` and Core shutdown.  Per-profile asyncio locks linearize lifecycle
operations.  State transitions are strict: `STOPPED -> STARTING -> READY -> BUSY -> READY ->
STOPPING -> STOPPED`, with `ERROR` reachable from active states and recoverable only through an
explicit start.  M005 has no generation implementation, so production uses an idle
`GenerationCoordinator` adapter; its required contract is already fixed: switch/stop/reset/delete
wait for an active generation or request cancellation, record the outcome, and do not start a
replacement until the old runtime is STOPPED.  M006A supplies the real FIFO implementation and
binds the same adapter; M005 tests exercise it with a deterministic busy placeholder.

Start is explicit and uses the profile's selected M004 association only; unavailable, missing,
replaced, invalid, unreadable, changed, or unselected models fail without fallback.  `switch`
accepts a target `ModelId` and expected association revision.  It validates the target and creates
an unselected association with M004 defaults only when necessary, quiesces/stops the old runtime,
starts/verifies the candidate, then atomically promotes selection and `last_valid`.  A failed
candidate leaves the previously selected/last-valid model selected and leaves no active runtime.
An active runtime makes the older `profiles.models.select` route fail with
`runtime.switch_required`; that avoids persistent selection silently diverging from an active
server.

Migration 0004 adds only:

- `runtime_events(event_id PRIMARY KEY, profile_id FK CASCADE, model_id FK, runtime_id,
  state, event_kind, reason_class NULL, occurred_at_utc)` plus `(profile_id, occurred_at_utc,
  event_id)` index; state/event enums are the explicit lifecycle values and safe recovery classes.
- `profile_runtime_last_valid(profile_id PRIMARY KEY FK CASCADE, model_id FK,
  profile_model_revision, runtime_id, ready_at_utc)`.
- `installation_runtime_policy(singleton PRIMARY KEY CHECK singleton=1,
  max_concurrent_runtimes INTEGER 1..16, revision, updated_at_utc)`.

Runtime events are metadata-only, retained newest-first to the centrally defined per-profile limit
on every insert, and deleted in the existing whole-profile reset transaction as well as by profile
delete cascade.  `profile_runtime_last_valid` is updated only after READY and removed by the same
reset/delete paths.  Locks, PIDs, endpoints, API-key files, live handles, queues, and output
counters remain ephemeral XDG-runtime state.  Migration is forward-only, transactionally upgrades
3 to 4, creates no runtime, and leaves schema 3 intact on failure.  Migrations 0001–0003 remain
byte-for-byte immutable.

Defaults move to schema/product 4.  Add centrally validated runtime-manager defaults: concurrent
runtime default `2`, pending-start bound, bounded stream-capture size, event-retention count, and
bounded endpoint-allocation attempts.  The installation policy row is lazily initialized from the
default and is revision-checked through management IPC, so later configuration can change the
limit without a schema or protocol redesign.  No existing profile/model defaults are changed.

Whole-profile reset/delete is routed by a new Core lifecycle coordinator, not directly from the
IPC server to the old synchronous service.  Its preview includes a runtime participant item.  Its
confirmation quiesces/cancels the runtime first, deletes runtime events/last-valid state in the
same profile transaction, and reports each participant's planned/completed outcome.  If database
confirmation fails after a runtime has stopped, return a typed partial-cleanup failure, never
success; the profile remains and can be retried.  Core shutdown stops all owned runtimes after it
stops accepting IPC work and before releasing Core ownership.  Physical client disconnect remains
irrelevant to accepted Core runtime work; no detached-request UX is added.

### IPC and CLI contract

Keep `IPC_PROTOCOL_VERSION = 1` and existing negotiated capabilities.  Add optional
`runtime-manager-v1`; clients not negotiating it retain all M000–M004 behavior.  Add profile-ID
required operations below, all using normal accepted/started/ordered events and exactly one
encodable terminal envelope.  The dispatch layer must pre-encode each `runtime.state_changed`
event and final result before state/terminal arbitration, preserving the M004 review invariant.

| Operation | Payload | Result |
|---|---|---|
| `profiles.runtime.start` | `{}` | safe runtime snapshot |
| `profiles.runtime.status` | `{}` | safe state/health snapshot |
| `profiles.runtime.stop` | `{}` | final stopped snapshot |
| `profiles.runtime.switch` | `{model_id, expected_profile_model_revision}` | ready candidate snapshot or typed error |
| `installation.runtime.policy.get` | `{}` | policy/revision |
| `installation.runtime.policy.update` | `{max_concurrent_runtimes, expected_revision}` | updated policy |

Runtime snapshots expose only `runtime_id`, `model_id`, state, health class, and safe timestamps;
they expose no endpoint, port, PID, executable/model path, argv, token, config, or log content.
`runtime.state_changed` uses the same safe fields.  Cancellation of a start/switch request invokes
the manager's cleanup path and arbitrates the existing request cancellation once; disconnect only
detaches delivery and never cancels accepted work.

Extend `jarvis-manage` with `runtime-policy-get/update`, `runtime-start/status/stop`, and
`runtime-switch` subcommands, all Core IPC only and all requiring `runtime-manager-v1` plus the
existing stream/model-registry capabilities.  Do not add runtime controls to `jarvis-config`,
`jarvis`, profile aliases, or a new executable.

## Implementation sequence

1. **DONE — Establish schema/defaults/domain.** Prerequisite: committed M004 baseline.
   Add migration 0004, defaults v4 validation, runtime models/errors/repository, bounded event
   retention, last-valid readiness record, installation policy revisions, and whole-reset SQL
   cleanup.  Validate fresh v4, 3→4, idempotency, rollback, constraints/FKs, reset/delete, and no
   startup side effect.  Recovery: a failed migration leaves v3; no runtime artifact exists.
2. **DONE — Build hostile process/artifact primitives.** Prerequisite: step 1.  Add
   descriptor-bound model/executable revalidation, `/proc` process evidence, private artifact and
   API-key-file handling, loopback endpoint allocation/ownership proof, output drains, and typed
   provider errors.  Validate with fake executable barriers, PID reuse fixtures, malicious runtime
   artifacts, invalid model swaps, argv/environment capture, timeout and process-group tests.
   Recovery: terminate only proven child/group; otherwise retain suspicious artifact and fail.
3. **DONE — Implement provider and manager lifecycle.** Prerequisite: step 2.  Add the
   provider protocol, LlamaCpp adapter, fake provider, per-profile state machines/locks, capacity
   admission queue, stale recovery, health monitor, explicit start/stop/status/switch, and Core
   composition/shutdown.  Validate deterministic state/race/queue/recovery tests.  Recovery:
   release capacity and state lock in `finally`; record safe ERROR and preserve last-valid model.
4. **DONE — Coordinate destructive lifecycle and IPC.** Prerequisite: step 3.  Introduce
   the Core destructive lifecycle coordinator; add capability, strict request validation, safe
   runtime events, event encoding preflight, routes, and typed error projection.  Validate
   reset/delete quiescence, cancellation/disconnect/replay, old-client compatibility, and
   terminal-envelope regressions.  Recovery: no destructive success after a participant failure.
5. **DONE — Add management presentation and documentation.** Prerequisite: step 4.  Extend
   only `jarvis-manage`, IPC/architecture/development/README documentation, and the active plan.
   Validate help without Core/model start, capability failure, safe JSON rendering, packaging, and
   no direct repository imports.  Recovery: presentation owns no state.
6. **DONE — Complete verification.** Prerequisite: steps 1–5.  Run focused and full
   M000–M005 regressions, static checks, clean wheel install, controlled fake/optional-real smoke,
   and the disposable-XDG walkthrough.  Record evidence in this plan; do not start M006.

## Exact files and components affected

Create: `src/jarvis/llm/{__init__,provider,llama_cpp,fake,errors}.py`,
`src/jarvis/runtimes/{__init__,models,artifacts,repository,manager,errors}.py`, migration
`src/jarvis/storage/migration_files/0004_runtime_manager.sql`, and focused runtime unit,
integration, migration, and security tests plus a controlled fake llama-server support executable.

Modify: `src/jarvis/config/{defaults.py,defaults.toml}`, `src/jarvis/models/{models,repository,
service,errors}.py`, `src/jarvis/profiles/destructive.py`, `src/jarvis/core/runtime.py`,
`src/jarvis/ipc/{models,server}.py`, `src/jarvis/manage/__main__.py`, `pyproject.toml` only if a
new package resource needs declaration (no dependency change), `README.md`, `docs/architecture.md`,
`docs/ipc-protocol.md`, and `docs/development.md`.

Deliberately leave migrations 0001–0003, M004 GGUF scanning behavior, `jarvis-config`, simple
chat CLI semantics, physical command aliases, tools/policy, and all M006+ storage untouched.

## Security and privacy considerations

- Runtime authority is Core-only; clients, models, and `jarvis-manage` cannot spawn directly.
- Local model output gains no host authority.  No model-content governance exists in provider,
  process, health, diagnostics, IPC, or management paths.
- Revalidation plus descriptor inheritance binds the launched model to M004 identity; executable,
  PID/start-time, process group, endpoint/listener, runtime ID, and authenticated health bind
  runtime ownership.  PID/name-only kill paths are forbidden.
- Loopback HTTP is a narrow internal dependency, authenticated with an in-memory secret and no
  external listener/outbound network.  Tests prove IPv4/IPv6 external networking remains denied.
- Diagnostics are aggregate allowlists and centralized-redacted; no raw server output, paths,
  prompts/responses, profile persona/context, model config, environment values, token, IPC payload,
  or raw exception may be stored.
- No sudo, system mutation, model mutation, downloads, telemetry, inherited secret FD/environment,
  or shell parsing is permitted.  Runtime artifacts resist link/special-file/path-swap attacks.

## Tests

Use event/barrier-controlled fake providers and subprocess fakes; never use sleeps as ordering
proof or a real user model library.  Add deterministic matrices for:

- **Unit:** state transition legality; argv mapping/rejection; exact environment/FD/cwd/stdin;
  identity parsing; output bounds/redaction; error sanitization; capacity FIFO; safe snapshots;
  health parsing; model/executable and artifact validation; no prompt transformation in the
  provider transport contract.
- **Migration:** 3→4/fresh/idempotent/rollback; constraints/indexes/cascades; policy lazy seed and
  revision conflict; event retention; whole reset/delete removal; M000–M004 tables/data unchanged.
- **Integration/cross-process:** start/health/stop/status, two profiles using one GGUF, concurrent
  double-start one profile, global capacity queue/reject behavior, port collision/retry, Core
  restart stale recovery, switch success/failure/selected-model rollback, Core shutdown, and
  `jarvis-manage` IPC-only behavior.
- **Security/race:** symlink/FIFO/hardlink/changed model or executable; altered metadata; PID reuse;
  forged/stale runtime metadata; ambiguous orphan not killed; exact owned orphan killed; listener
  ownership/auth mismatch; non-loopback bind rejection; malformed health/output; timeout/process
  group cleanup; no inherited secrets/FDs; no raw logs/paths/configuration; no model-file writes;
  no external network/telemetry; no provider-policy prompt/output behavior.
- **IPC/lifecycle:** capability negotiation and old-client preservation; profile-ID/payload bounds;
  state event order and pre-encodable terminal result; cancellation during start/switch; disconnect
  then reconnect/replay; one terminal under races; reset/delete quiesce and participant-failure
  reporting; busy-generation placeholder waits/cancels/records before switch.
- **Real smoke:** optional, explicitly opt-in `JARVIS_REAL_LLAMA_SERVER` plus controlled tiny GGUF;
  it verifies documented flags/health only and never gates ordinary CI.  The default suite uses the
  fake provider and a fake local 127.0.0.1 server, with a narrowly scoped fixture permitting only
  loopback during those tests.

Run marker suites and full pytest on CPython 3.12 and 3.14; run 3.13 if installed; run Ruff,
strict mypy, `git diff --check`, clean wheel build/install plus `pip check`, and the complete
M000–M004 regression selection.

## Manual verification

1. Create one mode-0700 disposable root and set isolated `HOME`, `XDG_CONFIG_HOME`,
   `XDG_DATA_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`, and `XDG_RUNTIME_DIR` beneath it.
2. Start a freshly installed wheel's `jarvisd`.  Configure only a disposable tiny GGUF and an
   explicitly controlled fake/compatible llama-server path through `jarvis-manage`; never point at
   the real model library.
3. Select the fixture for Jarvis; run management start/status/stop and verify READY only after
   health, 127.0.0.1-only listener, no external connection, no model mutation, and no prompt/chat.
4. Create a second profile, select the same fixture, and start both concurrently; verify separate
   runtime IDs and independent stop.  Set policy limit two, attempt a bounded third start, and
   observe deterministic queued/rejected behavior with neither existing runtime killed.
5. Switch Jarvis to a second fixture, force a fake startup failure, and verify old selection remains
   last-valid, no active replacement remains, and safe diagnostics contain no raw server output.
6. Force a stale artifact and a conclusively owned fake orphan; verify safe recovery.  Also create
   an ambiguous artifact/PID-reuse case and verify it is not signalled.
7. Confirm whole-profile reset/delete previews quiesce runtimes and remove runtime events; restart
   Core and verify schema/defaults 4, cleanup, no PATH/systemd artifacts, and only the validated
   disposable root is removed.

## Discoveries

- No authoritative contradiction was found.  ROADMAP, AGENTS, and architecture agree that M005 is
  the provider/runtime milestone and that M006A first owns chat/generation persistence.
- M004's historical ExecPlan has an outdated uncommitted handoff sentence, but the clean Git HEAD
  is the reviewed committed M004 completion.  This is not an authority conflict.
- `llama-server` supports Unix-socket hosts locally, but ROADMAP explicitly assigns M005 localhost
  binding; this plan therefore uses only IPv4 loopback and does not substitute Unix sockets.
- Adversarial implementation review found and fixed: runtime routes initially required only the
  new capability instead of both runtime/model capabilities; health polling could overrun the
  startup deadline; terminal startup health could not exercise bounded port-collision retry; and
  the HTTP health writer was not closed on every timeout/error path.
- Process/artifact review found and fixed: stale metadata identity/state was not fully typed;
  post-SIGKILL recovery cleaned before proving process exit; the initial artifact path handling
  allowed a symlinked `runtimes` parent; and crash cleanup could discard evidence/capacity after an
  ambiguous ownership failure.  Runtime artifact file operations are now descriptor-relative,
  exact-owned escalation confirms death, and ambiguous evidence remains locked and intact.
- State/concurrency review found and fixed: failed health performed a duplicate stop; startup ERROR
  evidence was preassigned before strict transition validation; health-detected crashes did not
  immediately release verified-dead capacity; and a queued start held the profile lock ahead of
  stop/switch/reset/delete.  Admissions are now profile-addressable and lifecycle cancellation is
  deterministic without evicting another profile.
- The first disposable walkthrough attempts exposed only test-driver assumptions (`jarvis-cli` as
  the XDG application directory and `/usr/bin/false` being a symlink on this host).  The driver was
  corrected to use product XDG resolution and a validated regular failing executable; all
  processes from failed attempts were explicitly stopped before the final clean walkthrough.
- Independent review discovery: a mutable API-key pathname was an artifact TOCTOU even though the
  containing directory was private. Passing the validated descriptor to the child is narrower and
  testable; argv contains only its `/proc/self/fd/<n>` reference, never the secret value or a
  mutable artifact pathname.
- Independent review discovery: a vanished `/proc/<pid>` record is not always PID reuse. For an
  already-created asyncio `Process`, bounded reaping establishes that the exact child exited; only
  a still-live process requires the stronger PID/start/executable/group check before a signal.
  This preserves the ambiguous-ownership rule without leaking a capacity slot after an ordinary
  fast server failure.
- Independent review discovery: runtime quiescence must remain held through profile reset/delete
  confirmation, not merely precede it. The lifecycle guard is Core-only and adds no detached-task
  or later-milestone behavior.

## Deviations from the original plan

None.  This is the initial M005 ExecPlan; later authorized changes must be appended here.

## Unresolved issues

None.  The concurrent-runtime policy was resolved by user direction: centrally configurable,
installation-wide, default 2, not hard-coded, with deterministic non-destructive admission.

## Completion criteria and evidence

M005 is complete only when a Core-owned provider can start, health-check, stop, and switch selected
available local GGUFs; exactly one healthy runtime exists per profile; two profiles independently
run the same GGUF; lifecycle/process/endpoint identity and stale recovery are safe; reset/delete
and shutdown quiesce runtimes; diagnostics are bounded and private; protocol-v1 compatibility and
one-terminal semantics remain intact; no M006 chat or host capability appears; and all listed
automated, wheel, regression, and disposable-XDG evidence is recorded as **DONE**.

Evidence: all completion criteria above are satisfied.  Runtime snapshots/SQLite history contain
only IDs, lifecycle/health classes, safe timestamps and reason classes.  Native tests prove an
exact allowlisted environment, `/dev/null` stdin, private cwd, passed model and API-key FDs, process-group
ownership, authenticated owned IPv4-loopback health, bounded/dropped stream counts, no token in
argv/environment/database/diagnostics, and no raw stream persistence.  Source and transport audits
show no M006 chat route, prompt construction, provider-policy layer, content classifier, semantic
moderation, refusal injection, output filter, external network integration, telemetry, shell
execution, systemd/PATH work, or model mutation.  Predecessor migration hashes remain
`9ae711fc…`, `574e0098…`, and `13623f96…`; migration 0004 is
`c6c3ba04a7dcd293d0e31a3b32310e2e312f52cc20e7dc914a7a83ee892217ed`.

## Handoff summary

M005 is implemented and verified without a commit or push.  The working tree is ready for an
independent review.  M006A/M006B, chat, tools/policy, autostart, physical aliases, and PATH work
remain deliberately unstarted.
