# Milestone 006C — User-local Installation and Core Activation Foundation

Status: COMPLETE
Last updated: 2026-08-21 America/Sao_Paulo

## 1. Purpose and user outcome

M006C establishes the first permanent production slice of Jarvis's user-local installation
architecture. The completed M006B simple chat MVP must be runnable from an ordinary shell as
`jarvis`, without a repository checkout, activated development environment, `python -m`, manual
`jarvisd` startup, `pipx`, root, or global Python mutation.

Bare `jarvis` initially opens the simple interactive CLI; `jarvis "request"` is a one-shot. The
logical `jarvis --profile-alias <alias>` path remains Core-resolved. An unconfigured profile enters
a typed Core-owned setup flow and, after readiness succeeds, continues into the original chat
request. First-run learning is activated only by the actual Agent Engine chat transaction, never by
installation, Core activation, discovery, setup, or runtime readiness validation.

## 2. Scope

- Root-free installation into `$XDG_DATA_HOME/jarvis-cli/installation/` with a Jarvis-managed
  private production virtual environment at `installation/venv/`.
- Collision-safe fixed dispatchers in `$HOME/.local/bin/` for `jarvis`, `jarvis-config`,
  `jarvis-help`, and `jarvis-manage`. The launchers execute the private environment and never the
  source tree or an activated development environment.
- No shell-RC or global PATH mutation. Installation reports the exact `$HOME/.local/bin` PATH
  action when it is absent. Preflight detects foreign fixed commands resolved through PATH and never
  overwrites or claims them.
- User-systemd socket/service assets under `$XDG_CONFIG_HOME/systemd/user/`, with systemd owning
  `%t/jarvis-cli/core.sock` and activating one foreground `jarvisd`.
- Explicit production socket-activation mode with inherited-listener validation/adoption; direct
  self-bound foreground mode remains available only for development and isolated tests.
- Deterministic client activation/readiness retry and typed activation failures.
- Minimal installation identity, manifest, protected-file identity, idempotent installation, and
  non-destructive repair foundation designed for M018A and M019A extension.
- Client-neutral `setup-v1` Core IPC orchestration reusing M004 model discovery/configuration and
  M005 runtime readiness services.
- Installed-wheel/fresh-user acceptance, ordinary-shell interactive and one-shot paths, help
  paths that do not connect or start inference, and logical alias continuity.

## 3. Non-goals

- M007+ behavior, tools, Policy Engine, Tool Broker, approvals, web, memory, private-note
  generation, and new host capabilities.
- Dynamic physical profile aliases or their collision, materialization, rename, delete, repair, or
  uninstall lifecycle; these remain M019A-owned.
- Per-profile `Start with computer` model autostart; M018B owns desired-state reconciliation over
  this single Core topology.
- TUI implementation or TUI-default dispatch; M016 changes only the existing bare dispatcher
  target after its stability gate.
- `jarvis-clear`, desktop assets not yet introduced, complete release packaging, final installer
  and uninstaller/purge, supported-distribution matrix, updater checks/application, signing,
  authenticity, rollback, or M019B updater authority.
- Root/system-wide installation, global/system Python mutation, `pipx`, source-tree runtime
  dependency, launcher background-spawned Core, second Core owner, or client-owned repositories/
  SQLite/runtime/model logic.

## 4. Current progress

### Summary

- DONE: repository and authority inspection; M000–M006B predecessor contracts verified.
- DONE: all implementation, documentation, security, installed-wheel, real-GGUF, and verification
  items.
- IN PROGRESS: none.
- NOT STARTED: none.

| Work item | Status |
|---|---|
| Installation layout, private venv, identity, and manifest design | DONE |
| Safe wheel bootstrap, idempotent install, and limited repair | DONE |
| Fixed dispatchers and collision-safe PATH behavior | DONE |
| systemd-user socket/service assets | DONE |
| Direct versus inherited Core listener modes | DONE |
| Inherited descriptor validation/adoption | DONE |
| Deterministic client activation/readiness | DONE |
| `setup-v1` Core orchestration and typed outcomes | DONE |
| CLI setup presentation and chat continuation | DONE |
| Documentation, installed-wheel acceptance, and full verification | DONE |

