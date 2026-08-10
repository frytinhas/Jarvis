# Jarvis-CLI Development Roadmap

## Status and authority

This roadmap decomposes the product specified by `AGENTS.md` into sequential, independently verifiable milestones. `AGENTS.md` remains authoritative. If this roadmap and `AGENTS.md` differ, implementation stops until the roadmap is corrected; a milestone may not reinterpret an invariant.

This document plans work only. Milestone 000 has not started. Before any milestone starts, its self-contained ExecPlan must be created and maintained as required by `PLANS.md`.

The roadmap excludes Jarvis Voice and the Jarvis Desktop App. Their compatibility requirement is preserved by keeping Jarvis Core behind a versioned local IPC protocol and keeping all client presentation outside Core.

## Dependency analysis

The principal dependency chains are:

1. XDG path ownership, versioned defaults, migrations, stable identifiers, redaction, and protected-installation detection underpin every persistent or security-sensitive subsystem.
2. Profiles precede model associations, runtime ownership, conversations, learning, permissions, appearance, and every `(profile_id, model_id)` namespace. Alias lifecycle depends on stable profile identity rather than display names.
3. The read-only GGUF registry precedes profile/model selection. Provider isolation and runtime locking precede chat. Core IPC precedes all real clients and lets later CLI, TUI, Voice, and Desktop clients share one brain.
4. The minimal chat path requires the Agent Engine, centralized Context Builder, conversation persistence, diagnostic logging, and visible first-run learning state together. Omitting learning from the first usable chat would violate the first-run rule.
5. The Policy Engine, Tool Broker, approval protocol, audit trail, typed tool contracts, bounds, and active-installation guard must exist before any host tool. Read-only tools come first; structured application launch follows; filesystem mutation follows that; shell and destructive process actions come last among local host tools.
6. Memory retrieval depends on accumulated conversations/private notes and a context budget. Web access depends on network policy and bounded downloads. Screen access depends on the same policy/broker path plus Wayland portals/adapters.
7. The TUI depends on stable streaming IPC and approval events, but not on desktop automation. Cleanup depends on all storage categories. Autostart depends on mature runtime recovery. Updating and distribution come last because they must preserve data and enforce the protected-installation boundary end to end.

Cross-cutting requirements apply from their first relevant milestone onward: no telemetry, no required cloud inference, English internals, localization-ready user text, user-local/XDG storage, typed errors, centralized defaults, bounded data, profile isolation, secret redaction, and GPL-compatible dependencies.

## Established product decisions

- **Profile cloning:** A new profile clones Jarvis’s current configurable state, including its selected model and that model’s applicable per-profile configuration such as reasoning level and context window. Conversations, private model notes, memories, learning history/state, chat logs, and diagnostic session history always start empty. An inherited model that is missing is reported as unavailable and is never silently replaced.
- **Interactive client dispatch:** Before the rich TUI is stable, bare `jarvis` and bare profile aliases open the simple interactive CLI. Once Milestone 016 establishes the TUI as stable, those bare commands open the TUI by default. One-shot commands remain non-TUI. The simple interactive CLI remains an independent fallback client; an explicit option such as `--simple` may expose it after the default changes.
- **Desktop input boundary:** SCREEN authorizes screen/context access only. The roadmap contains no unrestricted keyboard or mouse control. Any future input automation is a separate capability requiring its own explicit security and permission design.

## Remaining product/technical decision gates

These decisions do not block Milestone 000, but the named milestone must not silently select them:

- **Web search provider (Milestone 014):** choose the concrete backend, credential model, query-disclosure policy, and provider fallback behavior. The provider interface is fixed; no backend is selected now.
- **Release signing technology (Milestone 019):** choose the cryptographic authenticity technology and trusted-key/material lifecycle. The fixed requirement is authenticity rooted in trusted information already available to the installed Jarvis, in addition to integrity verification. A checksum distributed beside the artifact from the same source is insufficient by itself.

Until those gates are resolved, expose no concrete web-search backend and do not ship an updater whose trusted authenticity mechanism is unsettled.

## Milestone sequence

### Milestone 000 — Repository and security foundation

- **Objective:** Establish the smallest runnable project foundation: GPL-3.0 licensing, controlled dependency metadata, XDG path semantics, centralized/versioned defaults, typed error conventions, SQLite migration infrastructure, centralized redaction/diagnostic logging primitives, installation identity/protection primitives, and isolated test infrastructure.
- **Rationale for position:** Every later subsystem persists data, emits diagnostics, or evaluates paths. These rules must be fixed before feature state is created.
- **User-visible result:** No assistant yet; maintainers can initialize and inspect an empty user-local data environment without touching real user state in tests.
- **Exact scope:** Project/package metadata; license and essential developer documentation; XDG config/data/state/cache/runtime resolution and fallbacks; atomic initialization; schema-version and migration runner; versioned default registry; correlation identifiers; bounded structured diagnostic sink; central secret redactor; active-installation path identity and containment checks; fake clocks/filesystems/providers as needed for tests. No profiles beyond schema readiness.
- **Architectural components introduced:** Storage foundation, configuration-default registry, migration runner, logging/redaction foundation, installation-boundary service, common typed errors.
- **Important interfaces/contracts introduced:** `XdgPaths`; defaults version contract; migration transaction contract; sanitized structured-event envelope; installation identity and `is_protected_path` contract; clock/ID abstractions needed for deterministic tests.
- **Persistence/database implications:** Create the initial SQLite database and migration ledger only, with explicit XDG ownership and permissions. Separate persistent state from runtime artifacts. No production identity/history rows yet.
- **Security implications:** Fail closed on ambiguous protected-installation identity; redact centrally before persistence/rendering; never log secret environment values; prohibit unsafe path broadening; ensure tests use temporary XDG roots and databases.
- **Tests required:** XDG fallback/override tests; migration apply/rollback/idempotency tests; defaults version tests; redaction corpus tests; protected-path canonicalization, symlink, ancestor/descendant, and development-clone tests; file permission and test-isolation tests; no-network/no-telemetry checks appropriate to the foundation.
- **Dependencies:** Only `AGENTS.md`, this roadmap, `PLANS.md`, and its future ExecPlan.
- **Explicit out of scope:** Profiles, model discovery, IPC server, llama.cpp, chat, tools, TUI, installer/updater, and real user installation.
- **Manual verification:** Under temporary XDG environment variables, initialize twice, inspect path separation and database version, emit a synthetic event containing test secrets and confirm redaction, and verify active-installation paths are protected while a separate clone is not.
- **Definition of done:** Foundation contracts are documented and tested; initialization is deterministic and idempotent; no host capability or application feature exists; repository checks pass in isolated temporary state.

