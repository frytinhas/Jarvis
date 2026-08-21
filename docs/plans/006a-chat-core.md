# Milestone 006A — Core Chat Pipeline ExecPlan

Status: DONE — independently reviewed, ready for final commit
Last updated: 2026-08-21 America/Sao_Paulo

## Purpose and user outcome

M006A implements the client-neutral Core chat pipeline on top of the committed M005 provider and
per-profile runtime manager. A protocol test client must be able to submit a text request, observe
streamed local-model text, and verify durable session, message, learning, diagnostic, cancellation,
and terminal-state behavior. M006B remains a separate later milestone that presents these contracts
through the simple CLI.

## Scope

- Agent Engine for text-only chat, centralized Context Builder, typed chat request/stream contracts,
  sessions, turns, messages, context budgeting, and per-profile/model isolation.
- Transactional first-user-chat learning-state initialization.
- One active generation per profile runtime; deterministic FIFO with a maximum of 16 queued
  generations excluding the active generation; concurrent generation across different profiles.
- Queued/active cancellation, disconnect-does-not-cancel ownership, bounded reconnect/attach/status,
  model-switch quiescence, and reset/delete quiescence.
- Typed provider streaming through M005 `LLMProvider`; only `LlamaCppProvider` owns authenticated
  loopback HTTP/SSE transport.
- Bounded profile/model chat diagnostics, storage reservation before generation, persistence of
  successful/failed/cancelled turns, streaming IPC events, and exactly one terminal event.
- Migration `0005_chat_pipeline.sql` and defaults schema/product version 5/5 are planned deliverables
  of implementation, not created in this planning session.

## Non-goals

M006A does not implement CLI presentation, slash-command UX, tools, Tool Broker, Policy Engine,
approvals, private notes, semantic or episodic memory, web, TUI, desktop, physical aliases/PATH,
installer behavior, or any M007+ feature. Real-GGUF presentation is a final M006B acceptance path,
not an M006A presentation feature. Model-generated tool-looking text remains ordinary text.

## Current progress

| Work item | Status |
|---|---|
| Repository/authority reconciliation | DONE |
| M006A design and handoff | DONE |
| Migration/defaults/domain implementation | DONE |
| Provider streaming implementation | DONE |
| Agent Engine/Context Builder | DONE |
| Generation coordination and persistence | DONE |
| IPC `chat-v1` integration | DONE |
| Tests, documentation, wheel, and walkthrough | DONE |

Progress log: 2026-08-21 America/Sao_Paulo — committed HEAD `052b9bc258bb167cc3621be58a1da1761ba186f5`
on `new-jarvis` was independently checked. Worktree was clean, schema/defaults were 4/4, the
existing source-path suite passed 461 tests, and no M006 implementation exists. This file is the
only materialized M006 plan; M006B is deliberately not materialized yet.

Progress log: 2026-08-21 America/Sao_Paulo — implementation session independently confirmed
branch `new-jarvis`, the same committed M005 HEAD, and a worktree containing only this untracked
ExecPlan. The authority documents and M005 Core/IPC/profile/model/runtime/quota/diagnostic seams
were inspected. Packaged defaults and schema are 4/4, migrations are exactly 0001–0004, and the
provider chat path remains the intentional M005 byte placeholder. Schema/defaults/domain work is
now in progress; no M006B surface is being added.

Progress log: 2026-08-21 America/Sao_Paulo — after an interrupted implementation turn, worktree
reconciliation found the complete first-pass M006A production surface present: migration/defaults,
chat domain/repository/learning/diagnostics, ContextBuilder, provider SSE/fake stream, FIFO
coordinator, Agent Engine, runtime BUSY integration, destructive cleanup, and `chat-v1` routes.
Focused predecessor migration/default/provider tests passed (62 tests), and `ruff check src` plus
strict `mypy src` passed. All implementation slices remain IN PROGRESS until new adversarial tests
and full integration verification prove and correct the contracts.