Progress log: 2026-08-21 America/Sao_Paulo — branch `new-jarvis`, HEAD `774353c`, clean worktree
before materialization. AGENTS.md, ROADMAP.md, PLANS.md, docs/architecture.md, the completed
006A/006B plans, packaging metadata, CLI presenters, Core ownership/startup, IPC client, XDG and
installation-protection primitives, M004/M005 services, logical alias resolution, and fixed
presenters were inspected. No implementation work has begun.

Progress log: 2026-08-21 America/Sao_Paulo — implementation started from branch `new-jarvis` at
HEAD `774353c`. The worktree contained only this untracked active ExecPlan. The authoritative
documents were re-read in full and the M006C roadmap boundary was verified. Sequence item 1 is now
in progress; all automated installation/service work will use disposable HOME/XDG/PATH roots.

Progress log: 2026-08-21 America/Sao_Paulo — implementation items 1–9 completed. Added the
private-venv local-wheel bootstrap, bounded manifest/identity verification, deterministic fixed
launchers, systemd-user units, direct/systemd listener modes, exact inherited-descriptor checks,
activation-aware hello readiness, setup-v1 Core orchestration, and the simple CLI setup presenter.
Focused M006C tests passed (19 tests); the complete suite passed at the interim checkpoint (569
tests). A controlled systemd-style listener test reported `activation=ready
duplicate_core=refused inherited_path=preserved`. A clean wheel installed and reverified in a
disposable root; missing-asset repair succeeded, altered assets and foreign PATH commands were
refused, fixed help ran outside the checkout, `pip check` passed, and installed active-installation
identity was complete. The compatible second local GGUF passed real llama-server readiness and chat
(`READY`, healthy, response `OK`); the first available Qwen3.8 GGUF was incompatible with the local
llama.cpp build and failed safely before chat.

## 5. Repository state and prerequisites

M006A supplies client-neutral `chat-v1`, streaming events, session resolution, attach/status/replay,
cancellation, learning lifecycle, human-only diagnostics, bounded storage, and Core-owned
persistence. M006B supplies `python -m jarvis.cli`, simple interactive/one-shot semantics,
`--profile-alias`, slash routing, rendering, and reconnect behavior. M004 supplies installation
runtime/model-directory configuration and GGUF registry/discovery. M005 supplies structured
llama-server configuration, provider validation, RuntimeManager ownership, readiness, and one
runtime per profile.

Current package metadata exposes `jarvisd`, `jarvis-config`, `jarvis-help`, and `jarvis-manage`; it
does not expose a physical `jarvis` command. Current Core self-binds `$XDG_RUNTIME_DIR/jarvis-cli/
core.sock` through `RuntimeOwnership`. Existing IPC clients connect directly to that path and must
gain only the activation-aware connection behavior required here. Existing XDG, manifest/identity,
protected-file, quota, redaction, database, profile, model, runtime, and diagnostic contracts remain
authoritative.

Implementation requires CPython 3.12+, the existing offline-capable build/test toolchain, a fake
provider, small GGUF fixtures, temporary HOME/PATH/XDG roots, controlled local listeners, and a
fake systemd-user controller. Automated tests must never mutate the real home, installation,
profiles, models, or user service manager.

## 6. Implementation sequence

1. **DONE — Installation layout and identity.** Add installation path resolution, private
   directory validation, immutable asset inventory, atomic manifest writes, and verification. The
   manifest records schema/version, installation UUID, distribution version, private interpreter
   identity, fixed dispatcher/unit paths, modes, hashes, and ownership identities. Validate with
   temporary XDG/home/PATH roots.
2. **DONE — Safe bootstrap/install and limited repair.** Add an explicit bootstrap accepting a
   local wheel. Create the private venv using the invoking Python, install the wheel offline with
   `--no-deps`, stage assets in the same directory, fsync and atomically publish the manifest.
   Matching manifest-owned assets are idempotent; missing assets may be restored; altered, foreign,
   linked, or colliding targets fail without overwrite. No uninstall, release packaging, signing,
   or updater behavior.