### Milestone 001 — Profile identity and configuration domain

- **Objective:** Implement persistent profile identity, the permanent `jarvis` profile, profile-scoped settings, `(profile_id, model_id)` namespace-ready ownership, and centralized resettable configuration schemas.
- **Rationale for position:** Profile identity is the primary isolation key and must precede models, sessions, permissions, and clients.
- **User-visible result:** A service-level profile catalog always contains Jarvis and can create, rename, inspect, and safely delete/reset non-default profiles.
- **Exact scope:** Stable internal profile IDs; display names; deterministic Unicode-to-ASCII command normalization; reserved-name/collision checks; creation by cloning current Jarvis configurable defaults, including the selected-model reference and its applicable per-profile model configuration when present; rename preserving identity; deletion protection; profile and section reset planning/confirmation APIs; profile-owned persona/context/appearance/waiting/goodbye/logging/autostart/permission/model-setting schemas. Conversations, private model notes, memories, learning history/state, chat logs, and diagnostic session history are explicitly excluded from cloning. Destructive operations remain service APIs for later UI wiring.
- **Architectural components introduced:** Profile service, profile repository, configuration service, defaults/reset service.
- **Important interfaces/contracts introduced:** Profile CRUD commands/results; normalized alias contract; clone allowlist that includes selected-model configuration but excludes all historical, learned, memory, note, chat-log, and diagnostic-session data; protected-profile invariant; reset preview and confirmation token contract; stable profile ID contract.
- **Persistence/database implications:** Add `profiles`, `profile_aliases`, profile settings, and reset metadata through migrations. Enforce uniqueness and the permanent Jarvis invariant at service/database boundaries where practical.
- **Security implications:** Prevent alias injection/path traversal; never use aliases as data ownership keys; transactional clone/rename/delete/reset; fail closed on partial destructive operations; do not allow model-originated configuration mutation.
- **Tests required:** All normalization cases; empty/reserved/conflicting names; Jarvis creation idempotency, rename/deletion protection; clone current configuration and selected-model configuration but none of the forbidden historical/learned categories; profile isolation; reset previews and scoped resets; transaction rollback.
- **Dependencies:** Milestone 000.
- **Explicit out of scope:** `jarvis-config` presentation, executable alias files, models, sessions, runtimes, and full-profile history deletion for categories not yet implemented.
- **Manual verification:** In temporary state, initialize Jarvis, create “João Trabalho,” confirm `joao-trabalho`, alter Jarvis defaults and selected-model configuration and clone again, verify the configuration was copied while all historical/learned categories are empty, rename/delete the secondary profile, and confirm Jarvis cannot be renamed or deleted.
- **Definition of done:** Profile invariants are enforced below the UI, all current profile settings have centrally versioned defaults/reset behavior, and isolation tests pass.

### Milestone 002 — Profile-first configuration client and command aliases

- **Objective:** Provide the initial client-side configuration workflow and safe user-level profile command registration.
- **Rationale for position:** It exposes and verifies profile semantics before models make profiles operational, while keeping alias mechanics tied to stable identity.
- **User-visible result:** `jarvis-config` always begins with profile selection or “Create new profile”; secondary normalized commands dispatch to the same client identity; help paths do not start a model.
- **Exact scope:** Minimal localization-ready CLI/config presentation; create/rename/delete/reset confirmations; common versus Advanced grouping; reset routes for every exposed section; safe generated launcher/symlink/equivalent registry; atomic alias replacement and cleanup; `jarvis`, `jarvis-config`, `jarvis-help`, `-h`, `--h`, and `--help` behavior in development execution.
- **Architectural components introduced:** Thin CLI client shell, configuration presenter, alias registrar, command identity resolver.
- **Important interfaces/contracts introduced:** Client-to-service commands for profiles/configuration; alias-to-stable-profile resolution; confirmation UX contract; help-without-Core/model contract.
- **Persistence/database implications:** Alias registration status is reconciled with `profile_aliases`; no profile history is introduced. Filesystem registrations are user-local and recoverable.
- **Security implications:** Generated commands contain no shell interpolation; collisions include protected executables; registration destinations are constrained; destructive profile actions show exact categories and require explicit confirmation.
- **Tests required:** Profile-first navigation; all help spellings; no model startup on help; safe alias generation/reconciliation; collision/race/rollback tests; localization boundary tests; destructive confirmation tests.
- **Dependencies:** Milestones 000–001.
- **Explicit out of scope:** Model selection, daemon IPC transport, chat, rich TUI, production installer, and complete settings screens whose backing feature does not yet exist.
- **Manual verification:** Create a profile through `jarvis-config`, invoke its alias and help, rename it and confirm old alias removal/new alias creation, then verify attempted Jarvis deletion is rejected.
- **Definition of done:** Profiles are fully manageable through the required profile-first flow, aliases are safe and share one client, and no invocation starts inference.

### Milestone 003 — Installation model registry and GGUF discovery

