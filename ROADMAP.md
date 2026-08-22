# Jarvis-CLI Development Roadmap

## Status and authority

This roadmap decomposes the product specified by `AGENTS.md` into sequential, independently verifiable milestones. `AGENTS.md` remains authoritative. If this roadmap and `AGENTS.md` differ, implementation stops until the roadmap is corrected; a milestone may not reinterpret an invariant.

This document plans work only. Milestones 000 through 006B are **DONE**; their evidence is retained
in the corresponding completed ExecPlans. Before any milestone starts, its ExecPlan must be created
and maintained as required by `PLANS.md`. Milestone 006C is the next **NOT STARTED** milestone;
Milestone 007 and every later implementation milestone are also **NOT STARTED**.

The roadmap excludes Jarvis Voice and the Jarvis Desktop App. Their compatibility requirement is preserved by keeping Jarvis Core behind a versioned local IPC protocol and keeping all client presentation outside Core.

## Dependency analysis

The principal dependency chains are:

1. XDG path ownership, versioned defaults, migrations, stable identifiers, redaction, and protected-installation detection underpin every persistent or security-sensitive subsystem.
2. Profiles precede model associations, runtime ownership, conversations, learning, permissions, appearance, and every `(profile_id, model_id)` namespace. Alias lifecycle depends on stable profile identity rather than display names.
3. Core IPC precedes every real presentation client. The read-only GGUF registry and minimum installation-management API then precede profile/model selection and runtime startup. Provider isolation and runtime locking precede chat.
4. The first chat path is split into a Core pipeline and a simple client slice. The Core slice owns Agent Engine, Context Builder, persistence, diagnostics, FIFO generation scheduling and first-chat learning activation; the client slice makes those contracts visibly usable without implementing a second brain. The permanent user-local installation and socket-activated single-Core topology then expose that slice through the canonical physical `jarvis` command without changing the application-domain dependency direction.
5. The Policy Engine, Tool Broker, approval protocol, audit trail, typed tool contracts, bounds, and active-installation guard must exist before any host tool. Read-only tools come first; structured application launch follows; filesystem mutation follows that; shell and destructive process actions come last among local host tools.
6. Memory retrieval depends on accumulated conversations/private notes and a context budget. Web access depends on network policy and bounded downloads. Screen access depends on the same policy/broker path plus Wayland portals/adapters.
7. The TUI depends on stable streaming IPC and approval events, but not on desktop automation. Cleanup depends on all storage categories. Per-profile model autostart extends the established single-Core systemd-user topology and depends on mature runtime recovery. Final distribution hardening and updating come last because they must preserve the M006C installation foundation, data, and protected-installation boundary end to end.

Cross-cutting requirements apply from their first relevant milestone onward: no telemetry, no required cloud inference, English internals, localization-ready user text, user-local/XDG storage, typed errors, centralized defaults, bounded data, profile isolation, secret redaction, and GPL-compatible dependencies.

## Established product decisions

- **Profile cloning:** A new profile clones Jarvis’s current configurable state. Before model associations exist, this includes only profile configuration available at that milestone. Once the Model Registry exists, creation also atomically clones Jarvis’s selected model and that model’s applicable per-profile configuration such as reasoning level and context window. Existing profiles are not retroactively assigned a model. Conversations, private model notes, memories, learning history/state, chat logs, and diagnostic session history always start empty. An inherited model that is missing is reported as unavailable and is never silently replaced.
- **Interactive client dispatch:** M006B defines the simple assistant semantics for the default profile and logical aliases, and tests them before installation through `python -m jarvis.cli` and Core-resolved `--profile-alias`. M006C introduces the permanent physical `jarvis` dispatcher, initially routing bare use to the simple interactive CLI and argument-bearing use to the non-TUI one-shot path. Once Milestone 016 establishes the TUI as stable, that same dispatcher routes bare interactive use to the TUI without replacing the installation architecture. The simple interactive CLI remains an independent fallback; an explicit option such as `--simple` may expose it after the default changes. M019A later materializes dynamic physical profile aliases.
- **Desktop input boundary:** SCREEN authorizes screen/context access only. The roadmap contains no unrestricted keyboard or mouse control. Any future input automation is a separate capability requiring its own explicit security and permission design.

## Remaining product/technical decision gates

These decisions do not block Milestone 000, but the named milestone must not silently select them:

- **Web search provider (Milestone 014):** choose the concrete backend, credential model, query-disclosure policy, and provider fallback behavior. The provider interface is fixed; no backend is selected now.
- **Release signing technology (Milestone 019 family, resolved in 019B):** choose the cryptographic authenticity technology and trusted-key/material lifecycle. The fixed requirement is authenticity rooted in trusted information already available to the installed Jarvis, in addition to integrity verification. A checksum distributed beside the artifact from the same source is insufficient by itself.

Until those gates are resolved, expose no concrete web-search backend and do not ship an updater whose trusted authenticity mechanism is unsettled.

## Milestone sequence

### Milestone 000 — Repository and security foundation

- **Objective:** Establish the smallest runnable project foundation: GPL-3.0 licensing, controlled dependency metadata, XDG path semantics, centralized/versioned defaults, typed error conventions, SQLite migration infrastructure, centralized redaction/diagnostic logging primitives, installation identity/protection primitives, and isolated test infrastructure.
- **Rationale for position:** Every later subsystem persists data, emits diagnostics, or evaluates paths. These rules must be fixed before feature state is created.
- **User-visible result:** No assistant yet; maintainers can initialize and inspect an empty user-local data environment without touching real user state in tests.
- **Exact scope:** Project/package metadata; license and essential developer documentation; XDG config/data/state/cache/runtime resolution and fallbacks; atomic initialization; schema-version and migration runner; versioned default registry; quota/default/accounting/reservation primitives; correlation identifiers; bounded structured diagnostic sink; central secret redactor; active-installation path and protected-file-identity primitives; fake clocks/filesystems/providers as needed for tests. No profiles beyond schema readiness.
- **Architectural components introduced:** Storage foundation, configuration-default registry, migration runner, logging/redaction foundation, installation-boundary service, common typed errors.
- **Important interfaces/contracts introduced:** `XdgPaths`; defaults version contract; migration transaction contract; quota/accounting/reservation contract; sanitized structured-event envelope; installation path/file identity and protected-target contract; clock/ID abstractions needed for deterministic tests.
- **Persistence/database implications:** Create the initial SQLite database and migration ledger only, with explicit XDG ownership and permissions. Separate persistent state from runtime artifacts. No production identity/history rows yet.
- **Security implications:** Fail closed on ambiguous protected-installation path or file identity; do not treat stale canonical strings as final authorization; redact centrally before persistence/rendering; never log secret environment values; prohibit unsafe path broadening; ensure tests use temporary XDG roots and databases.
- **Tests required:** XDG fallback/override tests; migration apply/rollback/idempotency tests; defaults version tests; quota reservation/accounting and simulated storage-exhaustion tests; redaction corpus tests; protected-path canonicalization, symlink, hardlink identity, ancestor/descendant, changed-target, special-file, and development-clone tests; file permission and test-isolation tests; no-network/no-telemetry checks appropriate to the foundation.
- **Dependencies:** Only `AGENTS.md`, this roadmap, `PLANS.md`, and its future ExecPlan.
- **Explicit out of scope:** Profiles, model discovery, IPC server, llama.cpp, chat, tools, TUI, installer/updater, and real user installation.
- **Manual verification:** Under temporary XDG environment variables, initialize twice, inspect path separation and database version, emit a synthetic event containing test secrets and confirm redaction, and verify active-installation paths are protected while a separate clone is not.
- **Definition of done:** Foundation contracts are documented and tested; initialization is deterministic and idempotent; no host capability or application feature exists; repository checks pass in isolated temporary state.

### Milestone 001 — Profile identity and configuration domain

