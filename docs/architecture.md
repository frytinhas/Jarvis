# Jarvis-CLI Architecture

## Architectural rule

Jarvis-CLI is a user-local, fully local-inference assistant built around one authority boundary:

```text
Client -> local IPC -> Jarvis Core -> Policy Engine -> Tool Broker -> Linux host
                              |
                              +-> Runtime Manager -> LLM Provider -> localhost llama-server -> GGUF
```

The LLM plans and converses. It does not own OS authority. Core validates proposed actions, the Policy Engine decides `allow`, `ask`, or `deny`, the Tool Broker performs only registered typed capabilities, and logging/audit records the result. No client or model may bypass this flow.

## Clients and IPC

The simple CLI and rich TUI are presentation clients. They render streams, collect approval decisions, issue slash/configuration commands, and show human-facing errors and logging events. They do not run an agent loop, access the database directly, manage model processes, or execute tools.

Client dispatch depends on invocation mode and TUI maturity. M006C introduces the permanent
physical `jarvis` dispatcher; before the rich TUI is stable, bare `jarvis` opens the simple
interactive CLI. After the TUI passes its M016 stability gate, the same dispatcher opens the TUI
by default without replacing the installation architecture. Invocations containing a
natural-language request remain non-TUI one-shot commands in both phases. The simple interactive
CLI remains an independent client and fallback; a future explicit option such as `--simple` may
select it after the TUI becomes the default. Dynamic bare profile commands do not exist until
M019A materializes them, after which they follow the same interactive-versus-one-shot dispatch
rule.

Clients connect to Jarvis Core over a user-only Unix domain socket using bounded, structured, versioned serialization (never pickle). Core/IPC exists before any real configuration or chat client; no client ever receives a temporary direct repository/database path. Operations and payloads are client-neutral, and version plus capability negotiation lets different client types degrade explicitly.

Each accepted request emits monotonically sequenced events and exactly one terminal completion or error. Approval requests expire and bind to the validated originating request/tool call. Disconnect does not imply cancellation: Core retains accepted work until a terminal state or valid explicit cancellation. Reconnect/replay behavior is bounded and negotiated; without replay, Core reports authoritative request status rather than asking a client to infer it.

M006B implements the first chat presenter through `python -m jarvis.cli`. Bare package invocation
is interactive, while an argument-bearing invocation is one-shot; `--profile-alias` is resolved by
Core. The client renders ordered deltas, learning state, visible logging, cancellation, and bounded
reconnect/replay. It intercepts the M006B slash-command set before chat submission. `/clear` marks
the next Core chat submission as a new session without deleting history, and `/logs` consumes only
the dedicated human diagnostic-summary result. The presenter has no repository, SQLite, provider,
or RuntimeManager imports.

M006C installs this presenter in a Jarvis-managed private production virtual environment and
exposes it as canonical `jarvis`, along with the fixed management/configuration/help dispatchers
appropriate to that milestone. Normal installed use is independent of the source checkout and an
activated development environment, does not depend on `pipx`, and neither installs into nor mutates
global/system Python. Fixed dispatchers are collision-safe and never overwrite or claim unrelated
executables or PATH entries.

The M006C manifest under XDG state records a stable installation UUID, distribution/wheel and
private-interpreter identity, and exact mode/hash/inode evidence for fixed dispatchers and user-unit
assets. Matching assets are idempotent, absent owned assets may be restored, and altered, linked,
foreign, or shadowed targets fail closed. The private venv and every manifest asset extend active
installation protection.

This same boundary is the compatibility point for future Voice and Jarvis Desktop App clients. Those future products are not part of the current implementation roadmap and must reuse Core rather than create separate agent brains.

## Jarvis Core (`jarvisd`)

Core owns all product state and orchestration: profiles, configuration, models, runtimes, sessions, the Agent Engine, context construction, memory, policy, tools, persistence, logging, audit, and runtime coordination. Exactly one Core process owns a user's Jarvis XDG state and Core lock at a time; multiple clients and profile runtimes share it. In production, systemd owns the listening socket while the single Core owns accepted IPC work and all application services. Core exposes typed application operations over IPC and emits meaningful state events; it does not own CLI/TUI rendering.

