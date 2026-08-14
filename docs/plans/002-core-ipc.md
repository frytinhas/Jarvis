# Milestone 002 — Jarvis Core and Versioned Local IPC ExecPlan

Status: **DONE**  
Last updated: 2026-08-14 America/Sao_Paulo  
Target path: `docs/plans/002-core-ipc.md`

> This plan is decision-complete, materialized in the repository, and is the active M002 execution record.

## Purpose and user outcome

Milestone 002 establishes one authoritative persistent `jarvisd` Core process for the current Linux user and the bounded, versioned Unix-domain-socket protocol all future clients must use.

When complete, maintainers can:

- start exactly one Core for an isolated user/XDG state;
- connect multiple local same-UID clients;
- negotiate IPC protocol version 1 and capabilities;
- query Core health and the M001 profile catalog;
- address profiles by stable `ProfileId`;
- run harmless injected test requests with ordered lifecycle events;
- cancel one request without affecting another;
- disconnect without implicitly cancelling accepted work;
- resume a logical session and replay bounded in-memory events within the same Core lifetime;
- distinguish a live Core from stale or partially started runtime artifacts;
- shut down Core through an explicit same-user internal control operation;
- restart after clean shutdown or simulated crash; and
- prove cross-process correctness without opening network sockets.

This milestone introduces no assistant, model, chat, tool, or public configuration behavior.

## Scope

Included:

- one foreground `jarvisd` Core process per user/XDG state;
- lifetime single-instance ownership and concurrent-start handling;
- secure Unix-domain socket beneath the validated M000 runtime directory;
- Core lifecycle and runtime/process identity;
- bounded UTF-8 JSON framing;
- protocol-version and capability negotiation;
- typed Core-instance, logical-connection, and request identifiers;
- client-neutral request, event, error, cancellation, status, resume, and replay envelopes;
- multi-client request execution with bounded concurrency and backpressure;
- request/session-owned cancellation;
- monotonic request event sequencing and exactly one terminal event;
- disconnect-retained request ownership;
- bounded same-Core in-memory resume/replay added only after the base request lifecycle is proven;
- read-only `core.health`, `profiles.list`, and `profiles.get` operations;
- explicit internal `core.shutdown` operation;
- an internal IPC client library;
- a Python project entry point named `jarvisd`;
- test-only injected handlers and client helpers for lifecycle/concurrency proof;
- sanitized Core/IPC infrastructure diagnostics; and
- unit, integration, cross-process, security, packaging, and manual verification.

The roadmap’s mention of a model catalog does not authorize an empty or speculative model API. Model discovery and catalog ownership begin in M004, so M002 exposes only Core health and the already-implemented M001 profile catalog.

## Non-goals

M002 must not implement or create placeholders for:

- public `jarvis` chat or interactive UX;
- `jarvis-config`, profile mutation screens, executable profile aliases, or help UX;
- model directories, model discovery, model catalog, selection, or settings;
- GGUF parsing, llama.cpp, providers, model runtimes, or generation queues;
- chat, sessions, messages, learning, memory, notes, or context construction;
- Tool Broker, Policy Engine, approvals, audits, host tools, shell, filesystem, process, web, or desktop capabilities;
- TUI or Wayland integration;
- systemd, autostart, desktop entries, installation registration, or service management;
- installation into system or user `PATH`;
- `~/.local/bin` creation or management;
- installer, updater, or packaging-distribution workflows beyond declaring the wheel entry point;
- TCP, HTTP, outbound networking, telemetry, or remote configuration;
- durable request/event history or database-backed replay;
- process killing for stale-Core recovery;
- model/tool-specific event payload semantics.

Future event names such as `text_delta`, `tool_call_started`, `tool_progress`, `approval_requested`, and `tool_call_completed` are reserved protocol vocabulary only. M002 cannot route or emit them.

## Current progress

Milestone status: **DONE**

| Implementation item | Status |
|---|---|
| Protocol types, errors, and bounded codec | **DONE** |
| Runtime ownership and Core identity | **DONE** |
| Core lifecycle and composition | **DONE** |
| Base request registry, ordering, terminal arbitration, and cancellation | **DONE** |
| Unix socket sessions, routing, limits, and disconnect ownership | **DONE** |
| Base request-lifecycle completion gate | **DONE** |
| Resume and bounded replay | **DONE** |
| Resume/replay completion gate | **DONE** |
| Internal IPC client and `jarvisd` entry point | **DONE** |
| Diagnostics and security hardening | **DONE** |
| Automated and manual verification | **DONE** |

Progress log:

- 2026-08-13 America/Sao_Paulo — Read `AGENTS.md`, `ROADMAP.md`, `PLANS.md`, `docs/architecture.md`, and both completed predecessor ExecPlans in full.
- 2026-08-13 America/Sao_Paulo — Confirmed branch `new-jarvis` at `0bf9a0a`, synchronized with `origin/new-jarvis`, with a clean worktree.
- 2026-08-13 America/Sao_Paulo — Verified completion commits `cc81346` for M000 and `0bf9a0a` for M001.
- 2026-08-13 America/Sao_Paulo — Inspected the implemented XDG, private-file, SQLite, migration, defaults, error, diagnostic, clock/ID, bootstrap, profile identity, repository, and service contracts.
- 2026-08-13 America/Sao_Paulo — Fresh CPython 3.14.4 regression passed all 275 tests. CPython 3.12.13 is installed but its previous disposable pytest environment no longer exists; committed M001 evidence records the same suite passing on 3.12.13 and 3.14.4. CPython 3.13 is unavailable.
- 2026-08-13 America/Sao_Paulo — Confirmed defaults schema/product versions 2/2, packaged migrations exactly 0001 and 0002, and no existing Core, IPC, CLI, model, runtime, chat, tool, or network package.
- 2026-08-13 America/Sao_Paulo — Revised the plan after review: removed the ineffective Core control token, replaced JSON pre-scanning with bounded parsing plus iterative validation, fixed the profile catalog wire shape, separated base lifecycle and replay gates, and clarified request-ID collision, shutdown flush, packaging, and metadata-authority behavior.
- 2026-08-13 America/Sao_Paulo — No implementation or repository mutation occurred.
- 2026-08-13 America/Sao_Paulo — Implementation authorization received. Re-read all governing
  documents and predecessor ExecPlans in full. Current HEAD is `b1a6d3a` rather than the planning
  snapshot `0bf9a0a` because of a documentation-only model-content-neutrality commit; the M002
  architecture and prerequisites are unchanged. The only pre-existing worktree item is this
  untracked approved ExecPlan. Schema/defaults remain 2/2, migrations remain exactly 0001/0002,
  no Core/IPC or later surface exists, and the baseline CPython 3.14.4 suite passes 275 tests.
  Step 1 marked `IN PROGRESS` before implementation files were created.
- 2026-08-13 America/Sao_Paulo — Step 1 `DONE`. Added domain-owned UUID4 IDs, protocol-v1 exact
  hello/request validation, capability negotiation, safe IPC errors, four-byte framing, strict
  UTF-8 standard-library JSON hooks, and iterative depth/node/container/key/string validation.
  Focused unit tests pass 19 cases including duplicate keys, floats/constants, integer bounds,
  malformed escapes, structural characters in strings, parser recursion, partial frames, and
  oversized no-drain behavior. Ruff and strict mypy pass the new protocol/codec files. Step 2
  marked `IN PROGRESS` before runtime-artifact code was added.
- 2026-08-14 America/Sao_Paulo — Step 2 `DONE`. Added the strict Core lifecycle, Linux process
  evidence, descriptor-bound `core.lock` acquisition, lifetime nonblocking `flock`, safe stale
  socket/metadata classification, directory-relative identity-checked cleanup, bounded atomic
  informational metadata, Unix-path bounds, and private socket bind. Twelve focused lifecycle,
  identity, and runtime-security tests pass; socket tests required the isolated execution
  permission because the default tool sandbox rejects AF_UNIX bind with `EPERM`. Ruff and strict
  mypy pass. No code signals a PID or treats metadata as authority. Step 3 marked `IN PROGRESS`.
