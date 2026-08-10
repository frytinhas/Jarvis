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

Client dispatch depends on invocation mode and TUI maturity. Before the rich TUI is stable, bare `jarvis` and bare profile aliases open the simple interactive CLI. After the TUI passes its stability gate, those bare commands open the TUI by default. Invocations containing a natural-language request remain non-TUI one-shot commands in both phases. The simple interactive CLI remains an independent client and fallback; a future explicit option such as `--simple` may select it after the TUI becomes the default.

Clients connect to Jarvis Core over a user-only Unix domain socket using bounded, structured, versioned serialization (never pickle). The protocol supports request correlation, streaming text and tool events, approval requests, typed errors, and cancellation. A disconnected client does not erase Core’s responsibility to record the outcome of an in-flight destructive operation.

This same boundary is the compatibility point for future Voice and Jarvis Desktop App clients. Those future products are not part of the current implementation roadmap and must reuse Core rather than create separate agent brains.

## Jarvis Core (`jarvisd`)

Core owns all product state and orchestration: profiles, configuration, models, runtimes, sessions, the Agent Engine, context construction, memory, policy, tools, persistence, logging, audit, and runtime coordination. It exposes typed application operations over IPC and emits meaningful state events; it does not own CLI/TUI rendering.

Core is the trust boundary between untrusted/model-proposed content and host capabilities. Subsystems communicate through typed contracts and typed errors rather than reaching through layers to mutate each other’s storage.

## Profiles and configuration ownership

A profile is the primary user-facing identity and isolation boundary. Stable internal `profile_id` values—not display names or command aliases—own persona, profile context, selected model, per-model runtime settings, permissions, appearance, visible logging mode, messages, learning state, startup behavior, conversations, and other profile data.

The permanent `jarvis` profile always exists, cannot be renamed at the command level or deleted, and is the configuration template for new profiles. Cloning copies an explicit allowlist of current configuration, including Jarvis’s selected model and that model’s applicable per-profile settings such as reasoning level and context window. Conversations, private model notes, memories, learning history/state, chat logs, and diagnostic session history always start empty in the new profile. If the inherited model is missing when used, the Model Registry/Runtime path reports it as unavailable and never silently selects another model. Profile reset and deletion are service-enforced, transactional destructive operations with an exact preview and explicit confirmation.

Settings that logically affect a profile remain profile-owned. Settings that describe the installation—model search directories, llama.cpp path, installed commands, Core management, update source/checking, health, and repair—belong to installation management. Defaults are centralized, versioned, and resettable at setting, section, and profile levels.

## Profile command aliases

Every non-default profile has a deterministic lowercase ASCII/hyphen command alias derived from its display name. A safe user-level registrar creates a launcher, symlink, or equivalent dispatch entry that resolves to the one installed client plus a stable profile identity. It never creates a copy of Jarvis.

Alias creation, rename, collision detection, and removal are reconciled with the profile service. Reserved command names are rejected. Historical data never uses the alias as its sole key. Help through `jarvis` or a profile alias is client-side and does not start a model.

## Persistence and local storage

SQLite is the initial authoritative database, evolved only through migrations. It stores profile/model associations, sessions/messages, learning, memories, private notes, settings, approvals, tool calls, audit/runtime events, and storage accounting as those features are introduced. SQLite FTS5 supports local text search; optional future embeddings must also be local.

Storage follows XDG separation:

- configuration in XDG config;
- durable application/profile data in XDG data;
- diagnostics and operational state in XDG state;
- rebuildable data in XDG cache;
- sockets, locks, and PIDs in XDG runtime.

Private model data is keyed by `(profile_id, model_id)` and conversations add a session key. Configurable quotas and deterministic retention prevent unbounded storage. Active records are not pruned while being written. Tests replace every XDG root and database with temporary equivalents.

## Model registry

The installation-level model registry scans user-configured directories for user-owned GGUF files. It canonicalizes and deduplicates paths, reads bounded metadata where practical, tracks size and missing state, and assigns a stable local `model_id` without hashing entire multi-gigabyte files on every startup. It never downloads, moves, renames, or modifies model files.