- **Objective:** Implement persistent profile identity, the permanent `jarvis` profile, profile-scoped settings, `(profile_id, model_id)` namespace-ready ownership, and centralized resettable configuration schemas.
- **Rationale for position:** Profile identity is the primary isolation key and must precede models, sessions, permissions, and clients.
- **User-visible result:** A service-level profile catalog always contains Jarvis and can create, rename, inspect, and safely delete/reset non-default profiles.
- **Exact scope:** Stable internal profile IDs; display names; deterministic Unicode-to-ASCII command normalization; reserved-name/collision checks; creation by cloning the current Jarvis profile configuration that exists at this milestone; rename preserving identity; deletion protection; centrally coordinated profile and section reset planning/confirmation APIs; centrally versioned product-default restoration; profile-owned persona/context/appearance/waiting/goodbye/logging/autostart/permission/model-setting schemas. Model associations do not exist yet and are not cloned in this milestone. Conversations, private model notes, memories, learning history/state, chat logs, and diagnostic session history are explicitly excluded from cloning. Destructive operations remain service APIs for later UI wiring.
- **Architectural components introduced:** Profile service, profile repository, configuration service, defaults/reset service.
- **Important interfaces/contracts introduced:** Profile CRUD commands/results; normalized alias contract; clone allowlist for currently available profile configuration; protected-profile invariant; extensible destructive-operation participant/coordinator contract; reset preview and confirmation token contract; centrally versioned product-default reset contract; stable profile ID contract.
- **Persistence/database implications:** Add `profiles`, `profile_aliases`, profile settings, and reset metadata through migrations. Enforce uniqueness and the permanent Jarvis invariant at service/database boundaries where practical.
- **Security implications:** Prevent alias injection/path traversal; never use aliases as data ownership keys; transactional clone/rename; reset/delete require exact preview and central coordination; fail closed on partial destructive operations; do not allow model-originated configuration mutation.
- **Tests required:** All normalization cases; empty/reserved/conflicting names; Jarvis creation idempotency, rename/deletion protection; concurrent clone snapshot consistency; clone current profile configuration but none of the forbidden historical/learned categories; profile isolation; versioned-default reset rather than Jarvis re-clone; reset previews and scoped resets; participant failure/transaction rollback.
- **Dependencies:** Milestone 000.
- **Explicit out of scope:** `jarvis-config` presentation, executable alias files, models, sessions, runtimes, and full-profile history deletion for categories not yet implemented.
- **Manual verification:** In temporary state, initialize Jarvis, create “João Trabalho,” confirm `joao-trabalho`, alter Jarvis profile configuration and clone again, verify configuration was copied while historical/learned categories and model associations are absent, reset the clone to centrally versioned product defaults, rename/delete it, and confirm Jarvis cannot be renamed or deleted.
- **Definition of done:** Profile invariants are enforced below the UI, all current profile settings have centrally versioned defaults/reset behavior, and isolation tests pass.

### Milestone 002 — Jarvis Core and versioned local IPC

- **Objective:** Establish `jarvisd` as the sole Core process boundary and a versioned, streaming-capable Unix-domain-socket protocol used by thin clients.
- **Rationale for position:** Runtime, agent, approvals, CLI, and future clients need one transport and ownership boundary before feature-specific messages proliferate.
- **User-visible result:** A development CLI can connect, query status/profile/model catalogs, receive structured events, cancel a harmless request, and report protocol errors clearly.
- **Exact scope:** Single-Core-per-user/XDG-state ownership; atomic Unix socket/lock ownership and stale recovery; socket permissions; framing and safe serialization (never pickle); protocol and capability negotiation; client-neutral typed operations; request/correlation IDs; monotonically ordered streaming events with exactly one terminal event; bounded explicit reconnect/replay semantics; approval-expiry placeholder; cancellation/disconnect semantics; thin client transport; Core status APIs.
- **Architectural components introduced:** Jarvis Core host, IPC server/client, protocol schema, request router, event stream, cancellation coordinator.
- **Important interfaces/contracts introduced:** Client-neutral request/response/error envelopes; protocol/capability negotiation; `response_started`, `text_delta`, tool/approval placeholder event schemas, `response_completed`, and `error`; event sequence and terminal-event invariant; compatibility/reconnect policy; disconnect-does-not-cancel contract.
- **Persistence/database implications:** Runtime socket stays in XDG runtime storage; lifecycle/runtime events use sanitized logs; no chat rows yet.
- **Security implications:** User-only socket permissions; peer/local-user validation where supported; bounded frames; schema validation; no arbitrary object deserialization; clients cannot call internal repositories directly.
- **Tests required:** Serialization/framing fuzz cases; version/capability negotiation; client-neutral payload checks; user-only socket permissions; simultaneous Core-start race; malformed/oversized messages; monotonic streaming order and exactly-one terminal event; approval expiry schema; cancellation/disconnect and bounded reconnect status; stale socket/lock recovery; typed IPC errors.
- **Dependencies:** Milestones 000–001.
- **Explicit out of scope:** llama.cpp startup, chat generation, approvals execution, TUI, systemd service installation.
- **Manual verification:** Start Core in a temporary runtime directory, query it from two clients, observe ordered event/correlation IDs, test incompatible protocol and cancellation, stop Core, and verify socket cleanup.
- **Definition of done:** All client access crosses the documented local protocol, Core owns services, and transport robustness/security tests pass.

### Milestone 003 — Profile-first configuration client and logical aliases

- **Objective:** Provide the initial profile-first configuration workflow and logical alias management exclusively through Core IPC.
- **Rationale for position:** Core already owns repositories and application services, so the first real client never needs direct database access.
- **User-visible result:** `jarvis-config` always begins with profile selection or “Create new profile”; logical normalized aliases resolve to stable profile identity through Core; local configuration help does not start a model.
- **Exact scope:** Minimal localization-ready `jarvis-config` presentation over client-neutral Core operations; create/rename/delete/reset confirmations; common versus Advanced grouping; reset routes for every exposed section; persistent logical alias-to-ProfileId resolution; `profile-management-v1`; `jarvis-config`, `jarvis-help`, `-h`, `--h`, and `--help` behavior. No public `jarvis` or profile-alias command behavior is introduced.
- **Architectural components introduced:** Thin CLI client shell, configuration presenter, logical alias resolver, and profile-management IPC operations.
- **Important interfaces/contracts introduced:** IPC profile/configuration operations; alias-to-stable-profile resolution; confirmation UX contract; help-without-Core/model-start contract. Clients never import repositories or database services.
- **Persistence/database implications:** Existing M001 `profile_aliases` remains authoritative; no profile history or filesystem alias state is introduced.
- **Security implications:** Alias strings remain strict data and never ownership keys; reserved and profile-alias collisions are rejected; external PATH collision handling, executable exposure, and filesystem reconciliation are deferred; destructive profile actions show exact categories and require explicit confirmation.
- **Tests required:** Profile-first navigation over fake/real test Core; no direct repository imports; configuration help; no model startup on help; logical alias resolution/rename/delete; no physical command or PATH behavior; collision/race/rollback tests; localization boundary tests; destructive confirmation tests.
- **Dependencies:** Milestones 000–002.
- **Explicit out of scope:** Physical profile commands, executable aliases, launchers, symlinks, wrappers, filesystem alias registries, PATH integration/modification, external PATH collisions, chat, rich TUI, production installer, and complete settings screens whose backing feature does not yet exist.
- **Manual verification:** Through a temporary Core, create a profile in `jarvis-config`, resolve its logical alias through IPC, rename it and verify old/new logical resolution, then verify attempted Jarvis deletion is rejected without creating a command file or changing PATH.
- **Definition of done:** Profiles are fully manageable through the required profile-first IPC flow, logical aliases resolve to stable IDs, and no invocation starts inference or creates a physical command.

### Milestone 004 — Minimum installation management, model registry, and GGUF discovery