Progress log: 2026-08-21 America/Sao_Paulo — continuation resumed at the unfinished destructive
lifecycle race. A deterministic active-generation reset test exposed a lock-order cycle: the
runtime lifecycle guard held the per-profile runtime lock while waiting for generation quiescence,
while cancellation cleanup needed that lock to leave BUSY. Quiescence now completes before the
lifecycle guard acquires the runtime lock. The focused reset race and chat/coordinator/IPC suite
pass, followed by a complete CPython 3.12 source suite result of 480 passed. Storage/provider
adversarial coverage, documentation, cross-version verification, packaging, and the disposable-XDG
walkthrough remain in progress.

Progress log: 2026-08-21 America/Sao_Paulo — adversarial completion added deterministic
diagnostic quota rotation/exhaustion and simulated ENOSPC-before-admission coverage; first-learning
and same-session ordinal races; queued/active cancellation durability; partial provider failure;
model-switch drain; reset/delete/shutdown quiescence; provider timeout, framing/delta/response
bounds, malformed input, disconnect, UTF-8, metadata, and cancellation cleanup. Provider hardening
also mapped oversized header framing and negative content lengths to typed failures and retained
bounded completion finish metadata.

Progress log: 2026-08-21 America/Sao_Paulo — final verification passed. CPython 3.12.13 and
3.14.4 each passed unit 244, integration 133, migration 47, security 71, and full 495 tests;
CPython 3.13 was unavailable. The isolated predecessor-only selection passed 461. Twenty focused
concurrency/cancellation repetitions (160 test executions) and ten provider-stream repetitions
(90 test executions) passed. Ruff check, Ruff format check, strict mypy, and `git diff --check`
passed. A fresh offline wheel installed into a clean CPython 3.12 venv with `pip check`, zero runtime
requirements, unchanged four entry points, defaults 5/5, migrations 0001–0005, and all chat/default/
migration resources. The installed-wheel mode-0700 six-root disposable-XDG walkthrough passed Core
startup, streaming, learning/diagnostics, FIFO, cross-profile concurrency, queued/active
cancellation, disconnect/replay, switch, reset/delete, shutdown, and restart. No M006B entry point
or host tool was added.

Progress log: 2026-08-21 America/Sao_Paulo — independent adversarial review reproduced two
in-scope races not covered by the completion report. Context was built before FIFO ownership, so a
later durable user message could enter an earlier request and a queued request could miss the
preceding assistant response. Context construction and successful-turn finalization now occur while
the generation lease is held; history admits only completed turns. Runtime switch/stop/profile
lifecycle quiescence drained existing work but did not close future admission, allowing a new chat
to slip between quiescence and lifecycle locking. GenerationCoordinator now provides a held
quiescence gate used by those lifecycle operations. Permanent regressions cover both cases. Focused
chat/IPC/coordinator/provider tests (25), full suite (497), all marker suites, Ruff, strict mypy,
and diff checking passed on CPython 3.12.13; the full suite also passed on CPython 3.14.4. The
disposable-XDG walkthrough passed from the source tree. Wheel verification remains blocked in this
environment because neither available CPython environment has the declared hatchling build backend;
the required `pip wheel --no-build-isolation` command fails before building.

Progress log: 2026-08-21 America/Sao_Paulo — the remaining packaging blocker was completed in
isolated temporary Python 3.12 environments. Hatchling 1.32.0 was installed offline from the
repository/tool cache, a fresh uncached wheel was built with `pip wheel --no-deps
--no-build-isolation`, and the wheel archive contained no bytecode artifacts. Its metadata has no
base runtime `Requires-Dist` entries (only the declared `dev` extras), and its console scripts are
exactly `jarvisd`, `jarvis-config`, `jarvis-help`, and `jarvis-manage`; no public `jarvis` chat
entry point exists. The wheel contains defaults/resources, chat modules, and exactly migrations
0001–0005. Installation into a separate clean Python 3.12 venv passed `pip check`; installed
imports succeeded and packaged defaults reported schema/product 5/5. The earlier apparent bytecode
finding was caused by inspecting installed files after imports generated `__pycache__`; direct wheel
archive inspection is clean. No production defect or packaging change was required. M006A is now
ready for final commit; no M006B surface was added.