M006C establishes true systemd-user socket activation for installed use. systemd creates and
listens on the user-only XDG-runtime Unix socket, activates one foreground `jarvisd`, and passes the
listening descriptor to it. Core validates the inherited descriptor's activation contract, socket
type, expected address and ownership/access properties before adoption; it neither unlinks nor
rebinds the systemd-owned path. A self-bound foreground Core mode may remain for development and
isolated tests. The two modes never compete for socket ownership. Client connection/readiness is
deterministic and reports typed activation failures; launchers never implement `jarvisd &` or a
second Core lifecycle. The socket/service assets live in the user systemd unit search path and are
owned and tracked by the installation manifest; `jarvisd` is infrastructure, not a normal user
workflow.

Core is the trust boundary between untrusted/model-proposed content and host capabilities. Subsystems communicate through typed contracts and typed errors rather than reaching through layers to mutate each other’s storage.

## Profiles and configuration ownership

A profile is the primary user-facing identity and isolation boundary. Stable internal `profile_id` values—not display names or command aliases—own persona, profile context, selected model, per-model runtime settings, permissions, appearance, visible logging mode, messages, learning state, startup behavior, conversations, and other profile data.

The permanent `jarvis` profile always exists, cannot be renamed at the command level or deleted, and is the configuration template for new profiles. Cloning copies an explicit allowlist of Jarvis's current configuration. Model selection/settings join that allowlist only after the Model Registry exists; existing profiles are not backfilled. Conversations, private model notes, memories, learning history/state, chat logs, and diagnostic session history always start empty. A missing inherited model is unavailable and never silently replaced.

Creation and reset have different sources: creation clones Jarvis's current configurable state, while reset restores centrally defined, versioned product defaults. Reset and deletion run through one destructive-operation coordinator that previews exact categories, quiesces or explicitly cancels profile sessions/generations/runtimes, invokes every registered profile-owned store, and never reports partial cleanup as success. M003 changes only the persistent logical alias with the profile transaction; M019A coordinates dynamic physical profile-command cleanup once those aliases exist. Profile reset removes owned chat diagnostics while retaining a sanitized audit record of the reset.

Settings that logically affect a profile remain profile-owned. Settings that describe the installation—model search directories, llama.cpp path, installed commands, Core management, update source/checking, health, and repair—belong to installation management. A minimum management contract for model directories and the runtime path exists before model runtime configuration; the full `jarvis-manage` client comes later. Defaults are centralized, versioned, and resettable at setting, section, and profile levels.

## Profile command aliases

Every non-default profile has a deterministic lowercase ASCII/hyphen logical alias derived from its display name. M001 persists it, and M003 resolves it through Core to a stable `profile_id`; aliases never become ownership keys.

M003 creates no profile command executable, launcher, symlink, wrapper, filesystem registry, or PATH entry, and performs no external PATH collision check. M006B supplies the runnable/testable development/package mechanism: `python -m jarvis.cli` for the default profile and `python -m jarvis.cli --profile-alias <alias> [request]` after Core resolution. M006C then exposes the canonical physical `jarvis` and other fixed commands appropriate to its production foundation, with collision safety for each fixed dispatcher; logical profiles remain available through `jarvis --profile-alias <alias>`. M019A owns only dynamic physical profile-command materialization, external alias collisions, alias reconciliation/repair, rename/delete cleanup, and uninstall cleanup. Reserved command names and logical alias collisions remain enforced by the profile service. Help through a physically exposed `jarvis` or later profile alias is client-side and does not start a model.

## Persistence and local storage

SQLite is the initial authoritative database, evolved only through migrations. It stores profile/model associations, sessions/messages, learning, memories, private notes, settings, approvals, tool calls, audit/runtime events, and storage accounting as those features are introduced. SQLite FTS5 supports local text search; optional future embeddings must also be local.

Storage follows XDG separation:

- configuration in XDG config;
- durable application/profile data in XDG data;
- diagnostics and operational state in XDG state;
- rebuildable data in XDG cache;
- sockets, locks, and PIDs in XDG runtime.

Private data is initially keyed by `(profile_id, model_id)`: conversations, learning state/history, private notes, episodic memory, semantic memory, and model chat diagnostics. Conversations and derived episodes also retain session provenance. No implicit cross-model shared-memory class exists. Configurable quotas and deterministic retention prevent unbounded storage. Quota/default/accounting/reservation primitives exist in the foundation, and each writer enforces its limits from introduction. Active or reserved records are not pruned while being written. Chat reserves enough capacity for a minimum diagnostic record before generation and fails safely when it cannot do so. Tests replace every XDG root and database with temporary equivalents.