- 2026-08-14 America/Sao_Paulo — Step 3 `DONE`. Added one composition root that initializes M000,
  acquires Core ownership, verifies M001 Jarvis, opens bounded diagnostics, binds the listener,
  and publishes READY metadata last. Clean stop records STOPPED, closes diagnostics/listener,
  removes only owned socket/metadata, and releases the lifetime lock. Two disposable-XDG
  integration tests pass, including clean restart with a new Core instance ID; Ruff and strict
  mypy pass. Step 4 marked `IN PROGRESS`.
- 2026-08-14 America/Sao_Paulo — Step 4 `DONE`. Added atomic retained RequestId reservation,
  per-session/global admission, request-scoped cancellation controllers, legal start/completion/
  failure/cancel transitions, monotonic sequence allocation from one, and state-lock terminal
  arbitration. Seven focused tests cover cancel-before-start, completion/cancel races, ownership,
  collision non-aliasing, capacity release, and disconnect-retained work. Ruff and strict mypy
  pass. Step 5 marked `IN PROGRESS`.
- 2026-08-14 America/Sao_Paulo — Step 5 `DONE`. Added mandatory Linux `SO_PEERCRED` same-UID
  validation, handshake/session setup, serialized bounded outbound transports, idle/read/write
  deadlines, production routing for only health/profile catalog/get/shutdown, and injected
  test-only handlers. Profile responses have the exact five-field wire shape. Four integration
  tests pass for handshake/catalog, collision/cancel, disconnect ownership, and the shutdown
  terminal drain fence. Python 3.14 `AbstractServer.wait_closed()` waits for active connections;
  stop ordering was corrected to cease acceptance without waiting, then close transports before
  awaiting full server closure. Ruff and strict mypy pass. Step 6 gate is `IN PROGRESS`.
- 2026-08-14 America/Sao_Paulo — Step 6 base lifecycle gate `DONE` before any resume/replay code.
  Thirteen focused unit/integration cases pass for accepted/rejected requests, monotonic sequence,
  one terminal/no post-terminal events, retained ID collisions within/across sessions, cancel
  before/running/race outcomes, wrong-session denial, disconnect retention, concurrent client
  isolation, and shutdown cancellation. Terminal state is the authoritative in-flight status
  because admission-counter release follows terminal arbitration by one event-loop turn. Ruff and
  strict mypy pass. Step 7 marked `IN PROGRESS`.
- 2026-08-14 America/Sao_Paulo — Steps 7 and 8 `DONE`. Added in-memory 256-bit session tokens,
  constant-time proof, rotation, one attached transport, disconnected active-work retention,
  60-second completed-session expiry, status, replay-after-sequence, per-request/session/global
  replay bounds, deterministic trimming, and authoritative replay-gap errors. The first eviction
  test exposed sequence reuse after dropping old events; `next_sequence` is now independent of
  retained-list length, preserving monotonicity. The combined base/replay gate passes 18 focused
  tests including forged/rotated token denial, reconnect ownership, wrong-session status/replay,
  deterministic eviction, gap reporting, restart invalidation, collisions, and one terminal.
  Ruff and strict mypy pass. Step 9 marked `IN PROGRESS`.
- 2026-08-14 America/Sao_Paulo — Step 9 `DONE`. Added the thin asyncio `JarvisIpcClient` with
  handshake, concurrent request stream routing, cancellation, status, replay, resume, and safe
  disconnect behavior. Added `jarvisd` and `python -m jarvis.core --foreground` as the same
  foreground entry point through `pyproject.toml`; no daemonization, PATH registration, systemd,
  installer, or public probe command exists. Two focused client integration tests pass; Ruff and
  strict mypy pass. Step 10 marked `IN PROGRESS`.
- 2026-08-14 America/Sao_Paulo — Step 10 `DONE`. Added metadata-only redacted IPC diagnostics,
  ready-owner protocol probing after losing the lifetime lock, cross-process ownership tests,
  socket replacement and unsafe-artifact defenses, peer-credential fail-closed tests, slowloris/
  malformed-frame tests, connection/request admission tests, raw-error/token non-leakage checks,
  and explicit absence of a Core control-token artifact. An already terminal accepted shutdown
  now proceeds if its requester disconnects or stalls, while healthy requesters retain the drain
  fence. The CPython 3.14 matrix passes 171 unit, 75 integration, 36 migration, 55 security, and
  337 total tests; Ruff/format and strict mypy pass 86 files. Step 11 marked `IN PROGRESS`.
- 2026-08-14 America/Sao_Paulo — Interrupted-session reconstruction independently reproduced the
  recorded CPython 3.14 matrix, then reopened steps 5, 7/8, and 9 after adversarial review. The
  transport limit check and logical-session insertion were not one atomic admission; completed
  request contexts were never wholly evicted after replay trimming reached one event each, so the
  16 MiB global bound and RequestId-retention lifetime could grow without bound; expired sessions
  did not discard registry state; and a control error sharing an active RequestId could be routed
  into that request stream by the internal client.
- 2026-08-14 America/Sao_Paulo — Steps 5, 7/8, and 9 returned to `DONE`. Physical transports now
  reserve/release the connection cap under one lock before handshake. Replay trimming preserves
  active status and terminal summaries where capacity permits, deterministically evicts complete
  request contexts when needed, permits safe RequestId reuse only after eviction, and discards
  terminal state when a disconnected logical session expires. The internal client has a bounded
  control queue, strict hello shape, and pending-control-aware error routing. Four new regressions
  cover concurrent connection admission, terminal-summary byte exhaustion, expired-session
  cleanup, and control-error/request-stream isolation. The corrected focused gate passes 23 tests
  and the full CPython 3.14 suite passes 341 tests. Step 11 remains `IN PROGRESS`.
- 2026-08-14 America/Sao_Paulo — Final resource review bounded retained logical sessions at 128;
  without that separate cap, a same-UID client could churn disconnected resume shells and expiry
  tasks faster than the 60-second cleanup interval despite bounded replay bytes. The first new
  regression also exposed a pre-handshake error-envelope classification bug, which now returns
  `hello.error` until session insertion succeeds. A CPython 3.12 timing failure then showed that
  the request-limit test released its barrier before observing the rejected seventeenth request;
  the test now waits for the deterministic pre-acceptance result and passed ten consecutive runs.
- 2026-08-14 America/Sao_Paulo — Step 11 and M002 `DONE`. CPython 3.12.13 and 3.14.4 each pass 173
  unit, 76 integration, 36 migration, 57 security, and 342 total tests. The exact committed
  M000/M001 test tree passes 275 tests on each interpreter. The final focused cross-process,
  concurrency, recovery, resume, and Core security set passes 25 tests. Ruff lint/format and
  strict mypy pass 87 files. The final wheel builds without dependencies, installs cleanly outside
  the checkout, passes `pip check`, imports Core/IPC and packaged resources, exposes exactly the
  `jarvisd` foreground entry point, and has no unconditional runtime dependency. Exact schema
  audit confirms version 2, migrations 0001/0002 only, the M001 table set, and clean foreign keys.
  The fail-fast disposable-XDG walkthrough passed and removed its root; an earlier attempt was not
  counted because its verification shell failed to export the Core PID and mistook a deliberately
  stale socket for readiness. CPython 3.13 is unavailable and remains conditional.

## Repository state and prerequisites

Planning snapshot (subsequently revalidated as noted below):

```text
branch: new-jarvis
HEAD: 0bf9a0a feat: complete milestone 001 profile system
upstream: origin/new-jarvis
worktree: clean
defaults schema/product version: 2/2
database schema version: 2
runtime dependencies: none
fresh CPython 3.14 result: 275 passed
CPython 3.13: unavailable
```

Implementation preflight differs only in Git history: branch `new-jarvis` is at `b1a6d3a`, a
documentation-only authoritative clarification after completed M001. `origin/new-jarvis` matches,
the worktree contains only this untracked ExecPlan, and every listed technical prerequisite still
holds. No contradiction or user implementation change was found.

M000 contracts to reuse:

- `XdgPaths` and secure mode-0700 `$XDG_RUNTIME_DIR/jarvis-cli/`;
- mode-0600 private-file validation with owner/type/hardlink checks;
- descriptor-bound SQLite ownership;
- `JarvisError.to_safe_dict()` and centralized redaction;
- injected UTC clocks and UUID4/deterministic-ID conventions;
- bounded infrastructure diagnostics;
- isolated HOME and all-five-XDG test fixtures; and
- no-network/no-telemetry guards.