Profiles reference registry models through profile/model associations. Reasoning, context size, sampling, resource settings, and timeouts are per profile/model and represented as validated structured values, not free-form shell fragments.

## LLM provider and runtime manager

The provider interface hides inference-backend details from the Agent Engine. The initial `LlamaCppProvider` starts/stops/health-checks/chats with `llama-server` using structured arguments and localhost transport. Future local providers can implement the same contract without leaking llama.cpp assumptions into the rest of Core.

The Runtime Manager owns `STARTING`, `READY`, `BUSY`, `ERROR`, `STOPPING`, and `STOPPED` transitions, ports, health, timeouts, and sanitized server diagnostics. A robust combination of runtime ID, PID, lock, Unix socket, and health evidence enforces at most one active model server per profile and recovers stale artifacts. Different profiles may concurrently run the same GGUF, but their runtime and persistent state remain independent.

## Agent Engine and Context Builder

The Agent Engine coordinates a turn: resolve profile/model/session, ask the centralized Context Builder for a bounded prompt, invoke the provider, persist conversation and diagnostics, interpret structured tool proposals, and stream results over IPC.

The Context Builder is the only authority for assembling model input. It orders and budgets core instructions, profile persona/context, relevant policy descriptions, model-private notes, selectively retrieved semantic/episodic memory, workspace/tool context, recent conversation, and the current request. Other modules contribute typed, bounded candidates; they do not append arbitrary prompt text.

Slash commands are routed by the client/Core command system and are never blindly sent to the model. Persona and persistent profile context are profile-owned. Provider/model switches do not import another profile’s identity.

## Learning, memory, and private notes

The first run of every `(profile_id, model_id)` pair enters a visibly active Learning Session. Learning start, finish, status, and destructive reset are explicit operations and do not alter tool permissions.

Memory layers remain distinct:

- working memory is the bounded active-turn context;
- conversation history is persisted by profile/model/session;
- episodic memory summarizes relevant prior sessions;
- semantic memory stores durable locally derived facts/preferences;
- profile context and persona belong to the profile;
- private notes belong to a profile/model pair;
- diagnostic logs are operational evidence, not memory.

Memory and notes are local, inspectable, erasable, selectively retrieved, and scope-filtered before ranking. Diagnostic and audit logs are never searched, summarized, or injected as model context.

## Policy Engine

The Policy Engine is the single authority for capability decisions. Profile policies use `allow`, `ask`, and `deny`; tool-specific rules may refine but not bypass category rules. The defaults and semantics in `AGENTS.md` are product contracts, including CREATE not implying overwrite, COPY plus MODIFY for an overwrite, ASK for DELETE/MODIFY/MOVE, and denial of sudo.

The model cannot change effective permissions. When a decision is `ask`, Core sends the human client the validated action, canonical target, concise consequence, and relevant arguments. Allow-once is bound to that request; persistent matching permission changes require explicit human intent and are audited.

## Tool Broker

The Tool Broker is the sole execution path for host capabilities. It owns the typed tool registry, input/result validation, canonical target resolution, policy check, approval binding, timeout/cancellation, bounded execution, structured error/result, and audit lifecycle.

Adapters implement namespaces such as `filesystem.*`, `system.*`, `process.*`, `apps.*`, `shell.*`, `web.*`, and `desktop.*`. Structured operations are preferred. Shell support is a constrained fallback using explicit executable paths and argument arrays, not unrestricted arbitrary command strings. A tool adapter cannot authorize itself or be called directly by the model.

## Logging and audit

Every chat session produces complete local diagnostic records regardless of visible logging mode. Central redaction runs before persistence and rendering and removes credentials, tokens, cookies, private keys, authorization headers, secret environment values, and credentials in URLs. Events correlate profile, model, runtime, session, request, turn, and tool call identifiers while avoiding unnecessary large content blobs.

Profile-visible modes (`full`, `server-essential`, `essential`, `essential-minimum`, and `none`) only control client rendering. `none` still shows approvals, errors, destructive confirmations, and critical failures. Audit records permission and tool outcomes. Human clients may access safe diagnostic views; neither diagnostic nor audit stores are model-memory sources.