## Model registry

The installation-level model registry scans user-configured directories for user-owned GGUF files. It canonicalizes and deduplicates paths, reads bounded metadata where practical, tracks size and missing state, and assigns a stable local `model_id` without hashing entire multi-gigabyte files on every startup. It never downloads, moves, renames, or modifies model files.

Profiles reference registry models through profile/model associations. Reasoning, context size, sampling, resource settings, and timeouts are per profile/model and represented as validated structured values, not free-form shell fragments.

## LLM provider and runtime manager

The provider interface hides inference-backend details from the Agent Engine. The initial `LlamaCppProvider` starts/stops/health-checks/chats with `llama-server` using structured arguments and localhost transport. Future local providers can implement the same contract without leaking llama.cpp assumptions into the rest of Core.

The Runtime Manager owns `STARTING`, `READY`, `BUSY`, `ERROR`, `STOPPING`, and `STOPPED` transitions, race-safe local endpoint ownership, health, timeouts, and quota-bounded sanitized server diagnostics. Runtime ID, PID start time/executable identity, lock, owned endpoint, and expected health evidence enforce at most one active model server per profile and recover stale/orphan artifacts without killing an unrelated reused PID. A configured context of zero means Auto: after authenticated loopback readiness the provider retains only the positive bounded effective context needed by Context Builder, never the raw `/props` payload. Different profiles may concurrently run the same GGUF, but their runtime and persistent state remain independent.

M005 implements this boundary with authenticated IPv4 loopback HTTP only. Core constructs a
structured, offline `llama-server` argv from typed M004 configuration, passes descriptor-bound
revalidated model and private API-key files, filters the environment, owns the process group, and accepts READY only after
process/executable, listener-inode, endpoint, and authenticated-health evidence agree. Runtime
capacity is installation-wide, revisioned, configurable from 1–16, and defaults to two. Admission
is bounded FIFO and never stops an existing profile to make room. Only metadata events and
last-ready association evidence persist; tokens, handles, ports, locks, queues, and raw output do
not. Whole-profile reset/delete and Core shutdown quiesce owned runtimes before persistent cleanup.

Initially, a deterministic FIFO coordinator serializes generations for one profile/runtime while allowing different profiles to generate concurrently. A model switch waits for the active generation or explicitly cancels and records it, stops the old runtime completely, and only then starts the replacement.

## Agent Engine and Context Builder

The Agent Engine coordinates a turn: resolve profile/model/session, reserve bounded diagnostic
capacity, transactionally activate first-run learning, ask the centralized Context Builder for a
bounded request, enter the profile FIFO coordinator, invoke the provider, persist conversation and
diagnostics, and stream one ordered terminal outcome over IPC. M006A treats tool-looking model text
as ordinary assistant text and introduces no host capability path.

The Context Builder is the only authority for assembling model input. It orders and budgets documented product protocol/tool instructions, profile persona/context, explicit user-configured behavioral instructions, relevant capability/permission descriptions, model-private notes, selectively retrieved semantic/episodic memory, workspace/tool context, recent conversation, and the current request. Other modules contribute typed, bounded candidates with identifiable provenance; they do not append arbitrary prompt text.

In M006A its implemented order is exactly `CORE_PROTOCOL`, `PROFILE_PERSONA`, `PROFILE_CONTEXT`,
`USER_CONFIGURED`, `TECHNICAL_FORMATTING`, `CONVERSATION`, and `USER_REQUEST`. Oldest conversation
is dropped first. Persona, profile context, and the current request are mandatory and cause a typed
pre-generation overflow error rather than silent truncation. Notes, memory, workspace, tools,
permission descriptions, diagnostics, audit records, and raw logs are not M006A inputs; the broader
candidate classes above belong only to their later owning milestones.

Every persistent or system-level Jarvis-owned prompt component must identify its source and purpose. Product-required components are limited to documented protocol/tool instructions and required technical formatting/tool-use instructions; behavioral components come from the selected profile/model configuration. There is no undocumented provider-policy prompt layer.

Slash commands are routed by the client/Core command system and are never blindly sent to the model. Persona and persistent profile context are profile-owned. Provider/model switches do not import another profile’s identity.

## Model-content neutrality and execution authority

