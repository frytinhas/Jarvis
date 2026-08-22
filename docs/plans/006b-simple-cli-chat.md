# Milestone 006B — Simple CLI Chat MVP ExecPlan

Status: COMPLETE
Last updated: 2026-08-21 America/Sao_Paulo

## Purpose and user outcome

M006B exposes the completed M006A Core chat pipeline through a thin, simple CLI presenter. Before
final installation, `python -m jarvis.cli` selects the permanent default `jarvis` profile, while
`python -m jarvis.cli --profile-alias <alias> [request]` resolves a logical profile alias through
Core. A request supplied as an argument is a non-TUI one-shot; no request opens the simple
interactive client. Users can see streamed responses, use the defined slash commands, observe
first-learning state, choose visible logging verbosity, cancel work, and reconnect or attach to
authoritative Core-owned work.

The CLI is a client and presenter only. Core remains authoritative for profile/model/session
identity, runtime lifecycle, chat state, learning state, diagnostics, limits, and all persistence.

## Scope

- Add the package-level `python -m jarvis.cli` invocation for the default profile.
- Add `--profile-alias <alias> [request]`, resolved by Core rather than by client-side repository
  access.
- Dispatch bare invocation to simple interactive mode and argument-bearing invocation to non-TUI
  one-shot mode.
- Render streamed client-neutral Core events in order, including terminal outcomes and bounded
  partial output.
- Intercept `/help`, `/quit`, `/exit`, `/clear`, `/model`, `/reasoning`, `/context`, `/status`,
  `/server`, `/config`, `/license`, `/logs`, and `/learning status|start|finish`.
- Keep slash commands out of LLM requests; each presenter action calls the corresponding
  client-neutral Core operation.
- Render the first-learning banner and learning status/transitions.
- Render the five profile logging modes: `full`, `server-essential`, `essential`,
  `essential-minimum`, and `none`.
- Ensure `none` still renders approvals, errors, and critical failures.
- Support client cancellation and authoritative disconnect/reconnect or attach status.
- Add tests for the development/package-level CLI contract and client-boundary invariants.
- Perform final manual acceptance with a real local GGUF and llama-server where available.

## Non-goals

- No second Agent Engine, provider, runtime manager, policy engine, or chat brain.
- No direct SQLite, repository, runtime-handle, provider-HTTP, or raw-log access from the CLI.
- No client-owned persistence or database migration.
- No tools, approvals for host capabilities, private-note generation, memory search, web access,
  rich TUI, desktop integration, voice, or physical profile commands.
- No final PATH installation, launcher/symlink management, executable collision handling, or
  dynamic physical alias lifecycle; those belong to M019A.
- No change to the model-content-neutrality contract or hidden provider-policy prompt layer.
- No new product decisions beyond the accepted M006B roadmap and handoff.

## Current progress

| Work item | Status |
|---|---|
| Accepted M006B scope and M006A handoff | DONE |
| CLI invocation and profile-alias dispatch | DONE |
| Interactive and one-shot presenter | DONE |
| Slash-command routing and Core operation calls | DONE |
| Streaming, visible-event, learning, and logging renderers | DONE |
| Cancellation and reconnect/attach behavior | DONE |
| Contract, isolation, and terminal-rendering tests | DONE |
| Real local GGUF/manual acceptance | DONE |
| Independent adversarial review fixes and full regression verification | DONE |

Progress log: 2026-08-21 America/Sao_Paulo — M006A handoff, roadmap, and ExecPlan requirements
were reviewed. This plan materializes only the already-accepted M006B simple CLI presentation
scope; no implementation or new product decision has been made.

Progress log: 2026-08-21 America/Sao_Paulo — implementation began on committed M006A HEAD
`a878d1f` on branch `new-jarvis`. The only pre-existing worktree item was this untracked ExecPlan.
The existing `jarvis.cli` package is the M003 configuration client and its `__main__` currently
owns `jarvis-config`; M006B must separate the package-module chat entry from that unchanged console
script contract. Existing Core IPC already exposes all required client-neutral profile, model,
configuration, runtime, chat, learning, diagnostic-summary, cancellation, resume, status, and
replay primitives. The shared IPC client needs only a presentation-neutral attach/replay iterator
so a resumed connection can receive future events without guessing or duplicating generation.