- **Objective:** Discover user-owned GGUF files from configured installation-level directories and associate stable model records/configuration with profiles.
- **Rationale for position:** Runtime startup needs trustworthy canonical model identity and validated per-profile settings.
- **User-visible result:** Users can configure model directories, refresh discovery, see metadata/size/missing state, and select a model per profile without Jarvis downloading or modifying it. Newly created profiles inherit Jarvis’s current selected model and its applicable configuration; a missing inherited model is shown as unavailable.
- **Exact scope:** Installation-level model directory configuration; bounded/safe recursive scan; canonical-path deduplication; lightweight GGUF metadata parsing when reasonable; cached stable fingerprint that avoids full-file startup hashing; missing-file tracking; profile-model associations; reasoning levels and context window; structured advanced runtime settings schemas; transactional cloning of Jarvis’s selected-model association and applicable per-profile model settings into a new profile without copying any model-private or historical state.
- **Architectural components introduced:** Model registry, GGUF scanner/metadata reader, profile-model configuration repository.
- **Important interfaces/contracts introduced:** `ModelRecord`, stable `model_id`, scan request/result, missing-state contract, `ModelRuntimeConfig`, conceptual reasoning mapping input, structured argument validation.
- **Persistence/database implications:** Add `models`, model search directories, `profile_models`, scan metadata/fingerprint, and selected/last-valid model fields. Model files remain outside Jarvis storage.
- **Security implications:** Scanner is read-only; canonicalize and bound traversal; handle symlink loops/races; never execute/rename/move models; advanced arguments are structured and cannot become shell fragments.
- **Tests required:** Discovery, recursion policy, duplicates/symlinks, malformed/minimal fake GGUF, missing files, stable IDs/cache invalidation, same model across profiles, profile-specific settings, selected-model/settings inheritance, empty history/notes/memory/learning/chat-log/diagnostic-session namespaces after cloning, unavailable inherited model with no fallback, oversized metadata bounds, no model mutation.
- **Dependencies:** Milestones 000–002.
- **Explicit out of scope:** Model downloads, llama-server process management, chat, arbitrary runtime arguments, and automatic replacement of a missing model.
- **Manual verification:** Scan a temporary directory containing small fixtures, configure Jarvis’s selected model/reasoning/context, create a profile and verify those settings are inherited with empty private/history state, remove the inherited model and confirm it is unavailable without substitution, then configure different reasoning/context values for two profiles sharing one model.
- **Definition of done:** Registry operations are deterministic/read-only, stable IDs and per-profile settings persist, new-profile selected-model inheritance is exact and history-free, and missing models fail descriptively without substitution.

### Milestone 004 — Jarvis Core and versioned local IPC

- **Objective:** Establish `jarvisd` as the sole Core process boundary and a versioned, streaming-capable Unix-domain-socket protocol used by thin clients.
- **Rationale for position:** Runtime, agent, approvals, CLI, and future clients need one transport and ownership boundary before feature-specific messages proliferate.
- **User-visible result:** A development CLI can connect, query status/profile/model catalogs, receive structured events, cancel a harmless request, and report protocol errors clearly.
- **Exact scope:** Core lifecycle; Unix socket ownership/permissions; framing and safe serialization (never pickle); protocol negotiation/versioning; request/correlation IDs; streaming event envelope; cancellation semantics foundation; stale socket recovery; thin client transport; Core status APIs.
- **Architectural components introduced:** Jarvis Core host, IPC server/client, protocol schema, request router, event stream, cancellation coordinator.
- **Important interfaces/contracts introduced:** Request/response/error envelopes; `response_started`, `text_delta`, tool/approval placeholder event schemas, `response_completed`, and `error`; compatibility policy; client disconnect semantics.
- **Persistence/database implications:** Runtime socket stays in XDG runtime storage; lifecycle/runtime events use sanitized logs; no chat rows yet.
- **Security implications:** User-only socket permissions; peer/local-user validation where supported; bounded frames; schema validation; no arbitrary object deserialization; clients cannot call internal repositories directly.
- **Tests required:** Serialization/framing fuzz cases; version negotiation; user-only socket permissions; malformed/oversized messages; streaming order; cancellation/disconnect; stale socket recovery; typed IPC errors.
- **Dependencies:** Milestones 000–003.
- **Explicit out of scope:** llama.cpp startup, chat generation, approvals execution, TUI, systemd service installation.
- **Manual verification:** Start Core in a temporary runtime directory, query it from two clients, observe ordered event/correlation IDs, test incompatible protocol and cancellation, stop Core, and verify socket cleanup.
- **Definition of done:** All client access crosses the documented local protocol, Core owns services, and transport robustness/security tests pass.

### Milestone 005 — LLM provider and per-profile runtime manager

- **Objective:** Run local `llama-server` behind an implementation-neutral provider and enforce one active runtime per profile.
- **Rationale for position:** Chat must not own processes directly; runtime locking, health, timeouts, and isolation must be reliable first.
- **User-visible result:** A selected local GGUF can be started, health-checked, stopped, and switched; two profiles may run the same GGUF independently.
- **Exact scope:** Provider protocol; `LlamaCppProvider`; structured argv/process environment; localhost binding; explicit runtime states; per-profile port allocation; PID/runtime ID/lock/socket/health evidence; stale artifact recovery; startup/health/shutdown timeouts; sanitized server log capture; fake provider.
- **Architectural components introduced:** LLM provider abstraction, llama.cpp adapter, runtime manager, runtime lock registry, health monitor.
- **Important interfaces/contracts introduced:** Provider start/stop/health/chat primitives; `RuntimeHandle`, `RuntimeHealth`, state/event model; per-profile exclusivity and model-switch transition contract.
- **Persistence/database implications:** Add runtime events and last-valid runtime/model metadata; ephemeral locks/PIDs belong in XDG runtime, not persistent configuration.
- **Security implications:** No shell concatenation; no externally exposed listener by default; no inherited secret environment without allowlisting; models get no host tools/network authority; server output passes redaction.
- **Tests required:** State transitions, double-start race, stale locks, timeout/failure cleanup, model switch, same GGUF in multiple profiles, port collision, fake provider, structured argv, server log redaction.
- **Dependencies:** Milestones 000, 003, and 004.
- **Explicit out of scope:** Agent prompts, conversation UI/history, tool calling, autostart/systemd installation.
- **Manual verification:** With a configured compatible local runtime, start/health/stop one profile and concurrently start the same model for another; force a failed startup and stale lock, then verify recovery and diagnostics.
- **Definition of done:** Exactly one healthy runtime can exist per profile, cross-profile use remains isolated, failures leave recoverable state, and no llama.cpp detail leaks outside provider contracts.

### Milestone 006 — Architecturally correct local chat MVP