For local inference, Jarvis does not impose a hidden behavioral policy derived from OpenAI,
Anthropic, Google, Meta, Microsoft or another model provider. It does not silently instruct local
models to refuse harmful, cybersecurity or controversial topics, follow a hosted provider's rules,
or otherwise adopt third-party acceptable-use policy. It also does not censor, rewrite, suppress,
replace with a refusal or prevent a local-model response solely because a third-party/provider
content policy disfavors the response's subject matter, purpose, opinion or text. Cybersecurity,
security research, reverse engineering, exploit analysis and malware analysis are not separately
forbidden topics at the Jarvis architecture layer.

The generated-content behavior of a local model comes from its training and native behavior plus
the selected profile persona/context and explicit user-configured model/prompt settings. Users may
deliberately configure behavioral restrictions, and Jarvis neither removes model-native alignment
nor guarantees prompt compliance. The requirement is that Jarvis does not secretly add another
provider-specific behavioral layer. Subject to the selected model and explicit configuration, the
model may generate arbitrary text without first obtaining host-capability authorization.

```text
model output freedom != host execution authority

User -> profile persona/context -> local model -> generated text/tool request
                                                   |
                                                   v
                                      Tool Broker / Policy Engine
                                                   |
                                      capability authorization
                                                   |
                                                   v
                                        host/external capability
```

Generated text does not itself require capability authorization. A proposed real side effect does:
it crosses the Broker/Policy boundary and is decided from the validated operation, profile
capability state and explicit architectural integrity constraints. Installation and updater
protection, IPC/runtime integrity, profile isolation, permission and confirmation enforcement,
filesystem/process/tool authority, secrets, privacy, network controls, resource bounds, executable
identity and diagnostic/audit isolation remain absolute where documented. They constrain technical
authority rather than model subject matter, and a profile `allow` cannot override them.

The provider abstraction is behaviorally neutral and must not assume identical policies across
providers. A future optional external provider may independently enforce server-side behavior that
Jarvis cannot remove; that behavior must be distinguished from policy imposed by Jarvis itself.
This clarification adds no external-provider design.

## Learning, memory, and private notes

The first user-facing Agent Engine chat transaction for every `(profile_id, model_id)` pair enters a visibly active Learning Session, with activation committed before generation. Discovery, server startup, health checks and autostart do not consume first-run state. Learning start, finish, status, and destructive reset are explicit operations and do not alter tool permissions.

Memory layers remain distinct:

- working memory is the bounded active-turn context;
- conversation history is persisted by profile/model/session;
- episodic memory summarizes relevant prior sessions and is initially profile/model scoped;
- semantic memory stores durable locally derived facts/preferences and is initially profile/model scoped;
- profile context and persona belong to the profile;
- private notes belong to a profile/model pair;
- diagnostic logs are operational evidence, not memory.

Memory and notes are local, inspectable, erasable, selectively retrieved, and scope-filtered before ranking. Any future profile-shared memory requires an explicit separate design. Diagnostic and audit logs are never searched, summarized, or injected as model context.

## Policy Engine

The Policy Engine is the single authority for capability decisions; it is not a content-moderation engine or an LLM-content classifier. Profile policies use `allow`, `ask`, and `deny`; tool-specific rules may refine but not bypass category rules. Decisions derive from the validated capability/operation, configured permission state and separately documented architectural integrity constraints—not semantic judgment about the model's topic, purpose, opinion or generated text. The defaults and semantics in `AGENTS.md` are product contracts, including CREATE not implying overwrite, COPY plus MODIFY for an overwrite, ASK for DELETE/MODIFY/MOVE, and denial of sudo. Process inspection uses READ. Process termination requires EXECUTE plus DELETE and binds to fresh PID/start-time/executable identity.

The model cannot change effective permissions. A capability configured as `allow` is not silently converted to `ask` or `deny` because a provider-specific content policy disfavors the subject matter. When a decision is `ask`, Core sends the human client the validated action, canonical target, concise consequence, and relevant arguments. Allow-once is bound to that request; persistent matching permission changes require explicit human intent and are audited. Structurally forbidden operations remain forbidden under documented integrity constraints even when a category is `allow`; that is host protection, not semantic moderation.

## Tool Broker