Progress log: 2026-08-21 America/Sao_Paulo — invocation, presentation, strict slash routing,
learning, five-mode rendering, cancellation, and same-request reconnect/attach are implemented.
Focused Ruff, strict mypy, and 57 CLI/IPC tests pass, including source-package subprocess coverage
for all four default/alias interactive/one-shot forms. Integration tests prove latest-session
continuity, `/clear` new-session behavior without history deletion, Core diagnostic persistence
under `none`, explicit cancellation, and disconnect/replay without a duplicate provider request.
Documentation now describes the M006B boundary. Full predecessor, wheel, cross-version, disposable
XDG, and real-local-provider readiness verification remains.

Progress log: 2026-08-21 America/Sao_Paulo — all automated and installed-wheel verification is
complete. CPython 3.12.13 and 3.14.4 each pass all 544 tests; 3.13 is unavailable. The exact marker
suites pass with unit 284, integration 140, migration 47, and security 73 tests. Ruff, format, and
strict mypy pass across 154 files. The clean wheel SHA-256 is
`15cfb56e0317d4f02fef3bf3f41a58f4302a89f87c10ee3062ccb0eb7da5ab1d`; it has zero base runtime
dependencies, the same four console scripts, no `jarvis` script, defaults 5/5, migrations
0001–0005, and no bytecode. A clean installed-wheel disposable-XDG walkthrough passed both
profiles in interactive and one-shot modes with two isolated sessions, two learning rows, six
closed diagnostics, and exactly two provider requests.

Progress log: 2026-08-21 America/Sao_Paulo — real-local-provider acceptance was attempted because
`/usr/bin/llama-server` version 8681 and three local chat GGUFs are available. Existing M004
discovery marks every chat GGUF `invalid` with reason `array_header`; both available embedding
GGUFs are also rejected with `array_budget`. Core therefore correctly refuses model selection and
the CLI reports `model.not_selected`. Fixing GGUF discovery is outside the user-mandated
presentation-only M006B scope, and bypassing Core/registry state would invalidate acceptance. This
is the sole completion blocker; no M006B presenter defect remains known.

Progress log: 2026-08-21 America/Sao_Paulo — the user explicitly authorized one narrow M004 GGUF
compatibility correction. The parser had reused a 64 KiB byte budget as an element-count limit and
as a per-array payload limit. Real valid metadata contains 30,522-element fixed arrays occupying
122,088 bytes and tokenizer arrays with 151,936–248,320 elements occupying up to 5,086,368 bytes;
each file's complete metadata remains below the existing 16 MiB aggregate ceiling. Parsing now
uses that aggregate metadata/header ceiling as the per-array byte ceiling and separately caps
cumulative array work at 1,000,000 elements. Descriptor-only read-only parsing, recursion, entry,
string, file-snapshot, truncation, and aggregate byte bounds remain enforced. Both original failure
classes reproduce before the fix and all three chat GGUFs plus the bundled Nomic GGUF now discover
as `available` without filename or model special cases.

Progress log: 2026-08-21 America/Sao_Paulo — post-fix verification passes 547 tests on CPython
3.12.13 and 547 on CPython 3.14.4; marker suites pass with unit 287, integration 140, migration 47,
and security 73. Focused parser/defaults/registry/runtime-security coverage passes 59 tests. Ruff,
format, and strict mypy pass across 154 files. Wheel
`2efc62cf3438ca584688ddc66299cd6326fa94cb61ad73d0addcd50a2b9005e5` installs with zero base
dependencies and the unchanged four scripts; its disposable two-profile walkthrough again passes.

Progress log: 2026-08-21 America/Sao_Paulo — real acceptance advanced through installed-wheel
discovery and Core-owned selection of an available chat GGUF, then exposed a distinct pre-existing
M005 health-compatibility defect. llama-server 8681 opens its authenticated loopback listener while
the 13.70 GiB Qwen3-Coder model is still loading and returns HTTP 503 with `Loading model` from
`/health`. `LlamaCppProvider.health()` classifies every non-200 health response as terminal
`health_invalid`; RuntimeManager consequently stops and retries the healthy-loading child and the
CLI ends with `runtime.start_failed`. The identical descriptor/API-key launch reaches `model
loaded` and a listening server when allowed to continue for about 90 seconds, proving this is not a
scanner, model, CLI, or resource-capacity failure. Correcting M005 health-state interpretation is
outside the user's M004-only authorization, so streamed real response acceptance remains blocked.