M001 contracts to reuse:

- `ProfileId` as the only IPC profile ownership identifier;
- `ProfileService.list_profiles()` and `get_profile(ProfileId)`;
- deterministic catalog order: Jarvis first, then command alias, then profile ID;
- permanent Jarvis invariants;
- typed profile errors and safe serialization; and
- schema version 2 without model/session/history tables.

No runtime dependency is required. Use standard-library `asyncio`, `socket`, `struct`, `json`, `fcntl`, `secrets`, `hmac`, `uuid`, and Linux `/proc` interfaces.

## Implementation sequence

### 1. **DONE — Define protocol values, safe errors, and bounded codec**

Create typed IPC identifiers, exact envelope models, protocol validation, and the framed JSON codec.

The codec must use CPython’s JSON parser directly after enforcing the one-MiB frame bound. It must not contain an ad-hoc structural pre-parser.

Validation:

```bash
PYTHONPATH=src python -m pytest -m unit \
  tests/unit/test_ipc_codec.py \
  tests/unit/test_ipc_protocol.py \
  tests/unit/test_ipc_errors.py
```

Recovery: no persistent state is written.

### 2. **DONE — Implement secure Core ownership and identity**

Implement descriptor-bound lifetime `core.lock` ownership, Linux process evidence, informational runtime metadata, socket-path validation, stale-artifact classification, and identity-safe cleanup.

Security controls must exist before the server can bind.

Validation:

```bash
PYTHONPATH=src python -m pytest -m unit \
  tests/unit/test_core_identity.py \
  tests/unit/test_core_lifecycle.py
PYTHONPATH=src python -m pytest -m security \
  tests/security/test_core_runtime_security.py
```

Recovery: never kill a recorded PID. Remove only validated stale socket/metadata artifacts after winning the lifetime lock.

### 3. **DONE — Compose Core lifecycle and existing services**

Implement `JarvisCore` startup around `initialize_foundation()`, M001 profile services, diagnostics, lifecycle transitions, readiness publication, graceful shutdown, and startup-failure cleanup.

Validation: lifecycle transition tests and temporary-XDG Core startup integration.

### 4. **DONE — Implement the base request registry**

Implement, without resume/replay:

- atomic request-ID reservation;
- request acceptance;
- legal state transitions;
- sequence allocation;
- terminal arbitration;
- exactly-one-terminal enforcement;
- request/session-owned cancellation;
- disconnect-retained ownership; and
- bounded in-flight request admission.

Use deterministic barriers and injected handlers for completion/cancellation races.

Validation:

```bash
PYTHONPATH=src python -m pytest -m unit \
  tests/unit/test_request_registry.py
```

### 5. **DONE — Implement Unix socket sessions and base routing**

Implement peer credential validation, handshake, read/write loops, write serialization, backpressure, disconnect handling, and only these production operations:

- `core.health`;
- `profiles.list`;
- `profiles.get`;
- `core.shutdown`.

Test-only handlers are injected into the router and are never registered in production.

### 6. **DONE — Pass the base request-lifecycle completion gate**

Before resume/replay work begins, prove:

- accepted and rejected request behavior;
- all legal/illegal transitions;
- monotonic sequencing;
- exactly one terminal event;
- no event after terminal;
- atomic RequestId collision handling;
- cancellation before start and while running;
- deterministic cancellation/completion races;
- wrong-session cancellation denial;
- disconnect does not cancel;
- slow/disconnected writers do not corrupt request state; and
- multiple requests and clients remain isolated.

Resume/replay work must not begin until these focused suites pass.

### 7. **DONE — Add bounded same-Core resume and replay**

Add logical-session resume tokens, token rotation, request status, replay after a sequence number, retention limits, and deterministic eviction.

This step may consume the already-proven request registry but must not change its base state machine, terminal arbitration, or cancellation ownership rules.

### 8. **DONE — Pass the resume/replay completion gate**

Prove:

- valid resume;
- invalid/forged/rotated token rejection;
- only one attached transport per logical session;
- request ownership survives reconnect;
- wrong session cannot inspect, cancel, or replay;
- bounded replay and deterministic eviction;
- replay-gap response is authoritative;
- RequestId collisions cannot alias retained state;
- no replay survives Core restart; and
- no durable persistence exists.

### 9. **DONE — Add internal client and foreground entry point**

Add:

```toml
[project.scripts]
jarvisd = "jarvis.core.__main__:main"
```

`jarvisd` and `python -m jarvis.core --foreground` run the same foreground Core. There is no fork, double-fork, background daemonization, systemd integration, PATH registration, `~/.local/bin` management, installer, or autostart behavior.

Add `JarvisIpcClient` for future thin clients and internal test/manual use. Do not create a public end-user IPC probe command.

### 10. **DONE — Add diagnostics and security regression coverage**

Emit bounded, redacted infrastructure events without payload bodies. Extend no-network, active-installation, raw-error, peer-credential, runtime-artifact, malformed-frame, collision, shutdown-ordering, and resource-exhaustion tests.

### 11. **DONE — Complete cross-version and manual verification**

Run CPython 3.12 and 3.14 matrices; run 3.13 if available. Run manual temporary-XDG cross-process verification, wheel checks, schema audit, diff/status checks, and update this ExecPlan with evidence.

No migration or defaults update is permitted unless a newly discovered authoritative contradiction proves one necessary.

## Exact files and components affected

Expected new production files:

```text
src/jarvis/core/__init__.py
src/jarvis/core/__main__.py
src/jarvis/core/identity.py
src/jarvis/core/lifecycle.py
src/jarvis/core/ownership.py
src/jarvis/core/requests.py
src/jarvis/core/runtime.py

src/jarvis/ipc/__init__.py
src/jarvis/ipc/client.py
src/jarvis/ipc/codec.py
src/jarvis/ipc/errors.py
src/jarvis/ipc/models.py
src/jarvis/ipc/server.py

docs/ipc-protocol.md
docs/plans/002-core-ipc.md
```

Expected production modifications:

```text
pyproject.toml
README.md
ROADMAP.md
docs/development.md
```

Expected new tests/support:

```text
tests/unit/test_ipc_codec.py
tests/unit/test_ipc_protocol.py
tests/unit/test_ipc_errors.py
tests/unit/test_core_identity.py
tests/unit/test_core_lifecycle.py
tests/unit/test_request_registry.py

tests/integration/test_core_ipc.py
tests/integration/test_core_recovery.py
tests/integration/test_core_concurrency.py
tests/integration/test_core_cross_process.py
tests/integration/test_core_resume.py
tests/integration/test_ipc_client.py

tests/security/test_core_ipc_security.py
tests/security/test_core_runtime_security.py

tests/support/core_process.py
tests/support/ipc_client.py
tests/support/manual_core_walkthrough.py
```

Expected test modifications:

```text
tests/conftest.py
tests/security/test_no_network_or_telemetry.py
tests/security/test_profile_security.py
```

Deliberately untouched:

```text
AGENTS.md
PLANS.md
docs/architecture.md
src/jarvis/config/defaults.toml
src/jarvis/storage/migration_files/0001_migration_ledger.sql
src/jarvis/storage/migration_files/0002_profile_system.sql
src/jarvis/profiles/
```

No model, provider/runtime, chat, tool, policy, memory, TUI, desktop, web, systemd, updater, or installer package is created.

## Contracts and interfaces

New typed IDs:

```python
CoreInstanceId   # UUID4, one Core process lifetime
ConnectionId     # UUID4, one resumable logical client session
RequestId        # UUID4, one request; globally unique while retained
```

They use canonical lowercase UUID text and domain-owned generators following M000/M001 conventions.

Primary internal contracts:

```python
class CoreLifecycle:
    @property
    def state(self) -> CoreLifecycleState: ...
    def transition(self, target: CoreLifecycleState) -> None: ...

class CoreRuntimeIdentity:
    @classmethod
    def capture(cls, core_instance_id: CoreInstanceId) -> CoreRuntimeIdentity: ...
    def matches_live_process(self) -> bool: ...

class RuntimeOwnership:
    @classmethod
    def acquire(cls, runtime_directory: Path) -> RuntimeOwnership: ...
    def publish_metadata(
        self,
        identity: CoreRuntimeIdentity,
        state: CoreLifecycleState,
    ) -> None: ...
    def close(self) -> None: ...

class CancellationController:
    @property
    def requested(self) -> bool: ...
    async def wait(self) -> None: ...
    def request(self) -> bool: ...

class RequestRegistry:
    async def accept(
        self,
        request: IpcRequest,
        owner: ConnectionId,
    ) -> RequestContext: ...
    async def cancel(
        self,
        request_id: RequestId,
        owner: ConnectionId,
    ) -> CancelOutcome: ...
    async def status(
        self,
        request_id: RequestId,
        owner: ConnectionId,
    ) -> RequestStatus: ...
    async def replay(
        self,
        request_id: RequestId,
        owner: ConnectionId,
        after: int,
    ) -> ReplayResult: ...

class JarvisCore:
    async def run(self) -> None: ...
    async def request_shutdown(self) -> None: ...

class JarvisIpcClient:
    async def connect(self, ...) -> HandshakeResult: ...
    async def request(self, ...) -> AsyncIterator[IpcEvent]: ...
    async def cancel(self, request_id: RequestId) -> CancelResult: ...
    async def resume(self, ...) -> ResumeResult: ...
```

Core operations remain typed and client-neutral. Clients never receive a database path or import repositories to mutate state.

## IPC protocol and framing

### Framing

Use:

```text
4-byte unsigned big-endian payload length
+
strict UTF-8 JSON object
```

Rules:

- maximum encoded JSON payload: 1,048,576 bytes;
- zero-length frames are invalid;
- incomplete headers/bodies are invalid at EOF;
- read exactly four header bytes, then exactly the declared payload;
- all writes use one complete header+payload buffer and one serialized writer per transport;
- partial socket reads/writes are normal and handled explicitly;
- header/body acquisition deadline: 5 seconds each;
- outbound drain deadline: 5 seconds;
- handshake deadline: 5 seconds;
- idle established-connection timeout: 300 seconds.

### JSON decoding and structural bounds

Use CPython’s standard `json.loads` directly after the frame-length and strict UTF-8 checks.

Decoder hooks:

- `object_pairs_hook` rejects duplicate keys and objects with more than 256 entries;
- `parse_int` rejects representations longer than 20 decimal characters and values outside signed 64-bit range;
- `parse_float` always rejects floats;
- `parse_constant` rejects `NaN`, positive/negative infinity, and other nonstandard constants.

After parsing, perform one iterative stack-based traversal over the resulting Python JSON tree. This is not a JSON parser and never interprets source characters or escapes. It validates:

- root is an object;
- maximum structural depth: 32;
- maximum entries per object/list: 256;
- maximum total nodes: 4,096;
- object keys are strings of at most 128 UTF-8 bytes;
- string values are at most 65,536 UTF-8 bytes;
- scalar values are only `str`, signed-64-bit `int`, exact `bool`, or `None`;
- floats and implementation-specific objects are impossible/rejected.

The one-MiB frame cap bounds raw input before parsing. At most one inbound frame is accumulated per transport, and the 32-transport limit bounds concurrent raw input to 32 MiB before decoder overhead.

Translate these parser failures to `ipc.invalid_frame` and close the connection:

- `UnicodeDecodeError`;
- `json.JSONDecodeError`;
- duplicate-key/object-bound rejection;
- integer/float/constant rejection;
- `RecursionError` from pathological nesting;
- post-parse depth/node/container/key/string violations.

Tests must include deeply nested arrays/objects below and far beyond CPython’s parser recursion threshold, structural characters inside strings, escaped quotes/backslashes, Unicode escapes, malformed escapes, and large but valid bounded documents. No ad-hoc pre-scan is permitted.

A declared oversized body is not drained.

### Handshake and versioning

IPC protocol version is independent of package, database, defaults, and diagnostic-envelope versions.

Current protocol:

```text
IPC_PROTOCOL_VERSION = 1
```

Initial client frame:

```json
{
  "type": "hello",
  "supported_versions": [1],
  "required_capabilities": ["request-stream-v1"],
  "optional_capabilities": ["request-cancel-v1", "session-resume-v1"],
  "client_name": "bounded identifier",
  "resume": null
}
```

Successful result includes:

```text
selected_version
negotiated_capabilities
core_instance_id
connection_id
resume_token
Core lifecycle state
```

Core selects the highest common version; initially that is exactly 1. No common version returns `ipc.protocol_mismatch` with supported versions and closes. Missing required capabilities returns `ipc.capability_mismatch` and closes. Unknown optional capabilities are omitted.

Every post-handshake frame includes `protocol_version: 1`. Adding fields or changing existing semantics requires a new protocol version or an explicitly negotiated capability.

Initial capabilities:

```text
request-stream-v1
request-cancel-v1
core-health-v1
profile-catalog-v1
session-resume-v1
event-replay-v1
core-control-v1
```

`core-control-v1` is not a distinct security principal. It is an explicit protocol-semantic opt-in available only after same-UID peer validation and successful handshake. Its purpose is to prevent ordinary clients from accidentally invoking internal lifecycle control.

### Messages

Client to Core:

- `hello`;
- `request`;
- `cancel`;
- `replay`;
- `request.status`.

Core to client:

- `hello.ok`;
- `hello.error`;
- `event`;
- `cancel.result`;
- `replay.result`;
- `request.status.result`;
- connection-level `error`.

Request envelope:

```text
protocol_version
request_id
operation
optional profile_id
payload
```

`profile_id` must be canonical `ProfileId` text and is required only by profile-scoped operations. Aliases are never ownership identifiers.

Event envelope:

```text
protocol_version
core_instance_id
request_id
sequence
event_type
terminal
payload or safe error
```

Top-level unknown fields are rejected. Unknown operations are rejected before acceptance with an unsequenced safe request error and create no request state.

## Exact Core operation representations

### `core.health`

Request:

```json
{
  "protocol_version": 1,
  "request_id": "<uuid4>",
  "operation": "core.health",
  "payload": {}
}
```

`profile_id` is forbidden.

Successful terminal payload:

```json
{
  "state": "READY",
  "core_instance_id": "<uuid4>",
  "pid": 1234,
  "started_at_utc": "<RFC3339 UTC>",
  "protocol_version": 1,
  "capabilities": ["..."],
  "active_connections": 2,
  "in_flight_requests": 1,
  "database_schema_version": 2,
  "defaults_schema_version": 2,
  "product_defaults_version": 2
}
```

No path, environment, profile configuration, or runtime metadata file contents are returned.

### Profile catalog entry

Protocol-v1 profile entries contain exactly:

```json
{
  "profile_id": "<canonical UUID4>",
  "kind": "jarvis",
  "display_name": "Jarvis",
  "command_alias": "jarvis",
  "identity_revision": 1
}
```

Allowed `kind` values are `jarvis` and `standard`.

The wire representation deliberately omits M001 `created_at_utc` and `updated_at_utc` because M002 needs identity/catalog discovery, not profile history.

It also explicitly prohibits:

- persona;
- profile context;
- configuration revision or section revisions;
- permissions;
- appearance/colors;
- waiting or goodbye messages;
- visible logging configuration;
- startup/autostart configuration;
- defaults-origin metadata;
- destructive previews or intents;
- confirmation tokens/digests;
- configuration values of any kind;
- database paths or repository details.

### `profiles.list`

Request payload is exactly `{}` and `profile_id` is forbidden.

Successful terminal payload:

```json
{
  "profiles": [
    {
      "profile_id": "<uuid4>",
      "kind": "jarvis",
      "display_name": "Jarvis",
      "command_alias": "jarvis",
      "identity_revision": 1
    }
  ]
}
```

Order is exactly the M001 catalog order:

1. Jarvis;
2. standard profiles by `command_alias`;
3. profile ID as deterministic tie-breaker.

### `profiles.get`

The request envelope requires `profile_id`; payload is exactly `{}`.

Successful terminal payload:

```json
{
  "profile": {
    "profile_id": "<uuid4>",
    "kind": "jarvis",
    "display_name": "Jarvis",
    "command_alias": "jarvis",
    "identity_revision": 1
  }
}
```