The Tool Broker is the sole execution path for host capabilities. It owns the typed tool registry, input/result validation, target resolution, policy check, approval binding, timeout/cancellation, bounded execution, structured error/result, and audit lifecycle. A canonical path string is not durable execution authority: path-sensitive adapters re-resolve descriptor-relatively, use appropriate no-follow/link checks, compare expected identity/version, and reject symlink swaps, protected hardlinks, changed targets and unexpected special files. Protected installation identity includes existing file identity, not only path spelling.

Adapters implement namespaces such as `filesystem.*`, `system.*`, `process.*`, `apps.*`, `shell.*`, `web.*`, and `desktop.*`. Structured operations are preferred. Shell support is a constrained fallback using explicit executable/script/interpreter identities and argument arrays, not unrestricted arbitrary command strings. Validation and launch bind to the same stable identity; cwd, stdin, environment, resources, time and output are controlled.

EXECUTE authorizes ordinary internal side effects of the selected program; those effects are not reclassified as separate Jarvis MODIFY/MOVE/DELETE calls. Absolute boundaries still apply: no sudo/elevation, no active-installation mutation, no conversational updater/lifecycle authority, and no secret environment inheritance. Process network is disabled unless an execution request explicitly declares it and both EXECUTE and INTERNET authorize it; omission keeps networking disabled even if both profile categories are `allow`. Because unrestricted process networking can enable arbitrary upload, the Broker does not claim data-flow control it cannot enforce. A tool adapter cannot authorize itself or be called directly by the model.

## Logging and audit

Every chat session produces a sufficient complete local diagnostic record regardless of visible logging mode. Profile/model chat diagnostics, installation/infrastructure diagnostics, and audit records are separate stores. Central redaction runs before persistence and rendering and removes credentials, tokens, cookies, private keys, authorization headers, secret environment values, and credentials in URLs. Events correlate profile, model, runtime, session, request, turn, and tool call identifiers while avoiding unnecessary large content blobs; bounded excerpts include explicit truncation metadata.

Profile-visible modes (`full`, `server-essential`, `essential`, `essential-minimum`, and `none`) only control client rendering. `none` still shows approvals, errors, destructive confirmations, and critical failures. Audit records permission and tool outcomes. Human clients access diagnostics through dedicated client-only IPC result types that the Context Builder cannot consume; neither diagnostic nor audit stores are model-memory sources.

## Network and desktop boundaries

The LLM runtime does not need unrestricted internet. Core provides explicit brokered `web.search`, `web.fetch`, and `web.download` capabilities under INTERNET policy, outbound-data rules, timeouts, redirects, size limits, cache accounting, and redacted audit. `web.search` depends on a provider interface owned by the network subsystem; normalized search requests/results keep the concrete backend from changing the Agent Engine or Tool Broker. The provider, credential model, query-disclosure policy, and fallback behavior remain a Milestone 014 decision. No conversation, profile context, note, memory, screenshot, or private file is silently sent externally, and no cloud AI is required.

Desktop support is Wayland-oriented and adapter-based. It prefers desktop entries/XDG, D-Bus, portals, and accessibility APIs across GNOME, KDE, and wlroots rather than assuming X11 or visual clicking. SCREEN means screen/context access only: capture requires both SCREEN policy and compositor/portal consent, is locally processed through a screen-understanding provider abstraction, and yields bounded structured observations. A concrete local VLM is not required unless the active Milestone 017 ExecPlan demonstrates the need. Screenshots never go to external AI services. The current architecture grants no global keyboard or mouse authority. Any future input automation must be a separate typed capability with its own explicit permission, consent, threat model, and audit design.

## Installation management and protected installation

M006C is the first permanent production slice of the user-local installation architecture. Jarvis
owns a private virtual environment beneath its user-local installation root; stable user-local
dispatchers invoke that environment without a source-tree dependency or global Python mutation.
Application files, fixed dispatchers, systemd-user assets, XDG configuration/data/state/cache,
and XDG runtime state have distinct ownership and lifecycle. M006C establishes enough installed
identity, manifest and repair semantics for M019A to consume, preserve and extend rather than
introducing a replacement installer architecture. Every fixed dispatcher installed by M006C,
including canonical `jarvis`, is collision-safe.

`jarvis-config` is profile-first and owns ordinary profile configuration. Installation management owns model directories, llama.cpp path, Core/systemd-user state, update settings/checks, health, repair, version and diagnostics. M019A additionally owns dynamic physical profile-command exposure and its lifecycle. A minimum management surface for model directories/runtime path exists before runtime work; full `jarvis-manage` later expands repair and health over the M006C foundation without changing ownership.