Progress log: 2026-08-21 America/Sao_Paulo — the user explicitly authorized the narrow M005
startup-health compatibility correction. llama.cpp's documented `/health` contract and live
llama-server 8681 behavior agree: HTTP starts before the model is loaded; the exact 503 JSON error
with code 503, message `Loading model`, and type `unavailable_error` means transient loading, while
200 `{"status":"ok"}` means ready. `LlamaCppProvider.health()` now returns bounded `STARTING` only
for that exact status/payload combination. Other statuses, malformed responses, unauthorized
responses, wrong payloads, process exits, ownership mismatches, and listener mismatches remain
fail-closed. RuntimeManager's existing startup deadline remains authoritative.

Progress log: 2026-08-21 America/Sao_Paulo — final verification passes 556 tests on both CPython
3.12.13 and 3.14.4; marker suites pass with unit 294, integration 142, migration 47, and security
73. Focused provider/runtime/security coverage passes 39 tests. Ruff, format, and strict mypy pass
across 154 files. Wheel `e7d286a7fb758dfab1bcdeeb2ad975c89aa9303d440815c794f3069375aef92a`
installs with zero base dependencies and the unchanged four scripts; the installed two-profile
walkthrough passes again.

Progress log: 2026-08-21 America/Sao_Paulo — installed-wheel real acceptance is complete in a
fresh mode-0700 disposable XDG environment. Discovery returned all three chat GGUFs `available`;
Core selected the 13.70 GiB Qwen3-Coder Q3_K_M model, auto-started `/usr/bin/llama-server`, remained
in STARTING for 23.31 seconds through transient health responses, recorded READY then BUSY then
READY, and `python -m jarvis.cli "Responda apenas com: olá"` streamed `Olá` and exited zero. The
session retained user/assistant history, learning started, and three closed diagnostics recorded
queued, generation-started, and completed outcomes. Core shutdown cleanly stopped the owned model
process.

Progress log: 2026-08-21 America/Sao_Paulo — independent adversarial review reopened completion
verification. Three in-scope defects reproduced before repair: EOF detached from Core correctly but
returned the Ctrl+C exit status 130; terminal escaping could expand a 256 KiB response into 1 MiB of
terminal output; and M005's Python dictionary equality classified a malformed loading payload with
`code: 503.0` as the documented transient integer `503` response. The CLI now treats EOF as a clean
detach while retaining Ctrl+C cancellation, bounds post-sanitization terminal bytes, and M005 uses
duplicate-key-rejecting JSON plus exact typed loading fields. Focused regressions pass; complete
M006B/predecessor/static/real-GGUF verification remains in progress.

Progress log: 2026-08-21 America/Sao_Paulo — the independent review found and repaired three
further in-scope defects. A one-shot Core terminal error rendered correctly but exited zero; valid
llama-server process evidence could be sampled before `execve` settled; and llama-server 8681 aborts
on the product's default `--batch-size 1` with its auto-selected four parallel slots. One-shots now
return nonzero on a terminal Core error, provider startup retries only exact process-evidence capture
for one bounded second, and the centrally defined new-profile runtime batch default is 2048 (the
server default). Regressions cover terminal exit status, delayed exact executable evidence, and the
structured default argument. The provider still rejects arbitrary health replies and only reaches
READY after owned-process/listener/authenticated health verification.

Progress log: 2026-08-21 America/Sao_Paulo — final adversarial verification passes `pytest -m
unit` (298), integration (143), migration (47), security (73), and the full 561-test suite on
CPython 3.12.13; the full 561-test suite also passes on CPython 3.14.4. `ruff check .`, `ruff format
--check .`, strict `mypy src tests`, and `git diff --check` pass. Fresh wheel
`25ccb2e6615b062c45096fc26a389bb3dd6b6156567355472b4a20e584b6d03c` builds and installs with no
broken requirements and exactly the four existing public scripts. In a mode-0700 disposable XDG
environment, M004 discovered the 13.70 GiB Qwen3-Coder GGUF as available; Core selected it,
llama-server reached owned READY through authenticated 503 loading health, and
`python -m jarvis.cli "Responda apenas com: olá"` streamed `olá`, exited zero, stored one completed
turn with two messages and three chat diagnostics, and shut down cleanly.

## Repository state and prerequisites

M006A is the prerequisite and supplies the client-neutral `chat-v1` IPC capability, streaming
events, session resolution, attach/status/replay, cancellation, learning operations, human-only
diagnostic summaries, visible logging configuration, bounded storage, and Core-owned persistence.
The client must consume those contracts through the existing IPC client boundary.