3. **DONE — Fixed command dispatch.** Add `jarvis.dispatch` and private-venv launchers for
   the four fixed commands. Preserve M006B bare-simple versus argument-bearing one-shot behavior
   and Core-resolved `--profile-alias`. Handle all help before Core connection or inference. Keep
   the dispatcher extensible so M016 changes only the bare interactive target.
4. **DONE — systemd user assets.** Add `jarvisd.socket` and `jarvisd.service` templates.
   The socket owns `%t/jarvis-cli/core.sock`; the service executes the private venv Core in the
   foreground with `--socket-activation`, bounded restart behavior, and no alternate daemon path.
   Install/repair reloads and enables the socket only after assets validate.
5. **DONE — Core listener modes.** Split `RuntimeOwnership` into self-bound and inherited
   modes. Both retain the atomic Core lock, metadata, peer/framing checks, and exactly-one-Core
   semantics. Direct mode alone may recover/bind/unlink `core.sock`; inherited mode never unlinks or
   rebinds the systemd-owned pathname.
6. **DONE — Inherited listener contract.** Require `LISTEN_PID == getpid()`, exactly one
   `LISTEN_FDS`, exact `LISTEN_FDNAMES=jarvis-core`, descriptor 3, Unix stream type, listening
   state, expected non-abstract address, current UID, mode 0600, safe runtime parent, and no extra
   descriptors. Reject all malformed/type/address/owner/access conflicts with typed failures.
7. **DONE — Deterministic client activation/readiness.** Centralize non-help IPC connection
   through bounded retry/backoff while socket activation starts Core. A successful `hello.ok` is
   IPC readiness. Report typed unavailable, timeout, protocol, and activation errors; never spawn
   Core locally or duplicate accepted work. Preserve M006B reconnect/attach semantics.
8. **DONE — First-run setup workflow.** Add negotiated `setup-v1` operations: `setup.start`,
   typed state/step snapshots, `setup.advance`, `setup.cancel`, and `setup.validate`. Core resolves
   the profile/alias, evaluates runtime path, model directories, discovery, selection, and essential
   settings; applies updates through M004, refreshes the registry, and validates readiness through
   M005 RuntimeManager. Opaque profile-bound session tokens are revision-checked and Core-local.
   Setup readiness starts no chat and does not initialize learning.
9. **DONE — CLI setup presentation.** Before chat, request readiness. Prompt only for missing
   runtime path, directories, model selection, and essential reasoning/context settings. Render
   typed failures and cancellation. On success resume the original interactive prompt or one-shot
   request through normal chat IPC. The client never scans, edits SQLite, or manages runtimes.
10. **DONE — Documentation and acceptance.** Update architecture, protocol, development,
    installation guidance, README, and this plan. Run the complete predecessor/regression,
    installed-wheel, fresh-user, socket, setup, security, lint, type, and manual acceptance matrix.

Each step is independently checkable. Rollback is by deleting only newly created disposable test
roots; production install failures retain existing manifest-owned assets and never remove unrelated
files. Any migration, manifest, or unit change must be staged and atomically committed before it is
advertised as installed.

## 7. Exact files and components affected

Expected additions include installation/bootstrap/manifest modules under `src/jarvis/`, the
`jarvis.dispatch` module, setup service/contracts, packaged assets under `packaging/systemd/`, and
focused unit/integration/security tests.

Expected modifications include `pyproject.toml`, `src/jarvis/core/__main__.py`,
`src/jarvis/core/runtime.py`, `src/jarvis/core/ownership.py`, IPC client/models/server, CLI chat
connection/setup presentation, installation-protection integration, package-data configuration, and
architecture/protocol/development/README documentation.

Deliberately untouched: completed M000–M006B ExecPlans, M004/M005 domain semantics except typed
reuse, tools/policy/web/memory/TUI, dynamic profile aliases, per-profile autostart, `jarvis-clear`,
updater/release packaging, final uninstall/purge, and root/system-wide installation.

## 8. Contracts and interfaces

`InstallationManifestV1` is authoritative for M006C-owned application files, fixed launchers, and
systemd assets. It contains a schema version, installation UUID, distribution version, private-venv
interpreter identity, managed asset paths/modes/hashes, and file ownership identities. It is
extensible for M018A/M019A and is not a profile-data store.