An unconfigured ordinary `jarvis` invocation does not expose a cryptic raw
`model.not_selected` failure. A minimal guided presenter calls typed Core/service IPC operations to
locate/configure `llama-server`, manage model search directories, refresh GGUF discovery, select a
model for the Jarvis profile, configure essential reasoning/context/runtime settings where needed,
and validate readiness before continuing into chat. Model scanning, runtime management,
configuration persistence and SQLite remain owned by their existing Core services; neither the
client nor installer duplicates or directly mutates them. Setup cancellation and failures are
typed and understandable.

Core activation and profile model autostart are separate. M006C's socket activation starts one Core
on demand for IPC and does not start model runtimes merely because the user session begins. M018B
later adds per-profile `Start with computer` as profile-owned desired state reconciled by that same
Core, or by a thin activation request to it—not a separate Core, socket, service topology or
runtime manager per profile. The last valid selected model is used; a missing model is reported
without substitution. Duplicate login reconciliation is idempotent and does not consume first-run
learning state.

The active installed code and update infrastructure are immutable to the Agent/Tool Broker. Canonical installation identity and path checks form a real policy boundary for all mutating tools, including link/race defenses. A separate development clone that is not the active installation is an ordinary user project and may be edited subject to normal policy.

Only the separately invoked `jarvis-update` executable may acquire authority to replace installed application files. Core exposes no update-application IPC operation, and conversational execution cannot reach updater or protected lifecycle authority. Update checking is a separate installation-scoped narrow network operation, not a profile INTERNET tool; it is transparent, enabled by default, exchanges only minimal version/repository information, and cannot install anything.

Before application, the updater must verify integrity and cryptographic authenticity rooted in trusted information already available to the installed Jarvis. A checksum delivered beside the artifact from the same source is insufficient. M019B alone selects and documents the exact signing technology and trust-material lifecycle; M006C contains no release query/download, compatibility, integrity/authenticity, update application, rollback or post-update authority. The updater validates compatibility/migrations, preserves data, validates after application and fails recoverably. Normal installation and services are user-local and root-free. M019A completes release packaging and the installer/uninstaller over the M006C foundation; uninstalling binaries preserves user data unless the user separately confirms purge.

## Remaining decision gates

Only two product/technical decisions remain open in the current planning documentation:

- Milestone 014 must select the concrete web-search provider, credentials model, query-disclosure policy, and fallback behavior behind the stable provider interface.
- Milestone 019B must select the cryptographic signing/authenticity technology and trusted-key/material lifecycle while satisfying the installed-trust-root requirement above. This remains the Milestone 019 family decision gate.

## Ownership summary

| Concern | Owner | Must not own or bypass |
|---|---|---|
| Rendering, input, confirmations | CLI/TUI clients | Agent loop, database, runtimes, tools |
| Protocol and orchestration | Jarvis Core | Client presentation |
| Profile identity/configuration | Profile/config services | Alias strings as historical identity |
| GGUF identity/discovery | Model registry | Model file mutation or downloads |
| Model processes and per-profile FIFO | Runtime Manager/provider + generation coordinator | Profile history, host tools, competing Core ownership |
| Turn planning | Agent Engine | Direct host, permission, client rendering, or update authority |
| Prompt composition | Context Builder | Raw diagnostic/audit logs, unbounded or provenance-free contributions, hidden provider-policy instructions |
| Durable recall | Memory/notes services | Cross-scope data or diagnostic logs |
| Capability authorization | Policy Engine | Execution, model-controlled policy changes, or semantic content moderation |
| Capability execution | Tool Broker/adapters | Self-authorization or unrestricted model access |
| Operational evidence | Logging/audit services | Conversational memory |
| Installation checks/management | Management service | Profile INTERNET policy or update application |
| User-local installation/activation foundation | M006C installer, fixed dispatchers and systemd-user assets | Dynamic profile aliases, profile model autostart, or updater authority |
| Installation mutation | M006C/M019A installer lifecycle, M019A uninstaller, separate M019B `jarvis-update` | Core IPC, ordinary profile preferences, or in-chat self-update |

These boundaries preserve the central invariant: power is delivered as typed, validated, policy-authorized, bounded, structured, and audited capabilities—not as unrestricted LLM access to the host.