The implementation must preserve the repository's current user changes and inspect the actual
tree before editing. Tests use temporary XDG roots, disposable databases, fake providers/Core
services, and controlled terminal input/output. No real profile, home, model file, installation,
or user service may be modified by automated tests.

## Implementation sequence

1. **DONE — Invocation boundary.** Add the package/module entry for `python -m jarvis.cli`.
   Select `jarvis` when no alias is supplied; pass `--profile-alias` to the Core-resolved alias
   operation. Distinguish bare interactive invocation from argument-bearing one-shot invocation.
   Validate through subprocess/package-level dispatch tests. Do not create final PATH exposure.

2. **DONE — Presenter and stream rendering.** Implement the simple CLI presenter using the
   existing IPC client. Render response start, text deltas, completion, errors, cancellation, and
   reconnect/attach status without changing Core event ownership or ordering. Sanitize terminal
   control sequences and keep output bounded by Core contracts.

3. **DONE — Slash router.** Intercept the accepted slash commands before chat submission.
   Route each command to its client-neutral Core operation, including `/clear` as a new session
   request without deleting history and human-only `/logs` as a diagnostic-summary route. Unknown
   slash commands remain client errors and are never sent blindly to the model. Validate command
   parsing, help, exit, and session behavior.

4. **DONE — Learning and visible events.** Render the first-learning banner and
   `/learning status|start|finish`; map each of the five visible logging modes to its documented
   display policy. Preserve approvals, errors, and critical failures in `none`. Verify that
   diagnostic persistence remains Core-owned and independent of visible rendering.

5. **DONE — Cancellation and reconnect.** Wire client cancellation to the existing Core
   lifecycle and show authoritative status after disconnect/reconnect or attach. Do not infer
   terminal state from local presentation state or create a competing generation.

6. **DONE — Verification and manual acceptance.** Run focused tests, the predecessor
   regression suite, static checks, and the M006B integration matrix. Exercise two logical profile
   aliases, shared-model isolation, learning transitions, visible modes, cancellation,
   reconnect/attach, and real local GGUF/llama-server acceptance when the local prerequisites are
   available. Record evidence here before marking the milestone complete.

## Exact files and components affected

Expected production additions are limited to the simple CLI package/module and its presenter,
command-router, renderer, and client-boundary adapters, using the repository's existing package
layout. Expected test additions cover CLI dispatch, routing, rendering, isolation, and lifecycle
behavior.

No migration, database schema, model provider, Core persistence, physical launcher, or unrelated
client file is in scope unless the existing M006A IPC client contract requires the smallest
compatibility-only adjustment; any such discovery must be recorded before implementation.

Implemented production changes are `src/jarvis/cli/chat_application.py`, `commands.py`,
`rendering.py`, `presenter.py`, and `__main__.py`; the neutral attach iterator is in
`src/jarvis/ipc/client.py`; `pyproject.toml` retains the same four scripts but routes
`jarvis-config` to `config_main`. Tests are in the existing CLI unit files plus
`tests/integration/test_simple_cli_chat.py`, `test_simple_cli_subprocess.py`, and
`tests/security/test_simple_cli_boundary.py`. README and architecture/development/protocol docs
are updated. Database migrations, defaults, Core/server, providers, runtimes, and tools are
deliberately untouched by M006B. Under the explicit compatibility authorization, M004's GGUF
parser and packaged scanner-limit defaults gain corrected array limits and permanent regression
coverage. Under the subsequent explicit compatibility authorization, M005's provider recognizes
only llama-server's documented loading response as transient; no Core/server protocol changed.
Permanent provider and deadline regressions are in `tests/unit/test_provider_streaming.py` and
`tests/integration/test_runtime_manager.py`.

## Contracts and interfaces

- `python -m jarvis.cli` uses the default stable profile identity `jarvis`.
- `--profile-alias` is a logical alias input resolved by Core; aliases are never used as storage
  ownership keys and are not trusted to select a profile locally.
- Bare invocation is interactive; an argument-bearing invocation is a non-TUI one-shot.
- Chat submission, session resolution, attach/status, cancellation, learning operations, visible
  configuration, and human diagnostics use client-neutral IPC operations.
- Slash commands are parsed locally only for presentation control and then translated into typed
  Core operations; they are never blindly submitted as user chat text.
- Stream events are rendered in sequence and exactly one Core terminal outcome is displayed for an
  accepted request.
- Disconnect does not cancel Core-owned work. Reconnect/attach reports Core's authoritative active,
  partial, completed, failed, or cancelled state.