## Repository state and prerequisites

Consume M000–M005 contracts: XDG and SQLite migration/quota foundations; profile identity,
configuration, reset/delete coordinator, and logical aliases; model registry and per-profile model
configuration; protocol-v1 request lifecycle, cancellation, bounded replay, and disconnect
semantics; and M005 `LLMProvider`, `LlamaCppProvider`, `RuntimeManager`, runtime states, startup,
health, stop, switch, and quiescence. Core is the only owner of repositories, runtimes, and chat
state. Runtime startup/health/autostart currently do not initialize learning.

Implementation requires CPython 3.12 and 3.14 (3.13 when available), provisioned pytest/Ruff/mypy,
and deterministic fake providers. No model download or multi-GB GGUF is required for automated or
M006A manual verification.

## Architecture and contracts

### Agent Engine and ownership

The Agent Engine resolves stable profile/model/session identity, asks RuntimeManager to auto-start
the selected runtime when necessary, reserves diagnostic storage, initializes first-chat learning,
builds context, admits a generation, invokes the provider, persists lifecycle state, and emits the
client-neutral stream. It never calls localhost HTTP, repositories from a client, host tools, or
policy services.

### Provider streaming contract

Replace the M005 placeholder byte-echo behavior with typed streaming primitives. `ChatRequest`
contains bounded role/content messages, generation/runtime settings, and correlation metadata;
provider transport details are not exposed. `ProviderStreamEvent` represents a UTF-8 text delta,
completed usage/token metadata when available, or a typed failure. `LLMProvider.chat()` is an async
stream and supports generation timeout and cancellation. Malformed SSE/JSON, invalid UTF-8,
provider disconnect, partial generation, timeout, and unavailable completion metadata produce typed
failures or bounded partial completion according to the turn contract.

`LlamaCppProvider` alone serializes authenticated requests to the managed `127.0.0.1` llama-server
endpoint, parses streaming SSE, enforces response/delta bounds, and closes the owned stream on
cancellation. The Agent Engine never depends on llama.cpp-specific protocol details.

### RuntimeManager coordination

Chat requests call RuntimeManager for selected-runtime resolution and safe auto-start. A profile has
at most one active runtime and one active generation. Generation admission is FIFO per profile,
bounded at 16 queued requests, and permits different profiles to generate concurrently. Runtime
state is BUSY during generation and returns to READY after success, cancellation, or failure when
the process remains healthy. Runtime/provider failures release admission and finalize the turn.

Model switching waits for the active generation, or explicitly cancels and records it, before the
old runtime is stopped and the replacement starts. Reset/delete hold the existing profile lifecycle
guard, quiesce or cancel queued/active generations and runtimes, then perform destructive cleanup;
partial cleanup is never reported as success.

### ContextBuilder and provenance

ContextBuilder is the only model-input assembler. Contributions are typed, bounded, ordered, and
carry provenance. M006A order is exactly:

1. `CORE_PROTOCOL`: documented Jarvis technical/product protocol only.
2. `PROFILE_PERSONA`.
3. `PROFILE_CONTEXT`.
4. `USER_CONFIGURED`: explicit existing profile/model behavioral configuration only.
5. `TECHNICAL_FORMATTING`: required model/runtime formatting only.
6. `CONVERSATION`: newest recent durable messages that fit.
7. `USER_REQUEST`.

The configured context window is budgeted deterministically; oldest conversation is truncated first,
while mandatory persona/context/current request content is preserved or rejected before generation
if it cannot fit. No later-memory, private-note, workspace, tool, permission-description, or raw-log
source is added in M006A.