- **Objective:** Deliver one-shot and interactive local chat through Core with centralized context construction, persisted conversations, complete diagnostic logs, streaming, slash-command routing, and mandatory first-run learning visibility.
- **Rationale for position:** This is the earliest useful product slice; it follows identity, registry, IPC, runtime, logging, and storage foundations so it does not create architectural debt.
- **User-visible result:** Bare `jarvis` and bare profile aliases open the simple interactive CLI, while requests with a natural-language argument run as non-TUI one-shot commands. Both forms chat with the selected local model, stream responses where applicable, match user language by default, retain isolated sessions, and clearly show first-run learning mode.
- **Exact scope:** Agent Engine for text-only chat; basic centralized Context Builder (core instructions, persona, profile context, recent conversation, request); session/message persistence; context-window budgeting; CLI interactive/one-shot modes; `/help`, `/quit`, `/exit`, `/clear`, `/model`, `/reasoning`, `/context`, `/status`, `/server`, `/config`, `/license`; learning state initialization plus `/learning status|start|finish`; diagnostic chat logs always persisted; five visible logging modes; cancellation of generation.
- **Architectural components introduced:** Agent Engine, Context Builder, conversation service, command router, streaming CLI renderer, learning-state lifecycle minimum.
- **Important interfaces/contracts introduced:** Invocation-mode dispatch distinguishing bare interactive CLI from argument-bearing one-shot execution; `ChatRequest`/streamed response; session/turn IDs; context contribution/budget contract; slash commands never sent blindly to the LLM; profile/persona ownership; diagnostic-versus-visible-event separation.
- **Persistence/database implications:** Add sessions, messages, learning state, runtime/chat diagnostic records, and storage accounting. Keys include profile and model; session messages are transactionally finalized/cancelled.
- **Security implications:** Model input excludes raw diagnostic/audit logs; prompt contributions are bounded; server/network remains localhost-only; cancellation records outcome; visible mode `none` still shows critical errors; secrets stay redacted.
- **Tests required:** Bare `jarvis`/profile-alias simple interactive dispatch and argument-bearing non-TUI one-shot dispatch via fake provider; streaming/cancellation; context ordering/budget; profile/model/session isolation; first-run learning state per pair; language/persona placement; slash command interception; all logging modes; diagnostic persistence even in `none`; logs never enter context.
- **Dependencies:** Milestones 000–005.
- **Explicit out of scope:** Tool calls, private-note generation/retrieval, long-term memory, conversation search UI, web, TUI, desktop.
- **Manual verification:** Chat in two profiles using the same model, inspect first-run learning banner and status transitions, restart sessions to confirm history isolation, switch visible logging modes, cancel generation, and verify diagnostics exist but never appear in a captured prompt.
- **Definition of done:** A useful local chat MVP works end to end through IPC/Core, obeys all first-run/isolation/logging invariants, and has no host capability path.

### Milestone 007 — Learning sessions and model-private notes

- **Objective:** Complete inspectable, erasable per-profile/model learning and private-note behavior without confusing notes with diagnostics.
- **Rationale for position:** Chat now supplies user interactions; learning can safely produce durable model-private state before broader memory retrieval exists.
- **User-visible result:** Users can see, start, finish, inspect, and reset learning and private notes for the active profile/model.
- **Exact scope:** Learning prompts/UX; explicit `/learning reset` preview and confirmation; private-note CRUD via Core commands; bounded note generation/update policy; `/notes`; configuration/reset integration; storage quotas; clear provenance and local-only behavior.
- **Architectural components introduced:** Learning service, private-notes repository/service, learning-aware context contribution.
- **Important interfaces/contracts introduced:** `(profile_id, model_id)` note and learning keys; note provenance/size contract; inspect/reset operations; diagnostic-log exclusion contract.
- **Persistence/database implications:** Add private notes and learning history/state migrations with quotas and FTS readiness; cloning remains empty; profile reset removes owned data transactionally.
- **Security implications:** Notes cannot change permissions or Core instructions; no cross-model/profile access; logs cannot be summarized into notes; all destructive resets require exact previews/confirmation.
- **Tests required:** First-use/new-model/new-profile cases; restart/finish/status/reset; note isolation/limits/inspection; clone/reset behavior; prompt precedence; log-to-note noninterference.
- **Dependencies:** Milestone 006.
- **Explicit out of scope:** Semantic/episodic memory, automatic embeddings, OS tools, web.
- **Manual verification:** Create notes during learning, finish/restart without deletion, reset with confirmation, switch profile/model and confirm absence, and inspect captured contexts for only relevant bounded notes.
- **Definition of done:** Learning and notes meet lifecycle, locality, inspectability, reset, limit, and isolation requirements.

### Milestone 008 — Policy Engine, Tool Broker, approvals, and audit foundation

- **Objective:** Build the complete authorization/execution boundary before registering any real host capability.
- **Rationale for position:** AGENTS.md forbids OS access outside the broker and requires centralized allow/ask/deny decisions; tools cannot safely precede this gate.
- **User-visible result:** A synthetic non-host tool can demonstrate allowed, denied, and human-approved calls with clear streamed status and durable audit evidence.
- **Exact scope:** Typed tool definitions and registry; strict argument/result validation; capability categories/defaults; centralized Policy Engine; matching overrides; approval request/allow-once/always-allow/deny flows; permanent-change explicit intent; broker execution lifecycle, bounds, cancellation and timeouts; immutable active-installation rule; sudo denial; audit and tool-call records; client approval events.
- **Architectural components introduced:** Policy Engine, Tool Broker, approval service, audit service, tool registry, execution context.
- **Important interfaces/contracts introduced:** Tool descriptor, validated invocation/result/error; policy query/decision/reason; approval scope; `tool_call_*` events; capability-to-permission mapping; mandatory broker-only invocation contract.
- **Persistence/database implications:** Add permissions/overrides, approvals, tool calls, and audit events keyed by correlation/profile/model/session/turn; centralized retention/accounting.
- **Security implications:** Model cannot register tools, mutate permissions, forge approvals, bypass `ask`, access sudo, or target the active installation; policy re-checks validated canonical targets immediately before execution; audit is sanitized and non-model-readable.
- **Tests required:** Default decisions; override precedence; forged/stale/replayed approvals; always-allow intent; broker bypass attempts; installation path/symlink/TOCTOU cases; sudo denial; timeouts/cancellation; schema injection; audit completeness/redaction; model log/audit isolation.
- **Dependencies:** Milestones 000, 004, and 006.
- **Explicit out of scope:** Real filesystem, application, shell, web, desktop, or process tools.
- **Manual verification:** Exercise a synthetic tool through allow/ask/deny, approve once and persist a matching rule, try forged approval and protected-path/sudo requests, and inspect sanitized audit correlation.
- **Definition of done:** No callable host tool exists, but every authorization, approval, execution, event, and audit security contract is proven with synthetic adapters.

### Milestone 009 — Safe read-only filesystem and system inspection tools