Production activation requires one user-systemd socket and one foreground Core service. The socket
is `%t/jarvis-cli/core.sock`, equivalent to `$XDG_RUNTIME_DIR/jarvis-cli/core.sock`, mode 0600 in a
0700 parent. Systemd owns its lifecycle. `jarvisd --socket-activation` validates the inherited
descriptor contract, adopts it, and never unlinks/rebinds it. `python -m jarvis.core` retains
self-bound foreground mode for development/tests and cannot silently fall back from a failed
production contract.

The client connector retries only activation/readiness connection failures with bounded backoff.
Protocol hello is the readiness boundary; model readiness is separate. Existing IPC version,
capability negotiation, sequencing, terminal-event, cancellation, disconnect, and replay contracts
remain unchanged.

`setup-v1` operations are client-neutral. `setup.start` returns an opaque session and typed state;
`setup.advance` accepts one validated step plus expected revisions; `setup.validate` invokes the
Core-owned RuntimeManager readiness check; `setup.cancel` records cancellation and ends the setup
session. States include ready, needs-runtime-path, needs-model-directory, needs-discovery,
needs-model-selection, needs-essential-settings, validating, cancelled, and failed. Errors include
invalid input, revision conflict, missing model, runtime validation failure, Core restart, and
cancellation. Configuration writes already committed by Core remain explicit and visible; no
partial success is reported as complete setup.

## 9. Database, migrations, and storage

M006C adds no profile/model/chat/memory tables and no client-owned persistence. Existing XDG
configuration, data, state, cache, runtime, SQLite, quotas, diagnostics, and `(profile_id,
model_id)` isolation remain unchanged.

Installation identity and manifest are installation-scoped state, separate from profile data and
ephemeral runtime artifacts. The manifest is a bounded, mode-0600, atomically replaced JSON record
under `$XDG_STATE_HOME/jarvis-cli/installation/`. Setup sessions are Core-memory-only and expire on
Core restart; they do not consume first-learning state. If implementation requires a schema change,
it must be a numbered migration with transactional upgrade, fresh-install, idempotency, and
rollback/recovery coverage; no such change is currently planned.

## 10. Security and privacy considerations

- No root, sudo, global/system Python mutation, pipx, telemetry, cloud inference, or network
  download is introduced.
- The private venv, package files, launchers, units, and manifest become protected active-installation
  assets. Foreign paths, symlinks, hardlinks, changed identities, races, and special files fail
  closed.
- All fixed-command destinations are preflighted. Existing unrelated commands are never overwritten,
  shadowed, claimed, or silently replaced. Repair restores only absent manifest-owned assets.
- systemd owns the production listener. Core validates inherited PID/fd/name/type/address/owner/
  permissions and rejects extra or malformed descriptors. Direct mode alone owns unlink/rebind.
- Exactly one Core lock owner controls one user's XDG state. Concurrent activation probes the live
  protocol owner and never kills or replaces an unrelated process.
- Setup input is untrusted presentation data. Core owns profile resolution, model discovery,
  configuration, runtime startup, quotas, diagnostics, and learning boundaries. Setup cannot bypass
  the Agent Engine or cause first-learning activation.
- No diagnostic, audit, raw log, secret, credential, or profile data is uploaded or exposed through
  installation/setup contracts.

Security tests must cover command/path collisions, hardlinks, symlink swaps, changed managed files,
manifest tampering, inherited-fd spoofing, wrong-user sockets, duplicate Core activation, protocol
malformation, setup revision/session confusion, and client attempts to import repositories/runtime
services.

## 11. Tests

- Installation path, permissions, manifest schema/hash/identity, atomic publication, interruption,
  idempotent reinstall, missing-asset repair, altered-asset refusal, collision, PATH shadowing,
  symlink, hardlink, and replacement-race tests.
- Private-venv/source-independence tests proving installed launchers work after checkout removal and
  do not mutate global Python or require an activated environment.
- Dispatcher tests for bare/one-shot/default alias, `--profile-alias`, fixed command routing,
  argument errors, all help forms, and no Core/model startup on help.