Unknown IDs become the existing safe M001 `profile.not_found` terminal error. Supplying an alias where a `ProfileId` is required yields a pre-acceptance `ipc.invalid_message`.

### `core.shutdown`

The request has payload `{}`, forbids `profile_id`, and requires:

- validated `SO_PEERCRED` with peer UID equal to Core UID;
- successful protocol-v1 handshake; and
- negotiated `core-control-v1`.

No file token or hidden secret is required. The Linux user account is the security boundary.

## Request identity and collision handling

A client-supplied `RequestId` is reserved atomically under the global request-registry lock before `request.accepted` is emitted.

While a RequestId remains retained:

- a second request with the same ID is never accepted;
- existing state is never replaced, merged, restarted, or mutated;
- the colliding request cannot observe the existing request;
- it cannot infer the existing owner;
- it cannot cancel, query, or replay the existing request;
- the response is an unsequenced `ipc.request_id_conflict`;
- the existing request continues unchanged.

This collision result is identical whether the retained ID belongs to the same or another logical session.

`cancel`, `request.status`, and `replay` perform separate ownership checks:

- retained ID owned by caller → operation proceeds;
- retained ID owned by another logical session → `ipc.request_not_owned`;
- ID not retained → `ipc.request_not_found`.

After deterministic retention eviction, the registry no longer claims the ID. A later request may reuse it as new state, but no old state remains to alias or expose.

Random UUID4 makes accidental collisions negligible, but correctness never relies on probability.

## Core lifecycle and runtime identity

States:

```text
STARTING
READY
STOPPING
STOPPED
ERROR
```

Legal transitions:

```text
STARTING -> READY
STARTING -> ERROR
READY -> STOPPING
READY -> ERROR
ERROR -> STOPPING
STOPPING -> STOPPED
```

`STOPPED` is terminal.

Readiness requires:

- secure XDG directories verified;
- Core ownership lock held;
- runtime identity captured;
- M000 initialization/migrations complete;
- M001 Jarvis invariant verified;
- diagnostics sink available;
- socket bound/listening with verified ownership/mode;
- router and request registry ready; and
- READY metadata atomically published last.

During `STARTING`, no application request is accepted. If a connection reaches a partially published listener, handshake returns `ipc.core_unavailable` with state `STARTING`.

During `STOPPING`, health may report state while new ordinary requests receive `ipc.core_shutting_down`.

### Authoritative ownership facts

These are authoritative for single-instance ownership:

1. the validated mode-0700 runtime-directory descriptor;
2. the safely opened `core.lock` descriptor;
3. the nonblocking exclusive `flock` held on that descriptor for the complete Core lifetime; and
4. for an established IPC connection, Linux `SO_PEERCRED` UID equality.

The lifetime lock is the sole authority deciding whether a cooperating Core owner exists. A process that does not hold the lock cannot clean or replace runtime artifacts.

These facts are authoritative for socket cleanup after the lock has been won:

- the lock winner’s exclusive ownership;
- current `lstat` type/UID/mode/link count of `core.sock`;
- directory-relative identity rechecks immediately before unlink.

### Corroborating evidence

The following are corroborating or diagnostic only:

- `core-runtime.json`;
- PID stored in metadata;
- Linux boot ID;
- `/proc/<pid>/stat` start ticks;
- executable/import-anchor identities;
- metadata lifecycle state;
- metadata Core instance ID.

They help clients and maintainers explain live, stale, partially started, or PID-reused conditions, but they do not confer ownership.

A forged, stale, corrupt, or mismatched `core-runtime.json` must never:

- displace a lock holder;
- cause a lock loser to remove a socket;
- authorize socket cleanup without the lifetime lock;
- signal or terminate a process;
- cause acceptance of a peer with invalid credentials;
- make a client trust a foreign UID; or
- override the live handshake’s Core instance identity.

No Core lifecycle path sends signals to a PID recovered from metadata.

### Graceful shutdown ordering

An accepted `core.shutdown` request follows the normal request lifecycle.

Exact ordering:

1. validate peer UID, handshake state, negotiated capability, and operation schema before acceptance;
2. emit `request.accepted`;
3. emit `request.started`;
4. construct and commit the sequenced terminal `request.completed` event with:
   ```json
   {"shutdown_scheduled": true}
   ```
5. store that terminal event in the logical session’s bounded replay buffer;
6. enqueue the terminal frame on the requesting transport with a writer-drain completion fence;
7. do not transition to `STOPPING` and do not close the requesting transport as part of shutdown until that fence reports that the frame was written and `drain()` succeeded;
8. after successful flush, signal the Core shutdown coordinator and transition to `STOPPING`.

If the peer independently disconnects or the transport independently fails before the fence completes:

- the accepted request remains terminal in its logical session;
- disconnect does not cancel it;
- Core may proceed with the already accepted shutdown after the writer reports transport loss;
- shutdown logic did not pre-emptively close the requesting transport.

If the requesting transport exceeds the existing five-second write/drain deadline, it is classified as a failed/stalled transport under ordinary backpressure rules. The terminal event remains recorded in memory, the failed transport closes, and shutdown proceeds. Core never begins closing a healthy requesting connection before the terminal drain fence succeeds.

After entering `STOPPING`:

1. stop accepting new connections/requests;
2. request cancellation of unfinished M002 work;
3. wait up to five seconds;
4. force-cancel remaining internal tasks and arbitrate one terminal outcome where delivery remains possible;
5. close other transports and the listener;
6. close diagnostics;
7. remove instance-owned socket and metadata;
8. transition to `STOPPED`; and
9. release the lifetime lock.

## Concurrency and cancellation

Limits:

```text
maximum connected transports: 32
maximum retained logical sessions: 128
maximum accepted in-flight requests per logical session: 16
maximum accepted in-flight requests globally: 128
maximum outbound queued frames per transport: 64
maximum outbound queued bytes per transport: 2 MiB
maximum retained replay bytes globally: 16 MiB
```

Admission occurs before task creation. Exceeding a limit returns `ipc.connection_limit` or `ipc.request_limit`. There is no unbounded task or queue creation.

One writer task serializes every transport’s frames. Frames never interleave.

A stalled writer exceeding queue or drain limits is disconnected. Disconnect does not cancel accepted work; work remains owned by the logical session.

Request state machine:

```text
RECEIVED
  -> ACCEPTED
  -> RUNNING
  -> COMPLETED | CANCELLED | FAILED
```

`RECEIVED` is internal. Protocol-visible events are:

```text
sequence 1: request.accepted
sequence 2: request.started, unless cancelled before start
sequence N: request.completed | request.cancelled | error
```

Sequence numbers start at 1 per request. The terminal event is sequenced. Exactly one terminal event is selected under the request’s state lock, and no event may be appended afterward.

Cancellation rules:

- only the owning logical connection session may cancel;
- a resumed transport inherits ownership after valid resume-token proof;
- another session receives `ipc.request_not_owned`;
- unknown request IDs receive `ipc.request_not_found`;
- cancellation before start produces `request.cancelled` without `request.started`;
- cancellation while running signals only that request’s controller;
- duplicate cancellation while pending is idempotent;
- cancellation after terminal returns `already_terminal`;
- if completion wins terminal arbitration, completion is authoritative;
- if cancellation wins, later handler output is discarded;
- request A’s controller cannot affect request B;
- disconnect alone never requests cancellation.

No per-profile generation queue is introduced.

## Reconnect and replay

Resume/replay is implemented only after the base lifecycle completion gate passes.

M002 implements bounded same-Core in-memory resume; it does not provide durable replay.

Handshake returns a random 256-bit resume token. Unlike a Core control token, this token provides a real protocol property: proof that a reconnecting transport owns a specific logical session and its request state.

A reconnect presents:

```text
expected core_instance_id
connection_id
resume_token
```

Rules:

- tokens exist only in memory and are never logged or persisted;
- comparisons use constant time;
- successful resume rotates the token;
- one logical session has at most one attached transport;
- the previous transport is closed after successful replacement;
- request ownership survives physical disconnect;
- completed disconnected sessions are retained for 60 seconds;
- sessions with active accepted requests remain until terminal, subject to global request limits;
- each request retains at most 64 events and 256 KiB;
- each session retains at most 256 events and 2 MiB;
- global replay retention is 16 MiB;
- eviction is deterministic by completed time then request ID;
- active status and terminal summary remain authoritative when earlier replay events are dropped.