- **Objective:** Introduce the minimum installation-management contract for model directories and the llama.cpp runtime path, then discover user-owned GGUF files and associate stable model records/configuration with profiles.
- **Rationale for position:** Runtime startup needs installation-owned runtime configuration and trustworthy model identity; these settings must not leak into profile configuration.
- **User-visible result:** A minimal `jarvis-manage` surface configures model directories and the llama.cpp path. Users can refresh discovery, see metadata/size/missing state, and select a model per profile without Jarvis downloading or modifying it. Later profile creation inherits Jarvis’s current selected model and compatible settings; a missing inherited model is shown as unavailable.
- **Exact scope:** Client-neutral Core management operations and a minimal management presenter only for model directories/runtime path; bounded/safe recursive scan; canonical-path deduplication; lightweight GGUF metadata parsing when reasonable; cached stable fingerprint; missing-file tracking; profile-model associations; reasoning/context and structured advanced runtime settings; transactional extension of profile creation to clone Jarvis’s selected-model association and applicable settings without private/history data. Existing profiles are not backfilled.
- **Architectural components introduced:** Minimum installation-management service/client, Model Registry, GGUF scanner/metadata reader, profile-model configuration repository.
- **Important interfaces/contracts introduced:** Installation-owned `RuntimeLocationConfig`; `ModelRecord`, stable `model_id`, scan request/result, missing-state contract, `ModelRuntimeConfig`, conceptual reasoning input, structured argument validation, and model-aware profile-clone participant.
- **Persistence/database implications:** Add installation settings for model search directories/runtime path, `models`, `profile_models`, scan metadata/fingerprint, and selected/last-valid model fields. Model files remain outside Jarvis storage.
- **Security implications:** Management settings are not exposed through `jarvis-config`; scanner is read-only; traversal is bounded and link loops/races handled; model identity is revalidated before runtime use; models are never executed/renamed/moved; arguments cannot become shell fragments.
- **Tests required:** Installation/profile ownership boundary; no direct client database access; discovery, recursion, duplicates/symlinks, malformed/minimal fake GGUF, missing files, stable IDs/cache invalidation, changed model before use, same model across profiles, profile-specific settings, transactional selected-model inheritance, concurrent clone snapshot, empty private/history namespaces, unavailable inherited model with no fallback, oversized metadata bounds, and no model mutation.
- **Dependencies:** Milestones 000–003.
- **Explicit out of scope:** Full `jarvis-manage`, model downloads, llama-server process management, chat, arbitrary runtime arguments, and automatic replacement of a missing model.
- **Manual verification:** Configure temporary model/runtime paths through the minimal management client, scan small fixtures, configure Jarvis’s selected model/reasoning/context, create a profile and verify exact history-free inheritance, remove the model and confirm unavailable state without substitution, then configure distinct settings for two profiles sharing it.
- **Definition of done:** Minimum installation settings remain installation-owned, registry operations are deterministic/read-only, stable IDs and per-profile settings persist, cloning is exact and history-free, and missing models fail descriptively.

### Milestone 005 — LLM provider and per-profile runtime manager

- **Objective:** Run local `llama-server` behind an implementation-neutral provider and enforce one active runtime per profile.
- **Rationale for position:** Chat must not own processes directly; runtime locking, health, timeouts, and isolation must be reliable first.
- **User-visible result:** A selected local GGUF can be started, health-checked, stopped, and switched; two profiles may run the same GGUF independently.
- **Exact scope:** Provider protocol; `LlamaCppProvider`; structured argv/process environment; localhost binding; explicit runtime states; race-safe per-profile port ownership; PID start time/executable/runtime ID/lock/socket/health evidence; stale and orphan artifact recovery; startup/health/shutdown timeouts; sanitized server log capture with enforced quota; runtime participation in centrally coordinated profile reset/delete quiescence; fake provider.
- **Architectural components introduced:** LLM provider abstraction, llama.cpp adapter, runtime manager, runtime lock registry, health monitor.
- **Important interfaces/contracts introduced:** Provider start/stop/health/chat primitives; `RuntimeHandle`, `RuntimeHealth`, state/event model; owned-process/endpoint identity; per-profile exclusivity; model switching may proceed only after an active generation finishes or is explicitly cancelled and recorded.
- **Persistence/database implications:** Add runtime events and last-valid runtime/model metadata; ephemeral locks/PIDs belong in XDG runtime, not persistent configuration.
- **Security implications:** No shell concatenation; no externally exposed listener by default; no inherited secret environment without allowlisting; models get no host tools/network authority; server output passes redaction.
- **Tests required:** State transitions, double-start race, PID reuse, stale locks/orphan child, endpoint ownership, timeout/failure cleanup, profile reset/delete quiescing an active runtime, participant failure reporting, model switch with active-generation placeholder, same GGUF in multiple profiles, port allocation collision, fake provider, structured argv, server log redaction/quota, and proof runtime startup does not consume learning state.
- **Dependencies:** Milestones 000, 002, and 004.
- **Explicit out of scope:** Agent prompts, conversation UI/history, tool calling, autostart/systemd installation.
- **Manual verification:** With a configured compatible local runtime, start/health/stop one profile and concurrently start the same model for another; force a failed startup and stale lock, then verify recovery and diagnostics.
- **Definition of done:** Exactly one healthy runtime can exist per profile, cross-profile use remains isolated, failures leave recoverable state, and no llama.cpp detail leaks outside provider contracts.

### Milestone 006A — Core chat pipeline

- **Objective:** Implement the client-neutral Core chat pipeline with centralized context, isolated persistence, bounded complete diagnostics, first-chat learning activation, streaming/cancellation, and deterministic per-profile generation ownership.
- **Rationale for position:** Runtime and IPC contracts are stable; Core chat behavior must be correct before any client presentation is attached.
- **User-visible result:** Through a protocol test client, a local text turn streams and persists correctly, activates learning for the first user-facing `(profile_id, model_id)` chat, and reaches a single recorded terminal state.
- **Exact scope:** Agent Engine for text-only chat; centralized Context Builder (core instructions, persona, profile context, recent conversation, request); session/message persistence; context budgeting; transactional first-chat learning initialization; deterministic FIFO queue per profile/runtime while allowing cross-profile concurrency; generation cancellation; bounded diagnostic reservation/persistence; profile/model chat-diagnostic store distinct from infrastructure diagnostics/audit.
- **Architectural components introduced:** Agent Engine, Context Builder, conversation service, per-profile generation coordinator, learning-state lifecycle minimum, chat diagnostic service.
- **Important interfaces/contracts introduced:** Client-neutral `ChatRequest`/stream; session/turn IDs; FIFO admission and cancellation ownership; model-switch quiescence contract; context contribution/budget contract; exactly-one terminal event; human diagnostic response types are ineligible for Context Builder input.
- **Persistence/database implications:** Add sessions, messages, learning state and profile/model chat diagnostics keyed by `(profile_id, model_id)` plus session/request/turn identifiers. Reserve applicable quotas before generation; transactionally finalize successful, failed and cancelled turns.
- **Security implications:** Raw diagnostic/audit stores are type- and route-separated from model input; prompt contributions are bounded; inference remains localhost-only; secrets are redacted; work refuses to start if the minimum diagnostic record cannot be reserved.
- **Tests required:** FIFO ordering under concurrent same-profile requests; concurrent different-profile requests; cancel queued/active generation; profile reset/delete quiescing queued/active chat; reset removes owned chat diagnostics while retaining sanitized reset audit; model-switch wait/cancel; context ordering/budget; composite profile/model/session isolation and identifier-confusion attacks; transactional first-chat activation; runtime startup/autostart non-activation; diagnostic reservation/ENOSPC; terminal-event exactly once; logs/audit/human diagnostic results never enter context.
- **Dependencies:** Milestones 000–005.
- **Explicit out of scope:** Real CLI presentation, slash commands, tool calls, private notes, long-term memory, web, TUI, desktop.
- **Manual verification:** Use a test IPC client and fake provider to stream concurrent turns in two profiles, observe FIFO within one profile and concurrency across profiles, cancel a turn, and inspect isolated persistence and captured prompts.
- **Definition of done:** Core chat is deterministic, isolated, bounded, auditable and client-neutral, with no host capability path.

### Milestone 006B — Simple CLI chat MVP