Jarvis adds no provider policy, censorship, semantic moderation, refusal instruction, cybersecurity
restriction, political/content rule, classifier, output filter, or rewriting. Captured provider
requests must prove exact provenance and absence of undocumented policy layers. Native behavior of
the selected local model and explicit profile configuration remain its responsibility.

### Sessions, turns, and messages

Conversation ownership is `(profile_id, model_id, session_id)`, with stable `session_id`, `turn_id`,
and request/diagnostic correlation IDs. A new chat resolves the latest resumable session; `/clear`
in M006B will request a new session without deleting history. Session lifetime is independent of
physical IPC or terminal lifetime. A request owns one turn, while accepted work remains Core-owned
after disconnect. Reconnect/attach reports authoritative active/terminal state and bounded partial
output rather than creating a competing generation.

The user message is durable in the admission transaction. Assistant text is retained incrementally
within bounds as partial content and finalized only on success; cancelled/failed turns retain
structured state and bounded partial text when present, never a successful assistant result.
Session message ordinals are unique and monotonic; timestamps are normalized UTC. Existing history
remains under the model that generated it.

### Learning-state minimum

The first user-facing Agent Engine transaction for each `(profile_id, model_id)` transactionally
creates/activates the minimum learning-state row before generation. Runtime discovery, startup,
health, and autostart never consume it. State supports active/finished status and the later M006B
status/start/finish operations, but no private-note or broader learned-memory behavior.

## Persistence, migration, defaults, and quotas

Migration 0005 creates only M006A-owned tables: sessions, turns, messages, minimum learning state,
bounded profile/model chat diagnostics, and any required chat-storage policy/accounting records.
Foreign keys, composite ownership indexes, unique session ordinals, request/turn identity, and
profile reset/delete cascades must prevent cross-profile/model confusion. Profile creation clones
configuration but no chat/history/learning/diagnostic rows. Reset/delete removes owned chat rows after
quiescence and retains only the existing sanitized destructive audit evidence.

Defaults schema/product versions advance from 4/4 to 5/5 during implementation. Chat writers enforce
limits immediately: per-profile/model diagnostic retention, per-session conversation storage,
per-message/context bounds, bounded partial output, and the 16-entry generation queue. Before any
generation, the diagnostic service reserves enough capacity for the minimum auditable lifecycle
record. It rotates only closed, inactive, unreserved records; ENOSPC or failed reservation aborts
before unlogged generation. Large payloads use bounded excerpts and explicit truncation metadata;
structural lifecycle/error events remain persisted.

## IPC `chat-v1`

Add an optional negotiated `chat-v1` capability while retaining protocol version 1. Add
client-neutral operations for chat submission/session resolution, turn attach/status, learning
status/start/finish, and human-only bounded diagnostic summaries. Chat streams use monotonically
sequenced `response_started`, `text_delta`, `response_completed`, and `error` events. Tool events
remain reserved. Every accepted request has exactly one terminal event; terminal envelopes are
encoded/validated before arbitration. Existing request cancellation, status, replay, bounded event
retention, 2 MiB outbound backpressure, and disconnect-does-not-cancel rules remain in force.

Human diagnostic responses use dedicated IPC result types that ContextBuilder cannot consume. A
slow client is detached/fails delivery under existing transport bounds while Core continues work.

## Security, privacy, and diagnostics

All model input is local and provider-owned; llama-server remains authenticated loopback-only. Core
authority is separate from model output freedom. Profile/model/session identifiers are parsed as
canonical opaque IDs and never inferred from aliases or untrusted text. No client accesses SQLite,
repositories, runtime handles, raw server output, audit records, secrets, or diagnostic storage
directly.

Chat diagnostics are persisted regardless of visible logging mode, centrally redacted, bounded, and
correlated by profile/model/runtime/session/request/turn IDs. Raw infrastructure diagnostics and
audit records are separate stores and never become context, memory, notes, or prompt contributions.
Secrets, tokens, cookies, private keys, authorization headers, and credential-bearing URLs are
redacted before persistence/rendering.

## Implementation sequence