- Diagnostic events and human diagnostic summaries cannot be fed into a new chat request.
- The renderer is presentation-only: it cannot authorize host capabilities, access repositories,
  execute tools, or bypass Core policy and bounds.

## Database, migrations, and storage

M006B introduces no database tables, migrations, storage namespaces, or client-owned state. All
conversation, learning, diagnostic, quota, session, and turn persistence remains owned and
bounded by M006A Core under `(profile_id, model_id, session_id)` and associated correlation IDs.
The CLI must not write outside its normal transient terminal/client state, and it must not weaken
Core admission or diagnostic-reservation behavior.

## Security and privacy considerations

The CLI is untrusted presentation input. It must use typed IPC requests, preserve profile/model
isolation, avoid path or identifier reinterpretation, and never expose Core repositories, runtime
handles, secrets, raw logs, audit records, or provider transport. Terminal escape sequences and
unbounded output are sanitized/bounded. `/logs` is human-only and returns bounded summaries that
cannot enter Context Builder input. No network access, telemetry, sudo, host capability, or model
file mutation is added. The existing central redaction and Core policy boundaries remain
authoritative.

Abuse cases covered by tests include alias confusion, slash-command injection into the model,
cross-profile session access, terminal escape injection, diagnostic leakage, cancellation races,
disconnect/reconnect duplication, and a client attempting to bypass Core through direct imports.

## Tests

- Subprocess/package tests for default bare, default one-shot, logical-alias bare, and logical-alias
  one-shot dispatch.
- Tests proving the CLI has no direct repository, provider, runtime, database, or raw-log imports.
- Slash interception tests for every accepted command, `/clear` session semantics, learning
  commands, unknown commands, malformed arguments, and no accidental LLM submission.
- Streaming/order tests for deltas, completion, errors, cancellation, partial output, and exactly
  one terminal presentation.
- Reconnect/attach/status tests after disconnect, Core completion, failure, and cancellation.
- First-learning banner and learning-state transition tests.
- Tests for all five visible logging modes, including required errors/critical events under `none`.
- Language/persona presentation tests using Core/fake-provider fixtures.
- Terminal escape and bounded-output sanitization tests.
- Profile/model/session isolation and diagnostic non-context tests.
- Full predecessor regression, lint, type, formatting, and `git diff --check` verification.

## Manual verification

1. In a disposable XDG environment with Core available, run `python -m jarvis.cli` and confirm
   default-profile interactive mode.
2. Run `python -m jarvis.cli "request"` and confirm a streamed non-TUI one-shot with one terminal
   outcome.
3. Run both bare and one-shot invocations with two Core-resolved logical profile aliases; confirm
   isolated sessions and shared-model operation.
4. Observe the first-learning banner, inspect `/learning status`, and exercise `/learning start`
   and `/learning finish`.
5. Exercise every visible logging mode, including `none`, and confirm diagnostics remain persisted
   without appearing in model context.
6. Cancel an active request, disconnect and reconnect/attach, and confirm authoritative Core state
   and no duplicate generation.
7. Exercise `/help`, `/clear`, `/model`, `/reasoning`, `/context`, `/status`, `/server`, `/config`,
   `/license`, and human-only `/logs`; confirm slash commands are not sent to the model.
8. If a compatible local GGUF and llama-server are available, repeat the core chat path with the
   real local provider. Clean up only the disposable XDG environment and test processes.

## Discoveries

- HEAD `a878d1f` is the committed M006A completion on `new-jarvis`; `git status --short` initially
  reported only `?? docs/plans/006b-simple-cli-chat.md`.
- `src/jarvis/cli/__main__.py` is currently both the package module and the `jarvis-config` entry
  target. Preserving M003 while making `python -m jarvis.cli` chat requires a distinct
  `config_main` target and a one-line `pyproject.toml` entry-point adjustment; it does not create a
  physical `jarvis` command.
- `JarvisIpcClient` supports resume, status, replay, and cancellation, but has no iterator that
  registers a resumed request before replay and then consumes future events. Adding that neutral
  client method is the smallest compatibility adjustment needed to preserve disconnect !=
  cancellation for a real presenter; no Core/server contract or persistence change is required.
- Registering the resumed request queue after replay would lose a concurrently emitted live event;
  registering it before replay can receive an event present in both paths. The implemented attach
  iterator registers first and de-duplicates by monotonic Core sequence. The disconnect regression
  verifies one provider request, retained output, and one terminal presentation.