- **Objective:** Expose the Core chat pipeline through the required simple interactive and one-shot CLI behavior without duplicating Core logic.
- **Rationale for position:** The client consumes already tested Core contracts and becomes the first complete user-facing chat slice.
- **User-visible result:** Before production installation, package-level `python -m jarvis.cli` provides the default-profile assistant semantics and `python -m jarvis.cli --profile-alias <alias> [request]` provides logical-profile interactive/one-shot semantics; natural-language arguments run non-TUI one-shots; responses stream, match language by default, retain isolated sessions, and visibly show learning state. M006C later exposes the corresponding canonical physical `jarvis`; M019A later exposes dynamic physical profile commands.
- **Exact scope:** Invocation-mode dispatch through `python -m jarvis.cli` and Core-resolved `--profile-alias <alias> [request]` for development/package testing; streaming renderer; `/help`, `/quit`, `/exit`, `/clear`, `/model`, `/reasoning`, `/context`, `/status`, `/server`, `/config`, `/license`, and human-only `/logs`; `/learning status|start|finish`; slash-command interception; first-learning banner; five visible logging modes; client cancellation and authoritative disconnect/reconnect status. Each presenter calls client-neutral Core operations. It does not own production fixed-command/PATH installation or dynamic physical profile-command management.
- **Architectural components introduced:** Simple CLI presenter, command router and visible-event renderer only.
- **Important interfaces/contracts introduced:** Bare-versus-argument invocation dispatch; slash commands never sent blindly to the LLM; diagnostic-versus-visible event rendering; `none` still renders approvals/errors/critical failures.
- **Persistence/database implications:** No client-owned persistence or database access. Core-owned chat/logging limits introduced by 006A remain enforced.
- **Security implications:** CLI cannot retrieve raw logs into chat requests, access repositories, manage runtimes directly, or execute host capabilities.
- **Tests required:** Documented development/package-level default/profile-alias dispatch and one-shot dispatch; no direct repository imports; streaming/order/reconnect/cancellation rendering; first-run banner and learning commands; language/persona behavior; slash interception; every visible mode; diagnostic persistence even under `none`; terminal escape sanitization.
- **Dependencies:** Milestone 006A.
- **Explicit out of scope:** Private-note generation/retrieval, history/memory search, tools, web, rich TUI, desktop.
- **Manual verification:** Chat through two profile aliases sharing a model, inspect learning transitions, restart sessions, switch visible modes, cancel generation, disconnect/reconnect, and verify diagnostics exist but never appear in captured prompts.
- **Definition of done:** The complete simple CLI chat MVP works through IPC/Core and obeys first-run, isolation, logging and client-boundary invariants.

### Milestone 006C — User-local Installation and Core Activation Foundation

- **Objective:** Establish the first permanent production slice of Jarvis's user-local installation architecture so the completed simple chat MVP runs as `jarvis` from an ordinary shell with on-demand single-Core activation and an understandable first-run setup path.
- **Rationale for position:** M006B has completed the client and Core chat semantics, but normal use still depends on package-module invocation and a separately started Core. The production installation, activation and readiness contracts must exist before later user-facing milestones rely on an installed assistant.
- **User-visible result:** Without entering the repository, activating a development environment, manually starting `jarvisd`, or invoking `python -m`, `jarvis` opens the simple interactive CLI and `jarvis "hello"` runs a one-shot. `jarvis --profile-alias <alias>` continues to resolve logical aliases through Core. If Jarvis lacks a usable selected model/runtime configuration, invocation offers or enters a guided setup flow and can continue into chat after successful validation.
- **Exact scope:** Root-free user-local installation into a Jarvis-owned private production virtual environment; stable collision-safe user-local dispatchers for canonical `jarvis` and the already-existing fixed management/configuration/help commands appropriate to this milestone; service-owned `jarvisd` infrastructure rather than a normal user workflow; no source-tree or activated-venv dependency; no `pipx`, global/system Python installation or global Python mutation; clear ownership separation among application files, dispatchers, installation-manifest-owned assets in the user systemd unit search path, and XDG config/data/state/cache/runtime; true systemd-user socket activation with systemd owning the production Unix listener and passing it to foreground `jarvisd`; inherited-listener validation/adoption without unlink or rebind; deterministic client connection/readiness and typed activation failures; exactly-one-Core lock/ownership preservation; minimum installed-file identity, manifest and repair foundation designed for M019A extension; client-neutral readiness/setup IPC orchestration reusing M004/M005 services to configure `llama-server`, model directories, discovery, Jarvis-profile model selection, essential reasoning/context/runtime settings where required, readiness validation and return to chat.
- **Architectural components introduced:** User-local installation foundation, Jarvis-managed application environment, fixed-command dispatcher, systemd-user socket/service assets and activation adapter, installed-file manifest/repair foundation, and minimal setup/readiness presenter plus Core orchestration contracts.
- **Important interfaces/contracts introduced:** Fixed-command installation/collision result; installed application/dispatcher/unit identity and ownership contract; production versus self-bound development listener modes; validated inherited listening-descriptor contract; deterministic Core activation/readiness result; setup state/step/result and typed cancellation/failure contracts. The CLI and installer remain presentation/lifecycle layers and never own model scanning, runtime management, repositories or SQLite.
- **Persistence/database implications:** Reuse existing installation settings, profile/model associations and XDG stores through Core services. Add only installation identity/manifest state necessary to validate and repair the M006C foundation, with application files and service/dispatcher assets kept separate from mutable XDG profile data and ephemeral XDG runtime state. Any schema change must be migration-backed; setup introduces no client-owned persistence.
- **Security implications:** No root, sudo, global Python mutation, source-tree execution dependency, telemetry or updater authority. Fixed commands must never overwrite or claim unrelated executables/PATH entries. The private environment, dispatchers, systemd assets and manifest extend active-installation protection. The inherited listener must be a correctly owned, user-only Unix listening socket at the expected runtime identity; production Core must neither unlink nor rebind it. Concurrent activation must yield one Core, preserve peer/framing/protocol/security checks and stale-state safety, and never background-spawn a competing daemon.
- **Tests required:** Isolated install/reinstall/repair tests with temporary user roots and PATH; private-environment/source-independence/global-Python non-mutation proofs; fixed-command collision and replacement-race cases; installed identity/manifest and protected-file/link tests; unit/socket asset validation; inherited descriptor type/address/access/ownership validation and rejection cases; concurrent socket activation/single-Core/readiness/stale-state cases; framing, peer validation and disconnect semantics regressions; no launcher `jarvisd &` path; first-run state matrix for missing runtime path/directories/model/selection, discovery refresh, essential settings, successful readiness/chat continuation, cancellation and typed failures; client boundary tests proving no repository/SQLite/runtime duplication; help without model startup.
- **Dependencies:** Milestones 000–006B. It consumes M004/M005 model/runtime services and M006A/M006B Core/IPC/client behavior without changing their ownership.
- **Explicit out of scope:** Dynamic physical profile aliases and their collision/materialization/rename/delete/repair/uninstall lifecycle; per-profile `Start with computer` and model-runtime autostart; TUI default dispatch; `jarvis-clear`; desktop assets not yet introduced; complete release packaging and supported-distribution matrix; final installer/uninstaller, uninstall versus purge and interrupted uninstall recovery; release query/download, update compatibility, integrity/authenticity, signing/trust, updater authority, rollback and post-update validation.
- **Manual verification:** In a disposable user installation and user-service environment, install without root, confirm unrelated command collisions are preserved, remove access to the source checkout, run bare and one-shot `jarvis`, confirm systemd owns and activates one Core socket/service, exercise logical `--profile-alias`, complete setup from an unconfigured state through a real or controlled local GGUF/runtime, continue into chat, inspect installation identity/repair results, and verify no global Python or unrelated PATH entry changed.
- **Definition of done:** The permanent user-local foundation exposes collision-safe fixed commands including `jarvis`, runs independently of the source tree from a Jarvis-managed private environment, activates exactly one Core through a validated systemd-owned inherited socket, guides an unconfigured user to Core-validated chat readiness, extends active-installation identity/repair contracts, and leaves dynamic aliases, profile autostart, final distribution and updates to their owning milestones.

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
- **Dependencies:** Milestone 006B for the Core/IPC chat contract. Milestone 006C supplies the normal installed invocation and manual-acceptance path because M007 follows it in roadmap order, but M007's Core learning/private-note services must remain independently testable through Core/IPC and must not depend on systemd, dispatchers or installer code.
- **Explicit out of scope:** Semantic/episodic memory, automatic embeddings, OS tools, web.
- **Manual verification:** Create notes during learning, finish/restart without deletion, reset with confirmation, switch profile/model and confirm absence, and inspect captured contexts for only relevant bounded notes.
- **Definition of done:** Learning and notes meet lifecycle, locality, inspectability, reset, limit, and isolation requirements.