1. **DONE — Schema/defaults/domain.** Add migration 0005, defaults 5/5, typed chat models,
   repositories, storage policies, quota participants, profile clone/reset/delete participants, and
   migration/fresh/rollback/isolation tests.
2. **DONE — Context and provider stream.** Add ContextBuilder provenance/budget contracts,
   typed provider request/events, LlamaCppProvider authenticated SSE transport, fake streaming
   provider, timeout/cancellation/failure mapping, and captured-request neutrality tests.
3. **DONE — Generation coordinator and Agent Engine.** Add session/turn admission, FIFO 16
   queue, cross-profile concurrency, learning initialization, message/diagnostic transactions,
   partial-output bounds, runtime BUSY coordination, model-switch/reset/delete quiescence, and
   deterministic lifecycle tests.
4. **DONE — IPC integration.** Add `chat-v1` capability, operations, streaming events,
   attach/status/replay integration, cancellation, backpressure, exactly-one-terminal tests, and
   human-only diagnostic route isolation.
5. **DONE — Documentation and verification.** Update architecture/protocol/development/
   README and this ExecPlan; run the complete predecessor regression and M006A verification matrix.
   M006B presentation remains unstarted.

## Exact expected files and modules

Expected additions include:

- `src/jarvis/chat/__init__.py`, `models.py`, `errors.py`, `context.py`, `repository.py`,
  `conversation.py`, `learning.py`, `diagnostics.py`, `coordinator.py`, and `agent.py`.
- `src/jarvis/storage/migration_files/0005_chat_pipeline.sql`.
- Focused unit/integration/migration/security tests and deterministic streaming fake-provider support.

Expected modifications include `src/jarvis/llm/provider.py`, `src/jarvis/llm/llama_cpp.py`,
`src/jarvis/llm/fake.py`, `src/jarvis/runtimes/manager.py`, `src/jarvis/core/runtime.py`,
`src/jarvis/ipc/models.py`, `src/jarvis/ipc/server.py`, `src/jarvis/ipc/client.py`, profile
destructive/clone participants, defaults loader/resource, and the architecture/protocol/development/
README documentation. Do not modify M000–M004 migrations. Do not add CLI presentation files in
M006A, physical entry points, tools, or M006B files.

## Test matrix

- Context contribution order, exact provenance, persona/context injection, language behavior,
  context budgeting/truncation, mandatory-content overflow, no hidden provider policy, and exact
  captured provider request.
- Profile/model/session isolation, hostile identifiers, message ordering, session resume/attach,
  partial/empty assistant output, timestamps, and failed/cancelled turn durability.
- First-learning transaction race; runtime startup/health/autostart not consuming first-run state;
  explicit learning state transitions.
- Same-profile FIFO, queue bound/rejection, different-profile parallelism, queued cancellation,
  active cancellation, generation timeout, provider crash/disconnect, malformed stream, partial
  stream, and one terminal event.
- Model-switch wait/cancel/quiescence; reset/delete quiescence and cleanup; client disconnect
  continuing Core work; bounded replay/status/attach; slow-client backpressure.
- Storage reservation, rotation eligibility, per-message/context bounds, ENOSPC before generation,
  diagnostic redaction/isolation, raw logs/audit/human diagnostic responses never entering context.
- Migration v4→v5, fresh install, rollback/checksum behavior, foreign keys/indexes, clone/reset/
  delete isolation, and all M000–M005 predecessor regressions.
- Security tests for no host tools, no network beyond managed loopback, no direct provider HTTP from
  Agent Engine, no secret leakage, no policy/censorship layer, no cross-profile confusion, and no
  model-file mutation.

## Verification and manual walkthrough

Run on CPython 3.12 and 3.14, and 3.13 when available:

```text
pytest -m unit
pytest -m integration
pytest -m migration
pytest -m security
pytest
ruff check .
ruff format --check .
mypy src tests
python -m pip wheel --no-deps --no-build-isolation --wheel-dir <temporary-wheel-dir> .
git diff --check
```