- Static unit-file tests for exact socket path, mode, service foreground command, dependency,
  restart policy, unit ownership, and no background-spawn pattern.
- Inherited-listener tests using temporary Unix sockets and controlled `LISTEN_PID`, `LISTEN_FDS`,
  and `LISTEN_FDNAMES`: valid adoption, wrong fd count/name/type/address/owner/mode/listening state,
  abstract path, descriptor 3 mismatch, and extra-fd rejection. Verify inherited shutdown leaves
  the pathname to systemd while direct shutdown removes only its own socket.
- Fake-systemd integration tests for daemon reload, enable/start order, activation, concurrent
  clients, one-Core locking, stale metadata, service restart, bounded client retry/readiness, and
  no real user-manager mutation.
- `setup-v1` tests for every missing prerequisite, refresh/discovery, model selection, essential
  config, invalid input, revision conflict, cancellation at each step, runtime failure, Core
  restart, successful readiness, and no learning activation until actual chat submission.
- Interactive and one-shot setup continuation tests, logical alias continuity, profile/model
  isolation, M006B reconnect/attach/cancellation regressions, and client-boundary import tests.
- Fresh installed-wheel acceptance in disposable HOME/XDG/PATH and controlled systemd fixtures,
  followed by predecessor marker suites, full pytest, Ruff, formatting, strict mypy, wheel archive
  inspection, `pip check`, and `git diff --check`.

## 12. Manual verification

1. Build a local wheel and create disposable HOME, XDG, PATH, installation, model, and user-service
   roots.
2. Seed a foreign fixed command; verify installation refuses without changing it. Remove it and
   install without root.
3. Remove checkout access and deactivate the development environment; confirm all fixed launchers
   invoke only the private venv.
4. Run `jarvis --help`, `jarvis --h`, `jarvis -h`, `jarvis-help`, and fixed-command help; verify no
   Core connection, model discovery, runtime, or inference starts.
5. Run bare `jarvis`, `jarvis "hello"`, and `jarvis --profile-alias <alias> "hello"`; confirm one
   systemd-owned listener, one foreground Core, deterministic readiness, and normal M006B output.
6. Start with no usable runtime/model configuration, complete setup, validate readiness, and verify
   the original interactive or one-shot request continues. Confirm learning activates only when the
   chat transaction is submitted.
7. Inspect manifest and repair validation; alter a managed launcher/unit and confirm repair refuses
   replacement rather than overwriting it.
8. Restart Core while retaining the socket unit; verify Core never unlinks/rebinds the listener and
   clients reconnect with authoritative existing IPC semantics.
9. Clean only disposable roots and record all results in this plan.

## 13. Discoveries

- Current package metadata has four public fixed scripts and no physical `jarvis` script; M006C must
  add the canonical dispatcher without changing the M006B module contract.
- Current Core self-binds and cleans `core.sock`; production inherited mode must be a separate
  ownership path so systemd remains the pathname owner.
- Existing `RuntimeOwnership`, XDG, installation identity, IPC client, M004 model registry, M005
  RuntimeManager, and M006B presenters provide the required seams; clients must not duplicate them.

Further discoveries, platform limitations, test findings, and any scope implications must be added
here before dependent implementation continues.

- Standard `venv` creation symlinked its Python executable. The permanent private environment now
  uses `venv --copies`, allowing the interpreter to have a stable regular-file identity without
  relying on a global interpreter symlink at runtime.
- A Unix listener descriptor's socket inode is not the filesystem socket-node inode. Binding the
  descriptor to the production pathname therefore uses its kernel-reported exact non-abstract
  `getsockname()` plus independently validated pathname owner/mode/type/link evidence; comparing
  those unrelated inode classes would reject every valid systemd listener.
- Initial bootstrap acceptance found that recursive directory creation could leave the shared
  `$XDG_DATA_HOME/jarvis-cli` and `$XDG_STATE_HOME/jarvis-cli` parents at mode 0755. Bootstrap now
  creates and validates those product roots explicitly at mode 0700 before installing beneath
  them. Permanent regression coverage verifies both modes.