### Milestone 008 — Policy Engine, Tool Broker, approvals, and audit foundation

- **Objective:** Build the complete authorization/execution boundary before registering any real host capability.
- **Rationale for position:** AGENTS.md forbids OS access outside the broker and requires centralized allow/ask/deny decisions; tools cannot safely precede this gate.
- **User-visible result:** A synthetic non-host tool can demonstrate allowed, denied, and human-approved calls with clear streamed status and durable audit evidence.
- **Exact scope:** Typed tool definitions and registry; strict argument/result validation; capability categories/defaults; centralized Policy Engine; matching overrides; approval request/allow-once/always-allow/deny flows; permanent-change explicit intent; broker execution lifecycle, bounds, cancellation and timeouts; immutable active-installation rule; sudo denial; audit and tool-call records; client approval events; `/permissions` inspection/editor presenter over Core IPC.
- **Architectural components introduced:** Policy Engine, Tool Broker, approval service, audit service, tool registry, execution context.
- **Important interfaces/contracts introduced:** Tool descriptor, validated invocation/result/error; policy query/decision/reason; approval scope; `tool_call_*` events; capability-to-permission mapping; mandatory broker-only invocation contract.
- **Persistence/database implications:** Add permissions/overrides, approvals, tool calls, and audit events keyed by correlation/profile/model/session/turn; centralized retention/accounting.
- **Security implications:** Model cannot register tools, mutate permissions, forge approvals, bypass `ask`, access sudo, or target the active installation; authorization binds validated target identity and is rechecked at execution; canonical strings alone are insufficient; audit is sanitized, quota-enforced and non-model-readable.
- **Tests required:** Exact permission defaults/semantics; override precedence; forged/stale/replayed/expired approvals; always-allow intent; broker bypass attempts; protected path/file identity, symlink swap, hardlink, changed-target, special-file and TOCTOU cases; sudo denial; timeouts/cancellation; schema injection; audit quota/completeness/redaction; model log/audit type isolation.
- **Dependencies:** Milestones 000, 002, and 006B.
- **Explicit out of scope:** Real filesystem, application, shell, web, desktop, or process tools.
- **Manual verification:** Exercise a synthetic tool through allow/ask/deny, approve once and persist a matching rule, try forged approval and protected-path/sudo requests, and inspect sanitized audit correlation.
- **Definition of done:** No callable host tool exists, but every authorization, approval, execution, event, and audit security contract is proven with synthetic adapters.

### Milestone 009 — Safe read-only filesystem and system inspection tools

- **Objective:** Introduce the first real capabilities: bounded structured READ tools for allowed user locations and non-mutating system/process inspection.
- **Rationale for position:** Read-only operations provide useful tool integration with lower risk and validate the broker before execution/mutation.
- **User-visible result:** Jarvis can list/search/read bounded files and inspect ordinary system/process information, with understandable progress and typed failures.
- **Exact scope:** `filesystem.list`, metadata, bounded read by chunk/offset/lines, glob/content search; current/home/Documents/Downloads/Desktop and user-configured roots; safe system information and `process.list` inspection under READ; metadata-first behavior; tool-result context budgeting.
- **Architectural components introduced:** Filesystem read adapter, path-scope validator, system/process read adapters.
- **Important interfaces/contracts introduced:** Canonical target descriptor; read bounds; structured file/process/system results; typed `InvalidPath`, `FileTooLarge`, and limit errors.
- **Persistence/database implications:** Tool calls/audit/storage usage only; no user-file mutation. Bounded excerpts may appear in sanitized diagnostics according to policy.
- **Security implications:** Reject device files and unsafe/surprising targets; use descriptor-relative/no-follow resolution rather than stale canonical strings; enforce per-file/context/storage bounds; READ governs process inspection and never implies execution or mutation; protected installation remains readable only if policy explicitly permits but never writable.
- **Tests required:** Every read operation; boundaries/offsets/line ranges; binary/huge/sparse/special files; path traversal/symlink swaps/changed targets; configured roots; READ allow/ask/deny including process inspection; bounded model context; no mutation.
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
- **Dependencies:** Milestone 008.
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
- **Security implications:** Resolve and operate descriptor-relatively at execution; active installation path and protected inode identities are unmodifiable; reject symlink swaps, hardlinks into protected content, changed targets and special files; default ASK for MODIFY/MOVE/DELETE; no silent overwrite.
- **Tests required:** Permission composition invariants from AGENTS.md; create-existing rejection; atomicity; concurrent changes; symlink swap, hardlink, stale approval, changed-target and special-file cases; size/storage limits; partial copy/move; delete confirmation; protected installation/development clone; audit/redaction.
- **Dependencies:** Milestones 008–009.
- **Explicit out of scope:** Recursive directory deletion, arbitrary shell/scripts, process termination, network downloads.
- **Manual verification:** In a temporary allowed tree, create/copy/edit/move/delete fixtures, verify each ASK prompt and overwrite composition, exceed a limit, try a protected-installation path, and confirm precise outcomes.
- **Definition of done:** Mutations are structured, bounded, transactional where possible, correctly permissioned, recoverable where practical, and pass all specified security-sensitive tests.

### Milestone 012 — Explicit execution and destructive process operations

- **Objective:** Add the most constrained supported execution fallback: explicit scripts/executables with defined side-effect ownership, optional separately authorized network access, and guarded process termination, never unrestricted model shell access.
- **Rationale for position:** These high-risk capabilities require mature policy, broker, approvals, validation, logging, and cancellation behavior.
- **User-visible result:** Jarvis can run a specifically identified `.sh` or executable with structured arguments and can terminate an identified process only through clear authorization.
- **Exact scope:** Executable/script/interpreter validation bound to stable identity through launch; argv arrays; controlled cwd, stdin and filtered environment; no privilege gain; resource/time/output bounds; EXECUTE-owned ordinary internal side effects; process network disabled unless the request explicitly declares it and both EXECUTE and INTERNET authorize it; no conversational `jarvis-update` or protected lifecycle access; fresh process identity and termination preview; partial/destructive cancellation recording. `shell=True` is prohibited absent a future separately approved design.
- **Architectural components introduced:** Execution adapter, output limiter, process-action adapter.
- **Important interfaces/contracts introduced:** Stable executable/script/interpreter identity, argv/cwd/stdin/environment contract, explicit `network_required` declaration with a network-disabled default and EXECUTE+INTERNET composition, bounded result, and process termination requiring EXECUTE+DELETE bound to PID/start-time/executable evidence.
- **Persistence/database implications:** Sanitized bounded execution metadata/results and audit records; no credential-bearing environment persistence.
- **Security implications:** EXECUTE owns ordinary program side effects but cannot override active-installation protection, sudo/elevation denial, controlled identity/cwd/environment, limits, updater separation or privacy. The Broker does not claim to prevent arbitrary upload after network is granted; networked execution therefore has explicit scope and both permissions.
- **Tests required:** Arg/interpreter injection; executable/script replacement race; stable-identity execution; unsafe cwd/stdin/environment and secret leakage; resource/output/timeout limits; sudo/setuid/elevation attempts; protected-installation and updater invocation; EXECUTE-only network denial and EXECUTE+INTERNET authorization; permission matrices; PID reuse/start-time mismatch; EXECUTE+DELETE termination; cancellation/partial completion; audit redaction.
- **Dependencies:** Milestones 008 and 010. Milestone 011 is not a permission dependency because internal program side effects are governed by EXECUTE, not reinterpreted as Jarvis filesystem tool calls.
- **Explicit out of scope:** General interactive shell, arbitrary command strings, sudo flow, recursive deletion, desktop input automation.
- **Manual verification:** Execute a harmless fixture with spaced arguments, exercise timeout/output caps, reject sudo and command strings, terminate a disposable test process through approval, and inspect the audit trail.
- **Definition of done:** Supported execution is explicit and bounded; no unrestricted shell authority exists; destructive outcomes remain clear and auditable.