Replay uses `after_sequence`. If the required gap was evicted, Core returns `ipc.replay_unavailable` with:

```text
current request state
terminal flag
earliest retained sequence
latest retained sequence
```

It never silently returns an ambiguous partial history.

Resume never survives Core restart. A new `CoreInstanceId` causes `ipc.resume_unavailable`; the client establishes a new logical session. No SQLite table is added.

## Runtime storage and recovery

Exact layout:

```text
$XDG_RUNTIME_DIR/jarvis-cli/
├── core.lock
├── core.sock
└── core-runtime.json
```

Contracts:

- runtime directory: real directory, current UID, mode 0700;
- `core.lock`: regular file, current UID, mode 0600, link count 1;
- `core.sock`: Unix socket, current UID, mode 0600, link count 1;
- `core-runtime.json`: regular file, current UID, mode 0600, link count 1, maximum 4 KiB;
- no artifact may be a symlink;
- path operations are relative to an opened verified runtime-directory descriptor where supported;
- Unix socket encoded pathname plus terminator must be at most 108 bytes;
- socket bind uses restrictive umask and post-bind ownership/mode verification.

`core-runtime.json` contains no secret:

```text
metadata schema version
CoreInstanceId
PID
boot ID
process start ticks
executable device/inode
import-anchor device/inode
Core start UTC
lifecycle state
socket filename
protocol version
capabilities
```

It is written through bounded atomic replace and treated only as informational evidence.

Single-instance strategy:

1. securely open/create `core.lock`;
2. verify descriptor/path identity;
3. attempt nonblocking exclusive `flock`, held for the full Core lifetime;
4. if lock acquisition fails, probe the socket for up to two seconds:
   - valid same-UID protocol-v1 Core → `ipc.core_already_running`;
   - lock held but Core not ready/reachable → `ipc.core_unavailable`;
5. the lock loser never removes or replaces any artifact;
6. only the lock winner may inspect and recover stale socket/metadata;
7. unsafe pre-existing symlinks, regular files at `core.sock`, foreign-owned objects, hardlinks, or special files fail closed;
8. validated stale socket/metadata artifacts are removed through directory-relative identity checks;
9. bind/listen and publish READY.

`core.lock` remains as a safe reusable lock file after clean shutdown. Socket and runtime metadata are removed. After a crash they may remain, but the next lock winner can recover them without trusting their stored PID.

## Database, migrations, and storage

No database migration is added.

Expected schema remains:

```text
schema version 2
migrations 0001 and 0002 only
```

No request, event, connection, replay, Core-runtime, chat, session, or model table is created.

Runtime metadata is bounded and exists only under XDG runtime storage. Replay/session state is memory-only and disappears on Core restart.

Tests must assert schema version remains 2 and migration 0003 does not exist.

## Security and privacy considerations

| Threat | Control |
|---|---|
| Foreign local user connects | Directory mode 0700 plus mandatory Linux `SO_PEERCRED` UID equality |
| `SO_PEERCRED` unavailable/malformed | Fail closed; initial supported platform is Linux |
| Same-UID process invokes Core control | Same UID is the explicit local security principal; handshake, capability negotiation, and explicit operation semantics prevent accidental misuse but do not claim a second principal |
| Unsafe runtime object | `lstat`/descriptor checks, owner/mode/type/link-count validation |
| Symlink or replacement race | Directory-relative operations, no-follow opens, identity rechecks |
| Concurrent Core starters | Lifetime nonblocking `flock`; only winner cleans/binds |
| Forged runtime metadata | Metadata is informational and cannot override lock or peer credentials |
| Stale socket hijack | Lock ownership plus socket validation and live handshake |
| PID reuse | Never kill by PID; boot/start/executable evidence is corroborating only |
| Partially started Core | Explicit STARTING state; no ordinary request acceptance |
| Malformed or oversized frames | Fixed header, one-MiB maximum, strict decoder |
| Deep/pathological JSON | CPython parser failure translation plus iterative post-parse limits |
| Structural characters in strings | Handled only by CPython JSON parser; no ad-hoc scanner |
| Unsafe JSON values | Duplicate-key, float, constant, and integer-bound rejection |
| Slowloris | Handshake/header/body deadlines and connection cap |
| Frame/request flooding | Connection, in-flight, task, queue, and replay limits |
| Slow reader | Bounded outbound queue/drain deadline |
| RequestId collision | Atomic reservation; conflict never aliases or replaces retained state |
| Cross-request cancellation | Logical-session ownership and per-request controllers |
| Reconnect-token guessing/replay | 256-bit session tokens, constant-time comparison, rotation |
| Replay ambiguity | Explicit replay-unavailable status and retained sequence range |
| Shutdown ordering | Terminal stored and writer-drained before STOPPING closes healthy requester |
| Raw exception leakage | `JarvisError` safe envelopes; generic internal error fallback |
| Profile alias used as identity | Protocol accepts only canonical `ProfileId` |
| Profile configuration leakage | Exact five-field catalog entries only |
| Payload logged | Diagnostics record bounded metadata and identifiers only |
| Active-installation mutation | No host mutation/tool capability exists |
| Hidden networking/telemetry | AF_INET/AF_INET6 denial and dependency/import checks |

Socket-path secrecy is not authentication. OS peer credentials are mandatory.

The same Linux UID is the local authorization boundary. M002 does not claim protection against malicious code already executing with all of that user’s filesystem and process privileges.

## Error model

IPC errors extend `JarvisError` and use safe serialization:

```text
ipc.protocol_mismatch
ipc.capability_mismatch
ipc.invalid_frame
ipc.message_too_large
ipc.invalid_message
ipc.operation_not_supported
ipc.connection_limit
ipc.request_limit
ipc.request_id_conflict
ipc.request_not_found
ipc.request_not_owned
ipc.already_terminal
ipc.resume_unavailable
ipc.replay_unavailable
ipc.core_already_running
ipc.core_unavailable
ipc.core_shutting_down
ipc.runtime_path_too_long
ipc.internal_error
```

Connection-level framing/handshake failures are unsequenced and close the connection.

Pre-acceptance request validation or RequestId collision failures are unsequenced and create no new request state.

Errors after acceptance become the request’s single sequenced terminal `error` event.

Profile lookup failures reuse M001 safe errors. Never expose traceback, raw `OSError`/SQLite text, private paths, environment values, resume tokens, persona, context, or configuration.

## Diagnostics

Reuse M000 `InfrastructureDiagnosticSink` and centralized redaction.

Minimum event types:

```text
core.starting
core.ready
core.stopping
core.stopped
core.error
core.second_start
core.stale_artifacts_recovered
ipc.socket_listening
ipc.connection_accepted
ipc.connection_closed
ipc.protocol_mismatch
ipc.invalid_frame
ipc.request_accepted
ipc.request_started
ipc.request_terminal
ipc.request_cancelled
ipc.request_id_conflict
ipc.session_resumed
ipc.replay_unavailable
ipc.internal_failure
```

Allowed fields are bounded IDs, state, safe reason codes, frame sizes, sequence numbers, durations, counters, and peer UID/PID where necessary.

Do not log:

- request payloads;
- profile display names, aliases, persona, context, or configuration;
- resume tokens;
- raw frames;
- raw exception text; or
- future chat/tool content.

## Tests

### Unit

- framing round trips and partial header/body reads;
- malformed, zero, oversized, and truncated lengths;
- invalid UTF-8;
- duplicate keys;
- NaN/Infinity/floats and integer bounds;
- malformed escapes and Unicode escapes;
- braces/brackets/quotes/backslashes inside JSON strings;
- depth, node, mapping/list, key, and string bounds;
- pathological nesting translated from `RecursionError`;
- exact-field and message-type validation;
- handshake version/capability negotiation;
- typed ID canonicalization;
- safe IPC error serialization;
- lifecycle legal/illegal transitions;
- Core identity parsing and PID-reuse mismatch;
- request state machine;
- atomic retained-RequestId collision;
- sequence starts at 1 and remains monotonic;
- exactly one terminal event;
- no post-terminal events;
- cancel-before-start, running cancel, duplicate cancel, completion/cancel race;
- disconnect-retained ownership;
- replay bounds and deterministic eviction.