- **Objective:** Introduce the first real capabilities: bounded structured READ tools for allowed user locations and non-mutating system/process inspection.
- **Rationale for position:** Read-only operations provide useful tool integration with lower risk and validate the broker before execution/mutation.
- **User-visible result:** Jarvis can list/search/read bounded files and inspect ordinary system/process information, with understandable progress and typed failures.
- **Exact scope:** `filesystem.list`, metadata, bounded read by chunk/offset/lines, glob/content search; current/home/Documents/Downloads/Desktop and user-configured roots; safe system information and process listing; metadata-first behavior; tool-result context budgeting.
- **Architectural components introduced:** Filesystem read adapter, path-scope validator, system/process read adapters.
- **Important interfaces/contracts introduced:** Canonical target descriptor; read bounds; structured file/process/system results; typed `InvalidPath`, `FileTooLarge`, and limit errors.
- **Persistence/database implications:** Tool calls/audit/storage usage only; no user-file mutation. Bounded excerpts may appear in sanitized diagnostics according to policy.
- **Security implications:** Reject device files and unsafe/surprising targets as designed; resist traversal/symlink races; enforce per-file/context/storage bounds; READ never implies execution or mutation; protected installation remains readable only if policy explicitly permits but never writable.
- **Tests required:** Every read operation; boundaries/offsets/line ranges; binary/huge/sparse/special files; path traversal/symlink races; configured roots; permission deny/ask overrides; bounded model context; no mutation.
- **Dependencies:** Milestone 008.
- **Explicit out of scope:** Create/copy/edit/move/delete, app launch, shell, process termination, network, screen.
- **Manual verification:** Ask Jarvis to inspect a temporary directory and fixture, paginate a large file, search content, deny a read via profile policy, and confirm files and metadata remain unchanged.
- **Definition of done:** All supported inspection is structured, bounded, brokered, policy-authorized, audited, and demonstrably non-mutating.

### Milestone 010 — Application discovery and structured launch

- **Objective:** Safely discover installed applications by friendly name and launch them through structured desktop mechanisms.
- **Rationale for position:** Application launch exercises EXECUTE with a constrained target before general scripts or shell are available.
- **User-visible result:** Requests such as “open Spotify” resolve `.desktop` metadata with confidence handling and launch through the preferred structured mechanism.
- **Exact scope:** Desktop-entry discovery/parser/cache; exact/case/accent-insensitive/alias/fuzzy resolution; ambiguity UX; launch priority (desktop entry, XDG, D-Bus, official CLI); structured argv; launch status; profile policy integration.
- **Architectural components introduced:** Application registry/resolver and launch adapter.
- **Important interfaces/contracts introduced:** App identity/match confidence; ambiguous-match result; safe desktop-entry execution field parsing; structured launch request/result.
- **Persistence/database implications:** User-local app cache and audit records with deterministic invalidation; no application data mutation by Jarvis.
- **Security implications:** Never evaluate arbitrary desktop-entry shell syntax unsafely; validate executable/arguments; EXECUTE policy applies; no sudo; visual clicking is excluded.
- **Tests required:** Matching variants/misspellings/ambiguity; malicious desktop entries; launch priority/fallback; structured args; deny/ask/allow; timeout/audit; no shell injection.
- **Dependencies:** Milestones 008–009.
- **Explicit out of scope:** Arbitrary binaries/scripts, shell commands, visual automation, input control, process termination.
- **Manual verification:** Discover known desktop fixtures, resolve exact/fuzzy/ambiguous names, launch a harmless test application through an approved mechanism, and verify deny/approval paths.
- **Definition of done:** Application discovery and launch are useful, structured, policy-controlled, and cannot become arbitrary shell execution.

### Milestone 011 — Guarded filesystem mutation

- **Objective:** Add structured CREATE, COPY, MODIFY, MOVE, and DELETE filesystem capabilities with precise permission composition and deterministic limits.
- **Rationale for position:** Mutation follows a proven broker/path layer and approval UX; it precedes less constrained shell execution.
- **User-visible result:** Jarvis can create and manage user files/directories, while modifications/moves/deletions default to explicit approval and overwrites never masquerade as CREATE/COPY.
- **Exact scope:** Create file/directory, copy, bounded edit/append/replace, move/rename, delete file, delete empty directory; existence-aware permission composition; atomic writes where feasible; conflict modes; exact target previews; storage quotas. Recursive destructive deletion remains deferred.
- **Architectural components introduced:** Filesystem mutation adapter, atomic-write/conflict service, destructive-action preview.
- **Important interfaces/contracts introduced:** Expected precondition/version metadata; overwrite requires MODIFY; copy overwrite requires COPY+MODIFY; move/delete target contract; structured mutation outcome and partial-failure reporting.
- **Persistence/database implications:** Audit before/after metadata and storage accounting; never store unnecessary full content; active writes are protected from quota pruning.
- **Security implications:** Revalidate canonical targets at execution; active installation is unmodifiable; symlink/hardlink and TOCTOU defenses; default ASK for MODIFY/MOVE/DELETE; explicit stronger handling for destructive scope; no silent overwrite.
- **Tests required:** Permission composition invariants from AGENTS.md; create-existing rejection; atomicity; concurrent changes; symlink/path races; size/storage limits; partial copy/move; delete confirmation; protected installation/development clone; audit/redaction.
- **Dependencies:** Milestones 008–009.
- **Explicit out of scope:** Recursive directory deletion, arbitrary shell/scripts, process termination, network downloads.
- **Manual verification:** In a temporary allowed tree, create/copy/edit/move/delete fixtures, verify each ASK prompt and overwrite composition, exceed a limit, try a protected-installation path, and confirm precise outcomes.
- **Definition of done:** Mutations are structured, bounded, transactional where possible, correctly permissioned, recoverable where practical, and pass all specified security-sensitive tests.

### Milestone 012 — Explicit execution and destructive process operations