## Network and desktop boundaries

The LLM runtime does not need unrestricted internet. Core provides explicit brokered `web.search`, `web.fetch`, and `web.download` capabilities under INTERNET policy, outbound-data rules, timeouts, redirects, size limits, cache accounting, and redacted audit. `web.search` depends on a provider interface owned by the network subsystem; normalized search requests/results keep the concrete backend from changing the Agent Engine or Tool Broker. The provider, credential model, query-disclosure policy, and fallback behavior remain a Milestone 014 decision. No conversation, profile context, note, memory, screenshot, or private file is silently sent externally, and no cloud AI is required.

Desktop support is Wayland-oriented and adapter-based. It prefers desktop entries/XDG, D-Bus, portals, and accessibility APIs across GNOME, KDE, and wlroots rather than assuming X11 or visual clicking. SCREEN means screen/context access only: capture requires both SCREEN policy and compositor/portal consent, is locally processed (optionally by a local VLM), and yields bounded structured observations. Screenshots never go to external AI services. The current architecture grants no global keyboard or mouse authority. Any future input automation must be a separate typed capability with its own explicit permission, consent, threat model, and audit design.

## Installation management and protected installation

`jarvis-config` is profile-first and owns ordinary profile configuration. `jarvis-manage` owns installation status, model directories, llama.cpp path, registered aliases, Core/systemd-user state, update settings/checks, repair, version, diagnostics, and uninstall entry points. Per-profile autostart uses user-level systemd and the last valid selected model; a missing model is reported rather than silently replaced.

The active installed code and update infrastructure are immutable to the Agent/Tool Broker. Canonical installation identity and path checks form a real policy boundary for all mutating tools, including link/race defenses. A separate development clone that is not the active installation is an ordinary user project and may be edited subject to normal policy.

Only `jarvis-update` may replace installed application files. Update checking is transparent, enabled by default, exchanges only minimal version/repository information, and never applies an update. Before application, the updater must verify integrity and cryptographic authenticity rooted in trusted information already available to the installed Jarvis. A checksum delivered beside the artifact from the same source is not sufficient as the final authenticity mechanism. Milestone 019 must select and document the exact signing technology and trust-material lifecycle; this architecture does not select one prematurely. The updater also validates compatibility and migrations, preserves user data, validates after application, and fails recoverably. Normal installation and systemd services are user-local and avoid root. Uninstalling binaries preserves user data unless the user separately confirms purge.

## Remaining decision gates

Only two product/technical decisions remain open in the current planning documentation:

- Milestone 014 must select the concrete web-search provider, credentials model, query-disclosure policy, and fallback behavior behind the stable provider interface.
- Milestone 019 must select the cryptographic signing/authenticity technology and trusted-key/material lifecycle while satisfying the installed-trust-root requirement above.

## Ownership summary

| Concern | Owner | Must not own or bypass |
|---|---|---|
| Rendering, input, confirmations | CLI/TUI clients | Agent loop, database, runtimes, tools |
| Protocol and orchestration | Jarvis Core | Client presentation |
| Profile identity/configuration | Profile/config services | Alias strings as historical identity |
| GGUF identity/discovery | Model registry | Model file mutation or downloads |
| Model processes | Runtime Manager/provider | Profile history, host tools |
| Turn planning | Agent Engine | Direct host or permission authority |
| Prompt composition | Context Builder | Raw diagnostic/audit logs, unbounded contributions |
| Durable recall | Memory/notes services | Cross-scope data or diagnostic logs |
| Authorization | Policy Engine | Execution or model-controlled policy changes |
| Capability execution | Tool Broker/adapters | Self-authorization or unrestricted model access |
| Operational evidence | Logging/audit services | Conversational memory |
| Installation lifecycle | Manager/installer/`jarvis-update` | Ordinary profile preferences or in-chat self-update |

These boundaries preserve the central invariant: power is delivered as typed, validated, policy-authorized, bounded, structured, and audited capabilities—not as unrestricted LLM access to the host.