### Integration

- Core starts and publishes READY;
- socket mode/owner/type are correct;
- client/server handshake succeeds;
- mismatch and missing capabilities fail safely;
- health returns active Core identity/state;
- `profiles.list` returns only exact catalog fields in deterministic order;
- `profiles.get` validates the existing Jarvis `ProfileId`;
- catalog responses exclude all configuration/private fields;
- aliases are rejected as profile IDs;
- multiple clients and concurrent injected requests;
- request accepted/started/completed;
- exactly one terminal event;
- retained RequestId collision leaves original request unchanged;
- one cancellation does not affect another request;
- disconnect does not cancel;
- base lifecycle gate passes before resume tests are enabled;
- valid resume/replay;
- invalid/expired/restarted resume;
- slow-client backpressure;
- shutdown terminal is flushed before STOPPING closes the requester;
- independently disconnected/stalled shutdown requester follows documented fallback;
- graceful shutdown;
- clean restart receives a new `CoreInstanceId`;
- simulated crash leaves recoverable artifacts;
- forged/corrupt metadata cannot displace a live Core;
- schema remains version 2;
- no real user state is touched.

### Cross-process

- two simultaneous Core starters: exactly one reaches READY;
- second start against READY Core;
- second start while first is STARTING;
- stale lock/socket/metadata combinations;
- forged metadata while lock is held;
- stale PID and simulated PID reuse;
- concurrent clients;
- global/per-session request-limit races;
- duplicate RequestId races within and across sessions;
- wrong-session cancel/status/replay;
- resume race and token rotation;
- shutdown race and terminal-drain ordering;
- stale recovery attempted by multiple starters;
- no unrelated process is signalled or terminated.

### Security

- foreign UID rejection where testable, otherwise credential-validator unit proof;
- fail-closed missing/malformed `SO_PEERCRED`;
- symlink, hardlink, FIFO, regular-file, directory, foreign-owner, and mode attacks;
- socket replacement race;
- forged metadata cannot authorize cleanup or peer acceptance;
- malformed-frame corpus;
- frame/request/connection flood bounds;
- slowloris and stalled writer;
- deep/oversized JSON and parser failure translation;
- RequestId collision cannot observe or control retained foreign state;
- resume-token forgery and absence from diagnostics/metadata;
- no obsolete Core control-token file or logic;
- raw exception/path/configuration leakage;
- no TCP/HTTP/outbound socket;
- no telemetry or new runtime dependency;
- no active-installation mutation;
- no M003+ client/configuration mutation;
- no PATH, systemd, installer, updater, model, chat, tool, or policy surface.

### Required commands

Run on CPython 3.12 and 3.14; run 3.13 when available:

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
  --wheel-dir /tmp/jarvis-m002-wheel .