- **Objective:** Add the most constrained supported shell fallback: explicit scripts/executables and guarded process termination, never unrestricted model shell access.
- **Rationale for position:** These high-risk capabilities require mature policy, broker, approvals, validation, logging, and cancellation behavior.
- **User-visible result:** Jarvis can run a specifically identified `.sh` or executable with structured arguments and can terminate an identified process only through clear authorization.
- **Exact scope:** Executable/script validation; argv arrays; controlled cwd/environment; separate execution timeout/output bounds; process identity and termination preview; partial/destructive cancellation recording; application-binary compatibility. `shell=True` is prohibited absent a future separately approved design.
- **Architectural components introduced:** Execution adapter, output limiter, process-action adapter.
- **Important interfaces/contracts introduced:** Explicit executable identity, argv/cwd/environment allowlist, process identity freshness, bounded stdout/stderr result, termination consequence/confirmation contract.
- **Persistence/database implications:** Sanitized bounded execution metadata/results and audit records; no credential-bearing environment persistence.
- **Security implications:** EXECUTE does not grant sudo; deny elevation/password capture; prevent command-string injection, PATH substitution, environment secret leakage, protected-installation modification, and model self-permission changes.
- **Tests required:** Arg injection; executable replacement race; unsafe cwd/env; output/timeout limits; sudo/elevation attempts; allow/ask/deny; process PID reuse; termination confirmation; cancellation/partial completion; audit redaction.
- **Dependencies:** Milestones 008, 010, and 011.
- **Explicit out of scope:** General interactive shell, arbitrary command strings, sudo flow, recursive deletion, desktop input automation.
- **Manual verification:** Execute a harmless fixture with spaced arguments, exercise timeout/output caps, reject sudo and command strings, terminate a disposable test process through approval, and inspect the audit trail.
- **Definition of done:** Supported execution is explicit and bounded; no unrestricted shell authority exists; destructive outcomes remain clear and auditable.

### Milestone 013 — Searchable history and selective local memory

- **Objective:** Implement conversation search, episodic and semantic memory, private-note retrieval, and context-budget-aware selective recall entirely locally.
- **Rationale for position:** Enough isolated conversation/learning data now exists, and the centralized Context Builder can govern retrieval safely.
- **User-visible result:** `/history` and `/memory` inspect/search relevant past information, while chat recalls selectively rather than injecting all stored data.
- **Exact scope:** SQLite FTS5 for conversations/notes/memories; history filters by text/date/model/profile/session; episodic summaries; durable semantic facts/preferences; provenance/inspection/edit/delete/reset; local retrieval ranking; context contribution budgets; optional local embeddings only if justified by its ExecPlan.
- **Architectural components introduced:** Memory service, retrieval/indexing service, episode/semantic repositories, Context Builder retrieval stage.
- **Important interfaces/contracts introduced:** Memory type/provenance/ownership; retrieval query/result/budget; profile versus profile-model scope; inspectability and deletion contract; logs are non-indexable model input.
- **Persistence/database implications:** Add memories and FTS tables/triggers/migrations; storage/retention accounting and deterministic pruning; rebuildable indexes.
- **Security implications:** Strict scope filters precede ranking; no external embeddings; diagnostic/audit logs never enter indexes or summaries; memories cannot override system/policy instructions; deletions are confirmed.
- **Tests required:** FTS/filter/search; profile/model/session isolation; selective/budgeted injection; provenance; reset/pruning/index rebuild; malicious memory precedence; explicit proof logs are excluded.
- **Dependencies:** Milestones 006–007; tool milestones are not required.
- **Explicit out of scope:** Cloud/vector services, web-derived hidden memories, automatic ingestion of private files, diagnostic-log retrieval.
- **Manual verification:** Create distinct facts in two profiles/models/sessions, search with filters, observe relevant bounded recall, delete/reset an item, rebuild the index, and verify diagnostics never appear.
- **Definition of done:** History and memory are local, searchable, selective, inspectable, erasable, isolated, budgeted, and separate from logs.

### Milestone 014 — Explicit web access and bounded downloads

- **Objective:** Provide network access only through policy-controlled `web.search`, `web.fetch`, and `web.download` tools, with web search isolated behind a provider interface.
- **Rationale for position:** Network access needs the broker, INTERNET policy, storage limits, safe filesystem creation/mutation semantics, and auditable context handling.
- **User-visible result:** Authorized requests can search/fetch the web and download bounded files; denied profiles remain offline and no private context is silently uploaded.
- **Exact scope:** Network client boundary; transparent request metadata; provider-neutral web-search contract and the concrete provider selected through the Milestone 014 decision gate; fetch content-type/size/time/redirect controls; download destination/preflight; DNS/address and scheme policies; per-profile/per-model timeouts/limits; explicit error handling and caching. Provider selection must not alter the Agent Engine or Tool Broker contracts.
- **Architectural components introduced:** Network policy adapter, web tools, search provider interface, bounded downloader/cache.
- **Important interfaces/contracts introduced:** Web-search provider interface and normalized provider result; network request purpose, URL normalization, redirect policy, response/download bounds, `NetworkDenied`, external-data provenance, explicit outbound payload contract.
- **Persistence/database implications:** Cache and downloaded temporary accounting/retention; audit request metadata with credential redaction; user downloads obey filesystem ownership/permission composition.
- **Security implications:** LLM runtime itself receives no unrestricted internet; defend against local/private-address access and redirect bypass according to documented policy; never send conversation/profile/private file content without explicit tool semantics; strip credentials from logs; no telemetry.
- **Tests required:** INTERNET allow/ask/deny; URL/scheme/redirect/address cases; size/time limits; partial downloads; destination overwrite; secret redaction; offline behavior; malicious response bounds; cache quotas.
- **Dependencies:** Milestones 008, 011, and 013 for context provenance (history retrieval itself is optional to web execution).
- **Explicit out of scope:** Cloud AI, remote embeddings, background telemetry, browser visual automation, updater traffic.
- **Manual verification:** Against a controlled local test server, search/fetch/download within bounds, exceed limits, test redirects/denial/overwrite, inspect outbound payloads and logs, and confirm model-server network remains unnecessary.
- **Definition of done:** The provider decision is recorded in the active ExecPlan; all internet use is explicit, bounded, policy-controlled, auditable, redacted, and independent of local inference; switching providers does not require Agent Engine or Tool Broker changes.

### Milestone 015 — Full CLI command surface, cleanup, and storage lifecycle