### Milestone 013A — History, FTS, and scoped retrieval

- **Objective:** Add local searchable conversation/private-note history and a strictly scoped retrieval foundation without generating new semantic or episodic memories.
- **Rationale for position:** Conversation and note data already exist; indexing and ownership filters must be proven before derived memory can consume them.
- **User-visible result:** `/history` and existing `/notes` searches support text/date/model/profile/session filters and inspect/delete/reset operations.
- **Exact scope:** SQLite FTS5 for conversations and private notes; history filters; provenance; rebuildable indexes; deterministic quota/retention; client presenters owned by the history/notes subsystems.
- **Architectural components introduced:** History retrieval/indexing service and history presenter.
- **Important interfaces/contracts introduced:** Retrieval query/result with mandatory `(profile_id, model_id)` scope and optional session; inspectability/deletion; diagnostic/audit stores are structurally non-indexable.
- **Persistence/database implications:** Add FTS tables/triggers/migrations and accounting. Conversation/note source ownership remains `(profile_id, model_id)`; active records are not pruned.
- **Security implications:** Scope filters precede ranking; diagnostic/audit/infrastructure stores cannot be indexed through this service; deletions are previewed and confirmed.
- **Tests required:** FTS/filter/search; cross-profile/model/session identifier confusion; quota/pruning/index rebuild; reset/delete participation; explicit schema/type proof diagnostics and audit are excluded.
- **Dependencies:** Milestones 006B and 007. Tool milestones are not required.
- **Explicit out of scope:** Episodic/semantic memory, context injection, embeddings, private-file ingestion and diagnostic-log retrieval.
- **Manual verification:** Search distinct conversation/note fixtures across two profiles/models/sessions, rebuild the index, delete one scoped item, and verify diagnostics never appear.
- **Definition of done:** History and notes are locally searchable, isolated, inspectable, erasable, quota-enforced and separate from operational evidence.

### Milestone 013B — Episodic/semantic memory and context recall

- **Objective:** Add locally derived episodic and semantic memory with selective, context-budget-aware recall.
- **Rationale for position:** Scoped retrieval and index isolation are already proven by 013A.
- **User-visible result:** `/memory` supports inspection/edit/delete/reset, while chat recalls only relevant bounded profile/model memories.
- **Exact scope:** Episodic summaries; durable semantic facts/preferences; provenance; local ranking; Context Builder retrieval stage and budgets; optional local embeddings only if justified by this submilestone's ExecPlan.
- **Architectural components introduced:** Memory service, episode/semantic repositories, Context Builder memory stage and `/memory` presenter.
- **Important interfaces/contracts introduced:** Memory type/provenance; initial ownership always `(profile_id, model_id)`; retrieval candidate/budget; precedence below system/policy/persona; destructive coordination.
- **Persistence/database implications:** Add memory tables/indexes/migrations with enforced quotas, deterministic pruning and rebuildable indexes.
- **Security implications:** No external embeddings; diagnostic/audit logs never enter indexes or summaries; memories cannot override higher-priority instructions; no implicit cross-model shared memory.
- **Tests required:** Profile/model isolation; selective/budgeted injection; provenance; malicious-memory precedence; reset/delete/pruning/index rebuild; log-to-memory noninterference; local-only embedding proof if enabled.
- **Dependencies:** Milestone 013A.
- **Explicit out of scope:** Cloud/vector services, web-derived hidden memories, automatic private-file ingestion, profile-shared memory and diagnostic-log retrieval.
- **Manual verification:** Create distinct derived facts in two profile/model pairs, inspect bounded recall and precedence, reset one pair, and verify no cross-scope or log-derived result.
- **Definition of done:** Derived memory is local, selective, inspectable, erasable, isolated, budgeted and separate from logs.

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
- **Dependencies:** Milestones 008 and 011. History and long-term memory are not prerequisites for explicit web execution.
- **Explicit out of scope:** Cloud AI, remote embeddings, background telemetry, browser visual automation, updater traffic.
- **Manual verification:** Against a controlled local test server, search/fetch/download within bounds, exceed limits, test redirects/denial/overwrite, inspect outbound payloads and logs, and confirm model-server network remains unnecessary.
- **Definition of done:** The provider decision is recorded in the active ExecPlan; all internet use is explicit, bounded, policy-controlled, auditable, redacted, and independent of local inference; switching providers does not require Agent Engine or Tool Broker changes.

### Milestone 015 — Cleanup and storage lifecycle

- **Objective:** Provide deterministic selective cleanup and retention behavior for every data category introduced so far.
- **Rationale for position:** All principal data categories now exist, so cleanup can describe and remove them accurately without an ambiguous “clear all.”
- **User-visible result:** `jarvis-clear` selectively cleans notes, conversations, diagnostics, caches, downloads, learning data and inactive runtime artifacts. Slash-command presenters already arrived with their owning subsystems.
- **Exact scope:** Cleanup profile/model/category/age selection; previews/confirmations; retention/rotation controls; quota warnings; interrupted-cleanup recovery; database maintenance; concise typed errors. Do not reimplement `/permissions`, `/history`, `/memory`, `/notes`, `/learning`, `/model`, `/reasoning`, `/context`, `/status`, `/server` or `/logs` here.
- **Architectural components introduced:** Cleanup/retention service, consolidated storage-usage service and `jarvis-clear` presenter.
- **Important interfaces/contracts introduced:** Cleanup plan/preview/result; eligible-versus-active data contract; category-specific reset semantics; human-only log rendering route.
- **Persistence/database implications:** Accurate storage usage, retention timestamps, pruning records; active-session data is never pruned while written; database vacuum/maintenance is safe and explicit.
- **Security implications:** Destructive cleanup is scoped and confirmed; raw logs may be rendered to the human client but never returned to model context; secrets remain redacted; failures do not imply deletion succeeded.
- **Tests required:** Cleanup category/scope/age; active-write/reservation protection; quota rotation/refusal/warnings; ENOSPC; interruption recovery; profile/model isolation; exact chat-diagnostic versus infrastructure/audit category handling; log human/model separation.
- **Dependencies:** Milestones 006A, 007, 008, 011, 013B, and 014.
- **Explicit out of scope:** Rich TUI, desktop/Wayland, systemd autostart, updater/distribution.
- **Manual verification:** Fill temporary quota fixtures, preview and clean one category/profile/model/range, confirm unrelated/active/reserved data remain, recover an interrupted cleanup, and inspect human-only log routing.
- **Definition of done:** Cleanup and lifecycle behavior are complete, deterministic and safe without being the first enforcement point for any quota.

### Milestone 016 — Rich TUI client