git diff --check
git status --short
```

Also rerun the exact original M000/M001 test files and audit the installed wheel’s entry point, resources, runtime dependencies, and schema.

## Manual verification

1. Create a disposable `/tmp/jarvis-m002.XXXXXX` root.
2. Create mode-0700 HOME, config, data, state, cache, and runtime children.
3. Export HOME, all five XDG variables, and `PYTHONPATH="$PWD/src"`.
4. Initialize through M001 and record Jarvis `ProfileId`.
5. Start `jarvisd` in foreground/internal maintainer mode.
6. Verify exactly `core.lock`, `core.sock`, and `core-runtime.json`; inspect mode, UID, link count, and type.
7. Confirm no `core-control.token` or equivalent control-secret file exists.
8. Use `tests/support/ipc_client.py` to handshake and inspect protocol/Core identity.
9. Issue `core.health`.
10. Call `profiles.list`; verify exact five-field entries and absence of configuration/private fields.
11. Call `profiles.get` with Jarvis `ProfileId`.
12. Start a second Core and verify deterministic `ipc.core_already_running`.
13. Forge or corrupt `core-runtime.json` while the live Core holds the lock; verify it does not displace Core, remove the socket, authorize a peer, or signal a process.
14. Use two clients with injected test handlers to start concurrent requests.
15. Submit a retained duplicate RequestId; verify conflict and unchanged original state.
16. Cancel one request and verify the other completes normally.
17. Disconnect a client and verify its accepted work is not cancelled.
18. Reconnect with its resume token and replay from a known sequence.
19. Request `core.shutdown` over a same-UID connection that negotiated `core-control-v1`.
20. Verify the shutdown request’s terminal completion is observed before Core closes the healthy requesting connection.
21. Verify socket and metadata are removed while the safe reusable `core.lock` may remain.
22. Simulate validated stale socket/metadata artifacts and restart Core successfully.
23. Verify the restarted Core has a new `CoreInstanceId`.
24. Confirm Jarvis owns only a Unix socket and no TCP listener.
25. Confirm schema version remains 2 and migration 0003 does not exist.
26. Stop Core, validate the temporary-root prefix, remove only that root, and unset variables.

No public client command is added for this walkthrough.

## Discoveries

- M000 and M001 are committed as dedicated completion commits, and the current worktree is clean.
- Fresh current-tree verification passes all 275 tests on CPython 3.14.4.
- Committed M001 evidence records the same suite passing on CPython 3.12.13 and 3.14.4.
- CPython 3.12.13 remains installed, but pytest is not installed into that base interpreter; completion should recreate a disposable approved environment.
- CPython 3.13 is unavailable and remains conditional.
- M000 already supplies the secure runtime directory and private-file primitives required by Core.
- M001 exposes stable `ProfileId` and a deterministic profile catalog ordered Jarvis-first, then alias/profile ID.
- Schema/defaults versions are 2/2, and only migrations 0001/0002 exist.
- The pre-implementation repository had no Core, IPC, daemon, model, client, or later-milestone
  implementation; M002 added only its documented Core, IPC, internal client, and foreground entry
  point surfaces.
- A mode-0600 Core control token adds no authorization principal when the same UID can read it. The Linux UID plus peer credentials is the actual local security boundary.
- Resume tokens remain justified because they bind a reconnecting transport to one logical session rather than trying to distinguish Linux principals.
- CPython’s JSON parser already correctly handles strings, escapes, and Unicode escapes. A hard frame bound plus parser hooks, explicit parser-failure translation, and iterative post-parse validation is simpler and more auditable than an ad-hoc structural pre-parser.
- Runtime metadata is useful for correlation and diagnosis but cannot safely serve as single-instance authority.
- No authoritative-document contradiction requiring modification was found.
- A passing connection-limit test was insufficient because it connected clients sequentially; the
  original check/insert split admitted more than the configured maximum under concurrent hellos.
- Event-list trimming alone cannot enforce a global replay-byte limit while retaining one event
  for an unbounded number of completed requests. Whole completed-request eviction is required and
  is also the point at which a retained RequestId becomes reusable.
- The internal client must distinguish a control error from a pre-acceptance request error even
  when both carry the same RequestId; one pending serialized control call supplies that context.
- Replay-byte bounds do not bound disconnected logical-session shells or their expiry tasks. A
  separate maximum of 128 retained logical sessions closes that resource class.
- A runtime-artifact adversarial walkthrough must not use stale socket existence as restart
  readiness; newly published READY metadata is the corroborating readiness signal after the lock
  winner replaces validated stale artifacts.

## Architectural decisions

| Date | Decision and status | Rationale and consequence |
|---|---|---|
| 2026-08-13 | **Accepted:** standard-library JSON with four-byte big-endian framing | Simplest auditable dependency-free protocol |
| 2026-08-13 | **Accepted:** one-MiB pre-parse frame bound plus CPython decoder hooks and iterative post-parse validation | Avoids a second incomplete JSON parser while safely translating pathological nesting |
| 2026-08-13 | **Accepted:** protocol version 1 independent of other versions | Package/schema/default changes cannot silently alter compatibility |
| 2026-08-13 | **Accepted:** Linux `SO_PEERCRED` is mandatory | Path secrecy is not authentication |
| 2026-08-13 | **Accepted:** Linux UID is the local security principal; no Core control token | A readable same-UID token adds no distinct authorization property |
| 2026-08-13 | **Accepted:** resume tokens remain | They prove logical-session ownership and enable safe reconnect |
| 2026-08-13 | **Accepted:** lifetime `flock` is single-instance authority | PID/process name/metadata are insufficient |
| 2026-08-13 | **Accepted:** runtime metadata is corroborating only | Forged/stale metadata cannot displace Core or authorize cleanup |
| 2026-08-13 | **Accepted:** never kill stale recorded PIDs | Avoids PID-reuse process termination |
| 2026-08-13 | **Accepted:** foreground `jarvisd` project entry point only | PATH installation, systemd, autostart, and installer behavior remain later |
| 2026-08-13 | **Accepted:** request sequence starts at 1 and includes terminal | Provides one simple per-request ordering contract |
| 2026-08-13 | **Accepted:** atomic RequestId conflicts never inspect or mutate retained state | Prevents aliasing across sessions or retries |
| 2026-08-13 | **Accepted:** base request lifecycle must pass before replay work begins | Replay complexity cannot weaken terminal/cancellation invariants |
| 2026-08-13 | **Accepted:** shutdown terminal drain fence precedes STOPPING | Healthy requester receives terminal completion before server-driven closure |
| 2026-08-13 | **Accepted:** bounded in-memory same-Core replay only | No premature durable event store |
| 2026-08-13 | **Accepted:** exact five-field profile catalog | Exposes only M001 identity/discovery data |
| 2026-08-13 | **Accepted:** no migration/defaults change | Schema remains 2 |
| 2026-08-13 | **Accepted:** no new runtime dependency | Standard library covers the milestone |
| 2026-08-13 | **Accepted:** no model-catalog placeholder | M004 owns model catalog semantics |
| 2026-08-14 | **Accepted:** cap retained logical sessions at 128 | Bounds resume-token/session/expiry-task state not represented by replay-byte accounting |

## Deviations from the original plan

Implementation-time corrections preserve the approved contracts:

- connection admission now reserves a transport slot atomically rather than deriving capacity
  from the separately updated logical-session catalog;
- replay enforcement may evict a complete terminal request after deterministic event trimming can
  no longer satisfy a session/global byte bound, matching the plan's documented post-eviction
  RequestId behavior; and
- the internal client records one serialized pending control RequestId to demultiplex errors.
- retained logical sessions are separately capped at 128 because replay-byte accounting does not
  account for token/session/expiry-task overhead.

These are defect corrections, not product or scope deviations. `ROADMAP.md` received only the
required factual status reconciliation from completed M002 to not-started M003. No approved M002 interface,
milestone boundary, schema, dependency, or authority rule changed.

Review changes to the prior draft:

- removed `core-control.token` and all related runtime/recovery logic;
- made same-UID peer credentials, handshake, negotiated capability, and explicit internal operation the complete shutdown authorization contract;
- retained resume tokens solely for logical-session ownership;
- removed the proposed JSON structural pre-scan;
- selected CPython JSON decoding with hooks, parser-failure translation, and iterative post-parse validation;
- defined exact `profiles.list` and `profiles.get` wire fields and order;
- separated base request lifecycle and resume/replay into independent implementation/completion gates;
- constrained `jarvisd` to a Python project entry point with no installation registration;
- added atomic retained-RequestId collision behavior;
- added the shutdown terminal writer-drain fence;
- explicitly made `core-runtime.json` informational rather than authoritative.

The omission of a model catalog is a scope reconciliation, not an expansion: authoritative ordering and explicit user exclusions assign model discovery/catalog behavior to M004.

## Unresolved issues

No known product or implementation decision remains unresolved.

CPython 3.13 remains unavailable and conditional. A disposable CPython 3.12 verification environment must be recreated before completion.

## Completion criteria and evidence

Every criterion is **DONE**.

| Criterion | Status | Required evidence |
|---|---|---|
| Exactly one Core owns one user’s XDG state | **DONE** | simultaneous cross-process start and 25-test focused concurrency/security set |
| Lifetime lock, not metadata, is ownership authority | **DONE** | forged/stale metadata and lock-race tests plus walkthrough |
| Secure same-UID Unix socket | **DONE** | mode/owner and mandatory peer-credential tests |
| Live/stale/partial/PID-reused states are distinguished safely | **DONE** | identity/recovery matrix |
| Protocol-v1 negotiation is deterministic | **DONE** | protocol unit/integration tests and manual mismatch |
| Framing and JSON are strictly bounded | **DONE** | codec corpus and pathological parser tests |
| Profile catalog wire shape is exact and private | **DONE** | exact-key/negative-field assertions and walkthrough |
| Multiple clients operate concurrently | **DONE** | integration/cross-process tests and walkthrough |
| Request IDs cannot alias retained state | **DONE** | same/cross-session collision and eviction/reuse regressions |
| Requests emit monotonic events and one terminal | **DONE** | state-machine, race, and replay tests |
| Cancellation is request/session owned | **DONE** | wrong-owner and isolation tests/walkthrough |
| Disconnect does not cancel | **DONE** | lifecycle and resume integration/walkthrough |
| Base request lifecycle passes before replay | **DONE** | recorded 13-case gate before replay implementation |
| Replay is bounded, same-Core, and memory-only | **DONE** | byte/event/session eviction, expiry, and restart tests |
| Shutdown terminal precedes server-driven requester closure | **DONE** | writer-fence tests and observed manual terminal |
| Internal shutdown requires same UID and negotiated control semantics | **DONE** | credential/capability tests |
| Stale recovery never kills processes | **DONE** | source/security audit and crash/PID-reuse tests |
| `jarvisd` is only a foreground project entry point | **DONE** | final isolated-wheel entry-point/absence checks |
| Schema remains version 2 | **DONE** | exact migration/table/foreign-key audit |
| No network, telemetry, or M003+ surface exists | **DONE** | security/static/wheel review and Unix-only manual probe |
| Full M000/M001 regressions pass | **DONE** | 275 tests on CPython 3.12.13 and 3.14.4 |
| Manual temporary-XDG walkthrough passes | **DONE** | fail-fast 26-step walkthrough; root removed |
| Documentation and repository state reconcile | **DONE** | protocol/ExecPlan/Roadmap status, Git checks |

## Handoff summary

- Exact ExecPlan path: `docs/plans/002-core-ipc.md`.
- Implementation order: codec/protocol; lock/identity; lifecycle; base request registry; socket routing; base lifecycle gate; resume/replay; replay gate; internal client/entry point; diagnostics/security; complete verification.
- Core states: `STARTING`, `READY`, `STOPPING`, `STOPPED`, `ERROR`.
- Runtime ownership: secure runtime directory plus lifetime exclusive `flock`; metadata is informational only.
- Runtime layout: `core.lock`, `core.sock`, and `core-runtime.json`; no Core control-token file.
- Framing: four-byte big-endian length plus strict UTF-8 JSON, maximum one MiB.
- JSON bounds: CPython decoder hooks followed by iterative validation; no ad-hoc pre-parser.
- Versioning: independent protocol version 1 with required/optional capability negotiation.
- Request model: atomic ID reservation, visible accepted/running states, monotonic sequence from 1, exactly one completed/cancelled/error terminal.
- RequestId collisions: deterministic unsequenced conflict; retained state is never replaced, observed, cancelled, or replayed.
- Cancellation: owned by the logical session; disconnect does not cancel.
- Replay: separate gated feature, bounded in memory, same-Core only, no persistence.
- Shutdown: same UID plus handshake and negotiated `core-control-v1`; terminal frame drain fence precedes STOPPING.
- Profile catalog: exactly `profile_id`, `kind`, `display_name`, `command_alias`, and `identity_revision`.
- Packaging: `jarvisd` project entry point only; no PATH/systemd/autostart/installer behavior.
- Database impact: none; schema remains 2 and no migration 0003.
- New contradiction: none.
- Unresolved decisions: none.
- Exact next action: independent review of the uncommitted M002 work; do not begin M003.
- Current failing tests: none.
- Milestone status: **DONE**.
- CPython 3.13 remains unavailable and conditional; it is not a blocker under the project contract.
- No commit or push has been performed.