- **Objective:** Complete the simple CLI’s required operational commands and deterministic storage cleanup/retention behavior.
- **Rationale for position:** All principal data categories now exist, so cleanup can describe and remove them accurately without an ambiguous “clear all.”
- **User-visible result:** Required slash commands and `jarvis-clear` work; users can search/inspect status and selectively clean notes, conversations, diagnostics, caches, downloads, learning data, and inactive runtime artifacts.
- **Exact scope:** Complete `/permissions`, `/history`, `/memory`, `/notes`, `/logs`, `/learning`, `/model`, `/reasoning`, `/context`, `/status`, `/server`; cleanup profile/model/category/age selection; previews/confirmations; retention/rotation; quota warnings; recovery from interrupted cleanup; concise errors.
- **Architectural components introduced:** Cleanup/retention service, storage-usage service, complete CLI command presenters.
- **Important interfaces/contracts introduced:** Cleanup plan/preview/result; eligible-versus-active data contract; category-specific reset semantics; human-only log rendering route.
- **Persistence/database implications:** Accurate storage usage, retention timestamps, pruning records; active-session data is never pruned while written; database vacuum/maintenance is safe and explicit.
- **Security implications:** Destructive cleanup is scoped and confirmed; raw logs may be rendered to the human client but never returned to model context; secrets remain redacted; failures do not imply deletion succeeded.
- **Tests required:** Every command route; cleanup category/scope/age; active-write protection; quota rotation/refusal/warnings; interruption recovery; profile/model isolation; log human/model separation.
- **Dependencies:** Milestones 006–014.
- **Explicit out of scope:** Rich TUI, desktop/Wayland, systemd autostart, updater/distribution.
- **Manual verification:** Exercise every slash command; fill temporary quota fixtures; preview and clean one category/profile/model/range; confirm unrelated and active data remain; inspect log output routing.
- **Definition of done:** The CLI and lifecycle behaviors required for existing subsystems are complete, deterministic, safe, and fully tested.

### Milestone 016 — Rich TUI client

- **Objective:** Build the installed TUI as a presentation-only client of the existing Core protocol.
- **Rationale for position:** Stable streaming, approvals, history, permissions, logging, and model state now exist, preventing the TUI from inventing a second brain.
- **User-visible result:** A polished profile-themed terminal interface provides streamed Markdown chat, tool progress/confirmations, selectors, history, permissions, debugging, and TUI-local keyboard shortcuts. Once the TUI passes its stability gate, bare `jarvis` and bare profile aliases open it by default; one-shot commands remain non-TUI.
- **Exact scope:** TUI layout/state; streaming rendering; profile/model/learning/reasoning/context indicators; themes/colors/waiting/goodbye messages; debug panel; permission editor; history/model selection; reconnection/cancellation; accessibility and terminal degradation; an explicit stability gate followed by bare-command dispatch to the TUI; preservation of argument-bearing one-shot dispatch outside the TUI; preservation of the simple interactive CLI as an independent fallback, optionally exposed by a future explicit flag such as `--simple`.
- **Architectural components introduced:** TUI client/presenters only.
- **Important interfaces/contracts introduced:** Client-side view models; event-to-view mapping; profile appearance rendering; approval responsiveness; stable default-client selection and explicit invocation-mode dispatch. No Core business interface is duplicated.
- **Persistence/database implications:** Uses Core configuration APIs; no direct database access and no TUI-owned authoritative data.
- **Security implications:** TUI cannot bypass broker/policy/profile/runtime manager; secrets in debug rendering are redacted; confirmation intent is unambiguous; terminal escape content is sanitized.
- **Tests required:** Event rendering/order; reconnect/cancel; approval UX; profile theme isolation; terminal escape/Markdown sanitization; fake-Core integration; stability-gate behavior; bare-command TUI dispatch after stability; argument-bearing non-TUI one-shot dispatch; simple CLI fallback; no direct repository imports.
- **Dependencies:** Milestones 004 and 015.
- **Explicit out of scope:** Voice, Desktop App, desktop automation, changes to agent reasoning, separate TUI persistence.
- **Manual verification:** Run two themed profiles, stream chat/tools, approve/deny actions, browse history/edit permissions, reconnect after Core restart, and use the debug panel without model log exposure; then pass the documented stability gate, confirm bare `jarvis` and a bare profile alias open the TUI, confirm argument-bearing invocations remain non-TUI one-shots, and confirm the simple CLI fallback remains usable.
- **Definition of done:** TUI feature goals and the documented stability gate are met through the same IPC/Core; bare interactive commands default to the stable TUI, one-shot commands remain non-TUI, the simple CLI remains an independent fallback, and all profile/policy/isolation behavior matches CLI behavior.

### Milestone 017 — Wayland desktop and screen capabilities

- **Objective:** Add compositor-neutral desktop context and screen-reading capabilities through portals/D-Bus/accessibility/adapters, with all processing local.
- **Rationale for position:** SCREEN permissions and tool infrastructure are mature; structured application launch already exists; visual access is added only after safer mechanisms.
- **User-visible result:** On supported Wayland desktops, Jarvis can request authorized screen/context information and return structured local observations with explicit portal consent where required.
- **Exact scope:** Desktop adapter interface; capability detection; XDG Desktop Portal capture; D-Bus/accessibility integrations where appropriate for screen/context acquisition; GNOME/KDE/wlroots adapter strategy; local image processing/local VLM adapter; timeouts; ephemeral screenshot lifecycle; structured screen results. SCREEN grants screen/context access only and provides no keyboard or mouse authority.
- **Architectural components introduced:** Desktop adapter registry, screen-capture tool, local screen-understanding provider.
- **Important interfaces/contracts introduced:** Desktop capability/consent result; screenshot provenance/lifetime; local processing guarantee; structured observation/bounds; fallback ordering.
- **Persistence/database implications:** Screenshots are ephemeral by default and quota-controlled if explicitly retained; audit contains sanitized metadata, not unnecessary images.
- **Security implications:** SCREEN policy and compositor consent both apply; screenshots never reach external AI; sensitive image retention is minimized; no X11-only bypass; no keyboard/mouse automation or global input authority exists. Any future input automation requires a separate capability, explicit permission category, security model, and roadmap authorization.
- **Tests required:** Adapter selection; portal denial/cancel; SCREEN policy; time/size limits; image lifecycle; no-network proof for processing; mocked GNOME/KDE/wlroots cases; fallback behavior.
- **Dependencies:** Milestones 008, 010, 014 (network separation proof), and 015.
- **Explicit out of scope:** Jarvis Desktop App, Voice, all keyboard/mouse automation and global input control, X11-only global capture, cloud vision.
- **Manual verification:** On available Wayland environments or controlled mocks, inspect capability status, grant/deny portal capture, process a fixture locally, verify cleanup, and monitor that no network payload contains screenshots.
- **Definition of done:** Supported desktop/screen operations are adapter-based, local, policy/portal-controlled, bounded, audited, and compositor-neutral by contract.