- The first locally available Qwen3.8 GGUF was rejected by Debian llama.cpp b8681 because the file
  lacked an expected tensor. Jarvis surfaced a typed setup runtime-validation failure and cleaned
  up. A second local Qwen3-Coder GGUF loaded successfully and produced `OK`; no download or model
  mutation occurred.
- Independent adversarial review found that the initial manifest checked only the private
  interpreter inode and fixed launchers/units: in-place interpreter or installed wheel-code edits
  survived a same-wheel repair attempt. The manifest now hashes the private interpreter, pins the
  wheel `RECORD`, and verifies every hash-bearing wheel-owned file without importing code from the
  private environment. A permanent regression covers both tamper cases.
- Independent adversarial review found that validating a duplicate inherited listener but then
  retaining descriptor 3 left a descriptor-replacement window. Adoption now retains the validated
  close-on-exec duplicate itself, transitions it to nonblocking mode, and never relies on fd 3
  after validation. Regression coverage verifies the adopted descriptor is non-inheritable.
- Independent adversarial review found that Python 3.13+ asyncio removes a supplied Unix-socket
  pathname by default when its server closes. That violated systemd socket ownership after an
  otherwise clean Core shutdown. IPC server creation now explicitly disables asyncio pathname
  cleanup where the runtime supports that parameter; RuntimeOwnership remains the sole direct-mode
  cleanup owner. The controlled activation walkthrough now proves that the listener path remains.
- Independent adversarial review found that cancelled and completed setup-v1 tokens could be used
  again at their newest revision. Terminal sessions now reject all follow-up actions with typed
  outcomes, and setup session allocation is bounded at 128 entries. Regression coverage exercises
  cancellation and successful-validation replay.
- Independent adversarial review also reproduced an interrupted first install after private-venv
  publication but before manifest publication. A mode-0600, hash-bound transaction marker now
  permits only a matching wheel to resume after revalidating the isolated venv and exact staged
  launcher/unit contents; foreign, altered, linked, or extra installation-root objects still fail
  closed. A disposable interrupted-install walkthrough completed as `repaired`.

## 14. Architectural decisions

- **2026-08-21 — Accepted — Private installation root.** Use
  `$XDG_DATA_HOME/jarvis-cli/installation/` with `venv/` beneath it. This separates immutable
  application assets from profile/configuration state and is user-local without root.
- **2026-08-21 — Accepted — Fixed launcher location.** Use regular mode-0755 launchers in
  `$HOME/.local/bin/`, perform collision preflight, and do not edit shell startup files. This avoids
  claiming unrelated PATH entries while supporting ordinary-shell use where the standard user-local
  bin is already configured.
- **2026-08-21 — Accepted — Production socket topology.** systemd-user owns
  `%t/jarvis-cli/core.sock`; one socket unit activates one foreground Core service. Direct self-bound
  mode is retained only for development/tests.
- **2026-08-21 — Accepted — Inherited descriptor contract.** Require one named fd (`jarvis-core`),
  exact PID/count/type/listening/address/owner/access validation, and never unlink/rebind in adopted
  mode. This preserves systemd ownership and exactly-one-Core semantics.
- **2026-08-21 — Accepted — Setup ownership.** `setup-v1` is Core-owned and reuses M004/M005 typed
  services. The client presents steps and resumes the original request only after Core readiness.
- **2026-08-21 — Accepted — Manifest foundation.** M006C records bounded installation identity and
  managed asset hashes/identities and supports only safe idempotent restoration; complete health and
  repair are M018A, final packaging/alias/uninstall lifecycle is M019A, and authenticated updating
  is M019B.
- **2026-08-21 — Accepted — Future boundaries.** M016 may change the bare interactive target to
  TUI; M018B may reconcile per-profile autostart through this Core; M019A may add dynamic physical
  aliases and final packaging; M019B alone may apply authenticated updates.
- **2026-08-21 — Accepted — Private interpreter identity.** Create the managed venv with
  `--copies`. This retains standard-library venv isolation while making the recorded interpreter a
  private regular file whose inode can be checked; it introduces no global Python mutation.