Audit the wheel for exactly packaged resources, schema/defaults 5/5, no runtime dependencies,
unchanged public entry points, and importability from a clean installed wheel. Use disposable
mode-0700 HOME/XDG roots, start Core with the deterministic fake provider, and use a test IPC client
to exercise two profiles, same-profile FIFO, cross-profile concurrency, cancellation, disconnect /
resume/attach, learning, persistence, diagnostics, model switch, reset/delete, and cleanup. Never
touch real user state or require a real model for M006A.

## Discoveries

- HEAD is the committed, independently reviewed M005 state despite stale historical handoff wording
  in earlier ExecPlans.
- M005 `ProviderChatRequest`/`chat` is intentionally reserved and must become the typed streaming
  contract in M006A without exposing llama.cpp transport outside `LlamaCppProvider`.
- Existing IPC already supplies version 1, capabilities, request lifecycle, bounded replay,
  cancellation, and disconnect-does-not-cancel semantics; M006A extends it with `chat-v1`.
- Existing RuntimeManager exposes a generation-coordinator quiescence seam; M006A supplies its
  real coordinator while preserving RuntimeManager ownership of process lifecycle.
- The first destructive-lifecycle integration test found a real lock-order cycle between the
  profile runtime lock and generation cancellation cleanup. Waiting for GenerationCoordinator
  quiescence before acquiring the runtime lock preserves the required ordering and lets the stream
  restore BUSY safely before runtime stop/reset.

## Architectural decisions

- **Accepted, 2026-08-21:** M006A is Core-only; M006B is a separate later presentation milestone.
- **Accepted, 2026-08-21:** chat auto-starts the selected runtime through RuntimeManager.
- **Accepted, 2026-08-21:** one active generation per profile runtime; FIFO queue maximum 16 queued
  excluding active; different profiles may generate concurrently.
- **Accepted, 2026-08-21:** latest resumable session is selected automatically; physical terminal/
  IPC lifetime does not own session lifetime; disconnect does not imply cancellation; `/clear` later
  creates a new session without destructive history deletion.
- **Accepted, 2026-08-21:** ContextBuilder is the sole input assembler with the exact provenance/order
  in this plan and no hidden provider policy or semantic content moderation.
- **Accepted, 2026-08-21:** migration 0005 and defaults/schema 5/5 are implementation deliverables,
  not planning-session changes.

## Deviations from original plan

None. M006A stayed within its Core-only contract. M006B was not materialized or implemented.

## Unresolved issues

None. Numeric queue size, auto-start, and latest-session semantics were explicitly decided during
planning. Provider/model-specific token counting and SSE details are implementation contracts owned
by the provider and must remain within the typed boundaries above.

## Completion criteria and evidence

M006A is complete only when migration/defaults 5/5 are applied safely; Core can stream a real typed
provider response through a fake provider contract; sessions/messages/learning/diagnostics are
isolated, bounded, durable, and quota-reserved; ContextBuilder provenance and neutrality tests pass;
FIFO/cancellation/concurrency/model-switch/reset/delete/disconnect semantics pass; IPC emits bounded
streaming events with exactly one terminal outcome; no tools or M006B presentation exist; all tests,
static checks, cross-version checks, wheel audit, and disposable-XDG walkthrough pass; and this plan
records the evidence and handoff.

## M006B handoff

After M006A is independently reviewed and committed, create `docs/plans/006b-simple-cli-chat.md`.
It will add only a thin `python -m jarvis.cli` presenter for default Jarvis and Core-resolved
`--profile-alias <alias>` interactive/one-shot use, streamed rendering, slash interception,
learning banner/commands, visible logging modes, cancellation, and reconnect/attach status. It
will not add a second Agent Engine, direct repository/provider access, tools, notes, memory, TUI,
desktop, physical aliases, or database-owned presentation state. Real local GGUF + llama-server
manual acceptance belongs to that later M006B plan.