### Milestone 018 — Installation management, diagnostics, and per-profile autostart

- **Objective:** Complete `jarvis-manage`, installation health/repair, runtime diagnostics, model-directory management, registered-profile reconciliation, update settings/checks, and user-session autostart.
- **Rationale for position:** Management and autostart should operate on mature storage, aliases, runtime recovery, and Core health contracts.
- **User-visible result:** Users can inspect and repair their user-local installation, manage runtime/model directories and profile aliases, check daemon state/version, and enable `Start with computer` per profile.
- **Exact scope:** Management menu; installation health checks and non-destructive repairs; user-level systemd Core/profile runtime units; last-valid-model startup; missing-model graceful failure; transparent minimal update checks enabled by default; diagnostics export with redaction; update source/settings (not application).
- **Architectural components introduced:** Installation manager, health/repair service, systemd-user integration, autostart reconciler, update-check service.
- **Important interfaces/contracts introduced:** Health finding/repair plan; autostart unit generation/reconciliation; last-valid-model/no-substitution rule; update-check metadata/privacy contract.
- **Persistence/database implications:** Installation settings remain separate from profiles; per-profile autostart remains profile-owned; health/check timestamps and sanitized diagnostics persist under appropriate XDG roots.
- **Security implications:** User-only/no root; unit files use structured known arguments; repairs cannot mutate user history unexpectedly; update checks upload only minimal version/repository data; checking never installs; active installation remains protected from conversational tools.
- **Tests required:** Management ownership boundaries; unit generation/idempotency; missing model; stale runtime; alias repair; update checks disabled/enabled/privacy; diagnostics redaction; no-root/user-local paths.
- **Dependencies:** Milestones 002–005 and 015; TUI/desktop are not required.
- **Explicit out of scope:** Applying updates, installer/uninstaller, purge, release packaging, machine-wide services.
- **Manual verification:** Inspect status in a temporary user environment, reconcile a broken alias, enable autostart for one profile, simulate missing model and login startup, run a controlled update check, and review redacted diagnostics.
- **Definition of done:** Installation management and user-level autostart are safe, transparent, repairable, and keep profile versus installation settings correctly separated.

### Milestone 019 — Installer, updater, uninstaller, and release distribution

- **Objective:** Deliver reproducible GPL-compatible user-local releases and the only authorized application-update path.
- **Rationale for position:** Distribution must preserve every established migration, data, command, service, and protection invariant; implementing it last minimizes unsafe provisional update behavior.
- **User-visible result:** Users can install without root, receive all required commands/TUI/service assets, update stable releases with validation, and uninstall binaries separately from optional data purge.
- **Exact scope:** Release packaging; dependency/license inventory; user-local installer; all command entry points and desktop entry where appropriate; systemd user assets; `jarvis-update` release query/download/compatibility/integrity/authenticity policy/application/rollback/post-check; `jarvis-clear` inclusion; uninstall versus explicit purge; Debian/Ubuntu validation; migrations across supported versions.
- **Architectural components introduced:** Installer, release manifest/validator, updater, rollback/post-update validator, uninstaller.
- **Important interfaces/contracts introduced:** Separate integrity and cryptographic-authenticity verification contracts; authenticity rooted in trusted information already available to the installed Jarvis; exact signing technology and trust-material lifecycle selected and recorded during Milestone 019; compatibility/migration boundary; exclusive updater lock; preserved-data contract; uninstall/purge confirmation; official configured release source.
- **Persistence/database implications:** Preserve XDG profiles, conversations, memories, notes, and settings across install/update/default uninstall; back up/transactionally migrate as designed; purge is separate and explicit.
- **Security implications:** Never `curl | bash`; verify both integrity and cryptographic authenticity before application; reject a checksum as sufficient authenticity when it is distributed beside the artifact from the same source without an independent installed trust root; only `jarvis-update` mutates active installation; conversational tools cannot invoke an internal bypass; failure is recoverable; no root by default; dependencies are maintained, non-telemetric, and GPL-compatible.
- **Tests required:** Fresh install; all commands/help and default-client dispatch; upgrade/downgrade rejection/rollback; corrupt/untrusted/incompatible artifact; rejection when an attacker can replace both artifact and same-source checksum but cannot satisfy the installed trust root; trusted-key/material update and failure cases defined by the selected technology; interrupted update; concurrent update; data preservation/migrations; uninstall preserve/purge; protected-installation enforcement; Ubuntu/Debian matrix; license inventory.
- **Dependencies:** All prior milestones; Voice and Desktop App remain excluded.
- **Explicit out of scope:** Cloud inference, telemetry, machine-wide default install, silent in-chat updates, Voice, Jarvis Desktop App.
- **Manual verification:** In disposable supported-system environments, install as an ordinary user, run command/help/default-client/Core/chat smoke tests, update through a controlled cryptographically authenticated release, replace both an artifact and its adjacent checksum to confirm authenticity still fails, simulate failure and rollback, uninstall preserving data, reinstall and confirm recovery, then separately verify explicit purge.
- **Definition of done:** The exact signing technology and trust lifecycle are recorded in the active ExecPlan; a validated and cryptographically authenticated stable release installs, operates, updates only through `jarvis-update`, preserves user data, uninstalls safely, and satisfies the complete in-scope `AGENTS.md` product without Voice/Desktop implementation.

## Roadmap-wide release gates

Every milestone must satisfy these gates in addition to its own definition of done:

- Its ExecPlan exists before implementation, remains current, and records deviations and decisions.
- Automated tests run only against temporary homes/XDG roots, test databases, fake providers, fake GGUF fixtures, controlled local servers, or disposable environments as appropriate.
- New dependencies have documented maintenance, network/telemetry, installation-burden, and GPL-compatibility review.
- New user-facing strings are localization-ready; internal code, schemas, events, tests, and documentation are English.
- Security-sensitive operations use typed inputs/results/errors, bounded execution, centralized policy where applicable, sanitized diagnostics, and auditable correlation IDs.
- No milestone silently widens network access, permissions, data sharing, installation scope, model context, or deletion behavior.
- Documentation and the dependency graph are updated when a discovery changes later milestone assumptions.