- **2026-08-21 — Accepted — Inherited address binding.** Validate descriptor 3 by activation
  environment, Unix domain/type/listening state and exact `getsockname()`, then validate the
  expected socket node independently. Linux does not expose the pathname inode as the socket
  descriptor inode, so an inode equality test between them is not a valid ownership proof.

## 15. Deviations from the original plan

None. Implementation preserved the approved architecture and all later-milestone boundaries. The
M006B console-script expectation tests were updated only to recognize M006C's newly authorized
canonical `jarvis` entry, and its fake configuration client was updated to use the centralized
activation-ready connector. No completed ExecPlan, roadmap, or authority document was changed.

Review repairs strengthened the existing M006C manifest, inherited-listener, setup-token, and
interruption-recovery contracts without adding a new lifecycle authority, public command, model
behavior, network feature, or later-milestone capability.

## 16. Unresolved issues

None. All implementation choices required by the approved plan are settled. Any implementation
discovery that would alter installation scope, ownership, socket topology, setup ownership, or a
later milestone boundary must stop the dependent step and be recorded as a proposed deviation with
the required authority review.

## 17. Completion criteria and evidence

M006C is complete; all following are DONE:

- Root-free private-venv installation works independently of checkout and activated dev venv.
- Canonical `jarvis` plus fixed config/help/manage dispatchers are collision-safe and PATH-safe.
- Help paths do not connect to Core or start inference; bare/one-shot/alias paths retain M006B
  semantics.
- systemd-user owns the socket, activates one foreground Core, and inherited validation/adoption
  passes all rejection cases; direct mode remains development/test-only.
- Client activation/readiness is deterministic, bounded, typed, and preserves reconnect semantics.
- Manifest/identity/protected-file validation and idempotent safe repair foundation pass.
- `setup-v1` reuses M004/M005, handles typed cancellation/failure, validates readiness, and resumes
  the original chat without premature learning activation.
- Fresh installed-wheel and ordinary-shell acceptance passes in disposable environments.
- Predecessor/full tests, security tests, lint, format, mypy, wheel checks, documentation review,
  and `git diff --check` pass.

Evidence recorded on 2026-08-21 America/Sao_Paulo:

- `pytest -m unit`: 304 passed; `pytest -m integration`: 144 passed; `pytest -m migration`: 47
  passed; `pytest -m security`: 85 passed; complete `pytest`: 580 passed with four pre-existing
  Python multiprocessing fork deprecation warnings.
- `ruff check .`, `ruff format --check .`, and strict `mypy src tests` passed.
- Offline `uv build --wheel` produced a clean 100-file wheel with SHA-256
  `5b5379a589053888f51d4e95c29fd7b19a993be9236efeaaf5eb60bdf44ac20d`, exact fixed entry
  points, no bytecode/cache entries, and zero runtime dependencies. Installed private-venv
  `pip check` reported no broken requirements.
- Disposable bootstrap installed then verified idempotently; missing `jarvis-help` repair returned
  `repaired`; an altered service and a foreign PATH `jarvis` both failed without replacement.
- Fixed help and one-shot chat ran from `/` with `PYTHONPATH` absent using only the private wheel;
  the captured module path was under `installation/venv/.../site-packages`, and the fake-provider
  one-shot returned `installed-wheel-ok`.
- Controlled inherited activation reported `activation=ready duplicate_core=refused
  inherited_path=preserved`; the rejection matrix covered count/name/extra-fd/type/domain/listening/
  address/abstract/mode/UID failures.
- setup-v1 tests covered every prerequisite transition, selection/settings, readiness, revision,
  profile-token confusion, cancellation, and zero learning rows before chat. Real local
  llama-server/GGUF acceptance reached `READY`/healthy and returned `OK` after the first incompatible
  local GGUF failed safely.
- `git diff --check` passed at handoff; final `git status --short` is recorded in the final report.

## 18. Handoff summary

Current state: M006C is complete and ready for independent review. The worktree is intentionally
uncommitted. No M007, dynamic profile alias, TUI, autostart, `jarvis-clear`, updater, signing,
uninstall/purge, or final release-packaging work was started. Review should begin with the manifest/
bootstrap destination checks, inherited-listener validation, setup-v1 ownership boundary, and the
recorded disposable acceptance helpers. No blocker remains.