- **Objective:** Build the installed TUI as a presentation-only client of the existing Core protocol.
- **Rationale for position:** Stable streaming, approvals, history, permissions, logging, model state, and the M006C installed dispatcher now exist, preventing the TUI from inventing a second brain or a second installation architecture.
- **User-visible result:** A polished profile-themed terminal interface provides streamed Markdown chat, tool progress/confirmations, selectors, history, permissions, debugging, and TUI-local keyboard shortcuts. Once the TUI passes its stability gate, the existing physical `jarvis` dispatcher opens it for bare interactive use; one-shot commands remain non-TUI. Dynamic physical profile aliases use the same rule once M019A later materializes them.
- **Exact scope:** TUI layout/state; streaming rendering; profile/model/learning/reasoning/context indicators; themes/colors/waiting/goodbye messages; debug panel; permission editor; history/model selection; reconnection/cancellation; accessibility and terminal degradation; an explicit stability gate followed by changing only the existing dispatcher's bare interactive target to the TUI; preservation of argument-bearing one-shot dispatch outside the TUI; preservation of the simple interactive CLI as an independent fallback, optionally exposed by a future explicit flag such as `--simple`.
- **Architectural components introduced:** TUI client/presenters only.
- **Important interfaces/contracts introduced:** Client-side view models; event-to-view mapping; profile appearance rendering; approval responsiveness; stable default-client selection and explicit invocation-mode dispatch. No Core business interface is duplicated.
- **Persistence/database implications:** Uses Core configuration APIs; no direct database access and no TUI-owned authoritative data.
- **Security implications:** TUI cannot bypass broker/policy/profile/runtime manager; secrets in debug rendering are redacted; confirmation intent is unambiguous; terminal escape content is sanitized.
- **Tests required:** Event rendering/order; reconnect/cancel; approval UX; profile theme isolation; terminal escape/Markdown sanitization; fake-Core integration; stability-gate behavior; bare-command TUI dispatch after stability; argument-bearing non-TUI one-shot dispatch; simple CLI fallback; no direct repository imports.
- **Dependencies:** Milestones 002, 006B, 006C, 008, 013B, and 015.
- **Explicit out of scope:** Voice, Desktop App, desktop automation, changes to agent reasoning, separate TUI persistence.
- **Manual verification:** Run two themed profiles, stream chat/tools, approve/deny actions, browse history/edit permissions, reconnect after Core restart, and use the debug panel without model log exposure; then pass the documented stability gate, confirm the existing bare `jarvis` command opens the TUI without reinstalling or replacing its dispatcher, confirm argument-bearing invocations remain non-TUI one-shots, and confirm the simple CLI fallback remains usable.
- **Definition of done:** TUI feature goals and the documented stability gate are met through the same IPC/Core; the M006C dispatcher changes only its bare interactive target to the stable TUI, one-shot commands remain non-TUI, the simple CLI remains an independent fallback, and all profile/policy/isolation behavior matches CLI behavior.

### Milestone 017 — Wayland desktop and screen capabilities

- **Objective:** Add compositor-neutral desktop context and screen-reading capabilities through portals/D-Bus/accessibility/adapters, with all processing local.
- **Rationale for position:** SCREEN permissions and tool infrastructure are mature; structured application launch already exists; visual access is added only after safer mechanisms.
- **User-visible result:** On supported Wayland desktops, Jarvis can request authorized screen/context information and return structured local observations with explicit portal consent where required.
- **Exact scope:** Desktop adapter interface; capability detection; XDG Desktop Portal capture; D-Bus/accessibility integrations where appropriate for screen/context acquisition; GNOME/KDE/wlroots adapter strategy; local screen-understanding provider abstraction; timeouts; ephemeral screenshot lifecycle; structured screen results. A concrete local VLM is included only if this milestone's ExecPlan demonstrates it is necessary. SCREEN grants screen/context access only and provides no keyboard or mouse authority.
- **Architectural components introduced:** Desktop adapter registry, screen-capture tool, local screen-understanding provider.
- **Important interfaces/contracts introduced:** Desktop capability/consent result; screenshot provenance/lifetime; local processing guarantee; structured observation/bounds; fallback ordering.
- **Persistence/database implications:** Screenshots are ephemeral by default and quota-controlled if explicitly retained; audit contains sanitized metadata, not unnecessary images.
- **Security implications:** SCREEN policy and compositor consent both apply; screenshots never reach external AI; sensitive image retention is minimized; no X11-only bypass; no keyboard/mouse automation or global input authority exists. Any future input automation requires a separate capability, explicit permission category, security model, and roadmap authorization.
- **Tests required:** Adapter selection; portal denial/cancel; SCREEN policy; time/size/quota limits; image lifecycle; no-network proof for processing; mocked GNOME/KDE/wlroots cases; fallback behavior; provider-contract tests without requiring a concrete VLM.
- **Dependencies:** Milestone 008. Application launch, web access and cleanup UI are not prerequisites for screen/context acquisition.
- **Explicit out of scope:** Jarvis Desktop App, Voice, all keyboard/mouse automation and global input control, X11-only global capture, cloud vision.
- **Manual verification:** On available Wayland environments or controlled mocks, inspect capability status, grant/deny portal capture, process a fixture locally, verify cleanup, and monitor that no network payload contains screenshots.
- **Definition of done:** Supported desktop/screen operations are adapter-based, local, policy/portal-controlled, bounded, audited, and compositor-neutral by contract.

### Milestone 018A — Installation management, health, diagnostics, and update checks

- **Objective:** Complete `jarvis-manage` for installation health/repair, runtime diagnostics, model/runtime settings, daemon status/version, and update checking without update application.
- **Rationale for position:** The minimum management contract from Milestone 004 and permanent installation/activation foundation from M006C can now expand over mature Core, storage, aliases and diagnostics.
- **User-visible result:** Users can inspect and non-destructively repair their user-local installation, manage runtime/model directories, export redacted diagnostics, and enable/disable transparent update checks.
- **Exact scope:** Full management menu except per-profile autostart; health findings and non-destructive repair plans for the M006C application environment, fixed dispatchers, manifest and systemd-user socket/service foundation, while still excluding dynamic physical profile-command exposure; Core status/version; redacted diagnostics export; installation-scoped update source/settings/checks enabled by default. Core exposes no update-application operation.
- **Architectural components introduced:** Installation manager, health/repair service, diagnostic exporter and narrowly scoped update-check service.
- **Important interfaces/contracts introduced:** Health finding/repair plan; installation/profile ownership boundary; update-check metadata/privacy contract; checking-versus-application authority separation.
- **Persistence/database implications:** Installation settings and health/check timestamps remain separate from profiles; sanitized diagnostics use their correct XDG roots and quotas.
- **Security implications:** User-only/no root; repairs cannot mutate history unexpectedly; update checks transmit only minimal version/repository data, are not profile INTERNET tools and cannot acquire updater authority; active installation remains protected from conversational tools.
- **Tests required:** Management ownership boundaries; model/runtime setting migration from minimum client; health/repair excluding physical alias exposure; checks disabled/enabled/privacy/failure; proof Core has no update-apply operation; diagnostics redaction/quota and human-only routing; no-root/user-local paths.
- **Dependencies:** Milestones 002, 003, 004, 005, 006A, and 006C. Cleanup, TUI and desktop are not required.
- **Explicit out of scope:** Per-profile autostart, installation creation/mutation, final installer/uninstaller and purge, applying updates, release packaging and machine-wide services.
- **Manual verification:** Inspect status in temporary state, inspect a logical alias mapping, change installation runtime paths, run a controlled update check, attempt and fail to find any Core update-application operation, and review redacted diagnostics.
- **Definition of done:** Installation management is safe and repairable; update checking is transparent, minimal and incapable of applying an update.

### Milestone 018B — Per-profile autostart under one Core owner