- Package subprocess verification requires preserving the M003 console-script behavior while
  changing module behavior. `jarvis-config` now targets `config_main`; the public script set is
  unchanged and no `jarvis` console script was added.
- The plan's exact broad pytest command initially exposed that `tests.support` depended on implicit
  namespace-package import ordering. Adding `tests/__init__.py` makes the repository-local support
  package deterministic; the exact marker and full-suite commands then pass without `PYTHONPATH`
  adjustment on the provisioned 3.12 environment.
- Real-host evidence: `/usr/bin/llama-server --version` reports 8681. Discovery reports
  `array_header` for all three `/home/gabri/.lmstudio/models/huggingface/*.gguf` chat models and
  `array_budget` for both bundled Nomic GGUFs. The failure precedes RuntimeManager/provider startup
  and is not caused by CLI dispatch or rendering.
- GGUF v3 encodes array length as an element count, not a byte count. The former scanner compared
  that count directly to a 64 KiB byte budget and also rejected valid fixed-array payloads above
  64 KiB. The real files establish the needed compatibility range while remaining below the
  existing 16 MiB total metadata-read ceiling.
- Once discovery was corrected, llama-server's real startup behavior revealed that its listener
  and `/health` route become reachable before model loading finishes. A 503 `Loading model`
  response is transient startup state, but the committed M005 provider treats every non-200
  response as terminal invalid health and stops the process.

## Architectural decisions

- **2026-08-21 — Accepted — Thin Core client.** M006B introduces only a simple CLI presenter and
  command router over existing Core/IPC contracts. This preserves Core authority, profile
  isolation, and the roadmap boundary. No new product decision is introduced by this plan.
- **2026-08-21 — Accepted — Development/package invocation only.** `python -m jarvis.cli` and
  logical `--profile-alias` dispatch are the M006B acceptance surface; physical commands and PATH
  lifecycle remain M019A-owned.

## Deviations from the original plan

The expected smallest compatibility-only adjustment was required: the shared, presentation-neutral
IPC client gained `attach()` to atomically bridge replay into future delivery. This changes no
Core/server protocol or persistence contract and is within the plan's explicit allowance. No scope
or product deviation occurred. Test-package initialization was also added so the prescribed pytest
commands resolve `tests.support` deterministically; it changes no product behavior.

After explicit user authorization, the smallest M004 predecessor compatibility correction was also
made to distinguish array element work from array bytes. After a second explicit authorization,
the smallest M005 predecessor compatibility correction was made to distinguish the exact documented
503 loading response from terminal invalid health. Neither fix bypasses validation or changes the
respective subsystem's ownership, authentication, isolation, or resource bounds.

The independent review added only M005 compatibility required by the same real-GGUF path: bounded
post-spawn evidence settling and the valid llama-server batch default. It also hardened M006B
presentation exit and terminal-output bounds. These changes add no tools, PATH behavior, database
schema, Core presentation state, or M007 capability.

## Unresolved issues

None. Physical command exposure remains planned work for M019A and the TUI remains deferred; these
are non-goals, not M006B blockers.

## Completion criteria and evidence

M006B is complete only when the development/package-level default and logical-alias interactive
and one-shot paths work through IPC/Core; streams, slash commands, learning, visible logging,
cancellation, and reconnect/attach are verified; no direct repository/provider access or client
persistence exists; isolation and terminal safety tests pass; predecessor regressions and static
checks pass; and the manual local-provider acceptance is recorded where prerequisites exist.

At completion, update this section with exact commands and results, mark every work item DONE,
record repository status, and leave no implementation-blocking unresolved issue.

Evidence complete: `pytest -m unit` (298), integration (143), migration (47), security (73), and
`pytest` (561) pass on CPython 3.12.13; the full 561 pass on CPython 3.14.4 with `PYTHONPATH`
pointing to the source tree because that interpreter has no installed project package. CPython 3.13
is unavailable. `ruff check .`, `ruff format --check .`, `mypy src tests`, fresh wheel install, and
`git diff --check` pass. The final installed wheel and real-GGUF walkthrough evidence is recorded in
the progress log. No completion blocker remains.

## Handoff summary

Current state: M006B implementation, adversarial regressions, automated matrix, documentation,
installed-wheel walkthrough, authorized bounded M004/M005 compatibility fixes, and real local GGUF
streamed acceptance are complete. M006B is ready for final commit. Do not begin M007 or add physical
aliases, tools, notes, memory, TUI, desktop, or database-owned presentation state.