- **Objective:** Add user-session autostart without creating competing Core or runtime owners.
- **Rationale for position:** M006C already supplies the permanent systemd-user socket/service topology and single-Core activation; runtime recovery and M018A management diagnostics are now mature enough to add profile model desired-state reconciliation at login.
- **User-visible result:** Users can enable `Start with computer` per profile; one user-level Core starts requested last-valid profile models and reports missing models without substitution.
- **Exact scope:** Extend the M006C systemd-user Core activation architecture with login/session triggering for profile-owned desired autostart state; Core-side reconciliation or a thin activation request to that Core; last-valid-model/no-substitution behavior; login/logout/restart recovery; status/repair integration. Do not introduce another Core service, socket owner or runtime manager.
- **Architectural components introduced:** Per-profile model-autostart desired-state reconciler and login/session activation integration atop the existing M006C Core service.
- **Important interfaces/contracts introduced:** Idempotent desired-state reconciliation through the already authoritative one-Core topology; last-valid-model failure result; Core activation alone starts no models; runtime startup does not consume first-run learning state.
- **Persistence/database implications:** Autostart preference remains profile-owned; systemd/runtime artifacts are user-local and ephemeral where appropriate.
- **Security implications:** No root; unit files use known structured arguments; no per-profile Core units; stale activations cannot kill unrelated processes or duplicate runtimes.
- **Tests required:** Login/session trigger and reconciliation idempotency; simultaneous/duplicate activation through the M006C socket/service; proof no alternate Core/socket topology is created; proof ordinary Core activation without opted-in desired state starts no model; multiple autostart profiles under one owner; missing model; stale runtime/PID reuse; logout/restart; learning non-activation; no-root paths.
- **Dependencies:** Milestones 005, 006C, and 018A.
- **Explicit out of scope:** Update application, installation creation/mutation, final installer/uninstaller and purge, machine-wide services.
- **Manual verification:** Enable two profiles in disposable user-service state, simulate login twice, confirm one Core and one runtime per profile, then simulate a missing model and inspect the recorded failure.
- **Definition of done:** Autostart is per-profile desired state coordinated by exactly one recoverable user-level Core.

### Milestone 019A — Packaging, installer, and uninstaller

- **Objective:** Complete and distribution-harden the permanent M006C user-local installation architecture with reproducible release packaging, final dynamic command exposure, and uninstall/purge separation without implementing update application.
- **Rationale for position:** The M006C private environment, fixed dispatchers, systemd activation, identity/manifest and repair foundation already provide real installation. Distribution can now preserve and upgrade that architecture while incorporating every intervening command, client, data, service and XDG contract.
- **User-visible result:** Ordinary users can install every required command/TUI/service asset without root and uninstall binaries while preserving data unless purge is separately confirmed.
- **Exact scope:** Release packaging; final dependency/license inventory; final installer and uninstaller extending the M006C user-local installer/environment; final installed manifest and distribution completeness; upgrade/preservation of fixed commands, PATH reconciliation, systemd-user assets and later assets introduced by intervening milestones; dynamic physical profile-command launcher/symlink/wrapper strategy; external alias collision handling; alias materialization, reconciliation/repair, rename/delete and uninstall cleanup; desktop entry and `jarvis-clear` inclusion; uninstall versus purge; supported Debian/Ubuntu release validation; fresh-install migrations; interrupted install/uninstall recovery; protected-install identity completion.
- **Architectural components introduced:** Distribution/release packager, completed installer/installed manifest and uninstaller extending the M006C foundation, plus dynamic profile-command materializer/reconciler.
- **Important interfaces/contracts introduced:** Final installed-file manifest/identity and foundation-upgrade contract; preserved-data contract; uninstall/purge confirmation; dynamic alias materialization/reconciliation lifecycle; compatibility metadata consumed later by the updater.
- **Persistence/database implications:** Preserve XDG profiles, conversations, memories, notes and settings on normal uninstall; purge is separate and explicit.
- **Security implications:** Never `curl | bash`; no root by default; installed files/update infrastructure become protected identities; dependencies are maintained, non-telemetric and GPL-compatible.
- **Tests required:** Fresh install and upgrade from the M006C foundation without replacing its architecture or losing state; all commands/help/default-client dispatch; fixed PATH/service/manifest reconciliation; physical profile-command materialization, collision, reconciliation, rename/delete cleanup and uninstall behavior; protected-file and hardlink identity; uninstall preserve/purge; interrupted install/uninstall recovery; Ubuntu/Debian matrix; license inventory; no source-tree or real-home mutation in ordinary tests.
- **Dependencies:** All milestones through 018B; Voice and Desktop App remain excluded.
- **Explicit out of scope:** Applying updates and choosing signing technology/trust lifecycle.
- **Manual verification:** Install in disposable supported environments, run command/Core/chat smoke tests, uninstall preserving data, reinstall and verify recovery, then separately verify explicit purge.
- **Definition of done:** Reproducible user-local packages consume, preserve, upgrade and complete the M006C foundation; the complete in-scope product installs and uninstalls safely with final distribution assets, dynamic alias lifecycle and protected-install identity.

### Milestone 019B — Authenticated updater and release validation

- **Objective:** Implement the only authorized application-update path with compatibility, rollback, integrity and cryptographic authenticity validation.
- **Rationale for position:** M006C established the permanent installation foundation, and the final installed manifest/trust boundary from 019A plus every migration/data-preservation contract now exist. Update authority remains deliberately separate and late.
- **User-visible result:** The separately invoked `jarvis-update` can update a stable release recoverably while Core and conversational tools remain unable to apply updates.
- **Exact scope:** Release query/download; compatibility; integrity and authenticity verification; exclusive updater authority/lock; application; rollback; post-check; migrations across supported versions. The exact signing technology and trust-material lifecycle remain the Milestone 019 family decision gate and are selected only in this submilestone's active ExecPlan.
- **Architectural components introduced:** Updater, release validator, rollback and post-update validator.
- **Important interfaces/contracts introduced:** Separate integrity/authenticity contracts rooted in installed trust information; compatibility/migration boundary; exclusive external updater lock; preserved-data and recoverable-failure contract; official configured release source.
- **Persistence/database implications:** Back up and transactionally migrate as designed; preserve all user XDG data and restore coherently on failure.
- **Security implications:** A same-source checksum is insufficient authenticity; only separately invoked `jarvis-update` mutates installed files; Core exposes no apply API; conversational execution cannot invoke updater authority; no root by default.
- **Tests required:** Upgrade/downgrade rejection/rollback; corrupt/untrusted/incompatible artifacts; attacker replacement of artifact plus adjacent checksum; trusted-material update/failure cases defined by the deferred technology; interrupted/concurrent update; data preservation/migrations; Core no-apply proof; conversational updater denial; installation protection before/after update.
- **Dependencies:** Milestone 019A.
- **Explicit out of scope:** Resolving signing technology before this submilestone's ExecPlan, cloud inference, telemetry, silent in-chat updates, Voice and Desktop App.
- **Manual verification:** In disposable installations, update through a controlled authenticated release, confirm adjacent-checksum replacement fails, simulate interruption/rollback, verify data and commands, and confirm Core/conversation paths cannot apply updates.
- **Definition of done:** The deferred signing decision is recorded in the active 019B ExecPlan and a validated authenticated release updates only through `jarvis-update` with recoverable data preservation.

## Roadmap-wide release gates

Every milestone must satisfy these gates in addition to its own definition of done:

- Its ExecPlan exists before implementation, remains current, and records deviations and decisions.
- Automated tests run only against temporary homes/XDG roots, test databases, fake providers, fake GGUF fixtures, controlled local servers, or disposable environments as appropriate.
- New dependencies have documented maintenance, network/telemetry, installation-burden, and GPL-compatibility review.
- New user-facing strings are localization-ready; internal code, schemas, events, tests, and documentation are English.
- Security-sensitive operations use typed inputs/results/errors, bounded execution, centralized policy where applicable, sanitized diagnostics, and auditable correlation IDs.
- Every subsystem that begins producing data in a milestone must enforce its applicable quota, accounting, reservation and active-write rules in that same milestone; Milestone 015 is presentation and lifecycle consolidation, not deferred enforcement.
- Every new profile-owned or profile/model-owned store must use composite isolation keys and register reset/delete preview, quiescence and cleanup behavior with the destructive-operation coordinator in the milestone that introduces it.
- Every real client remains presentation-only over client-neutral Core IPC and has an automated boundary test preventing direct repository/database access.
- Path-sensitive or executable capabilities must bind authorization to execution-time identity and test link swaps, changed targets, protected identities and replacement races appropriate to their risk.
- No milestone silently widens network access, permissions, data sharing, installation scope, model context, or deletion behavior.
- Documentation and the dependency graph are updated when a discovery changes later milestone assumptions.
