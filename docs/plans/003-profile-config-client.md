# Milestone 003 — Profile-first Configuration Client and Logical Aliases ExecPlan

Status: **DONE**
Last updated: 2026-08-16 America/Sao_Paulo

## Purpose and user outcome

M003 delivers the first thin user-facing configuration client: `jarvis-config -> local IPC -> jarvisd -> Core-owned profile/configuration services`.

Users select a profile first, create profiles, edit existing profile configuration, rename profiles, reset configuration, and delete non-Jarvis profiles. Logical aliases remain persistent Core-owned data mapping normalized alias to stable `ProfileId`. M003 does not expose `jarvis` or profile aliases as executable commands, start chat, or assign temporary configuration semantics to chat commands.

## Scope

- Dependency-free `jarvis-config` terminal client and local `jarvis-help`.
- Profile-first selection and `Create new profile`.
- M001-backed profile creation, rename, configuration section reads/writes, reset preview/confirm, and delete preview/confirm over IPC.
- Logical alias resolution over IPC through protocol-v1 `profile-management-v1`.
- Normal configuration for persona, profile context, appearance, waiting/goodbye messages, permission preferences, and profile management; Advanced configuration for visible logging only.
- Accessible terminal/error behavior, tests, documentation, and disposable-XDG verification.

## Non-goals

M003 must not create physical profile commands, executable aliases, launchers, symlinks, wrappers, filesystem alias registries, PATH entries, PATH inspection, or PATH mutation. It also excludes chat, one-shot requests, models/GGUF/runtime configuration, TUI, Policy Engine, Tool Broker, startup UI, installer/systemd/updater, network, telemetry, migrations, defaults changes, history, memory, notes, conversations, and chat diagnostics.

M006B owns the documented development/package-level `python -m jarvis.cli` and `python -m jarvis.cli --profile-alias <alias> [request]` mechanism for a runnable/testable simple chat CLI. M019A owns final user-local physical command exposure, PATH integration, external collision handling, reconciliation, cleanup, and uninstall behavior.

## Current progress

| Item | Status |
|---|---|
| Authority reconciliation and this ExecPlan | **DONE** |
| IPC capability and Core routing | **DONE** |
| Thin configuration client | **DONE** |
| Tests, documentation, and verification | **DONE** |

Progress log: 2026-08-14 America/Sao_Paulo — Materialized this approved ExecPlan and reconciled current authority so M003 owns logical aliases only. No M003 implementation work began.

Progress log: 2026-08-14 America/Sao_Paulo — Verified committed M000/M001/M002 baseline and that the only existing worktree changes were approved M003 documentation. Added `profile-management-v1`, Core-owned routing backed by M001 services, and initial `jarvis-config`/`jarvis-help` package clients. Focused M002 IPC regression tests pass (8 passed); Ruff is unavailable in the current interpreter environment.

Progress log: 2026-08-14 America/Sao_Paulo — Added an IPC integration test covering create, canonical logical alias resolution, section update, and stable-ID-preserving rename. `PYTHONPATH=src python3 -m pytest tests/integration/test_profile_management_ipc.py tests/integration/test_core_ipc.py tests/unit/test_ipc_protocol.py -q` passes (9 passed); `compileall` and `git diff --check` pass. Local help and unsupported-argument exit-64 behavior were exercised. Full milestone test, wheel, static-analysis, security, and disposable-XDG verification remain pending.

Progress log: 2026-08-14 America/Sao_Paulo — Reviewed client input handling and fixed it to read the injected terminal stream rather than process-global input. Added control-character/EOF/numbered-selection coverage. CPython 3.14 marker suites pass: unit 176, integration 78, migration 36, security 58; full suite 348. Ruff is clean after formatting. CPython 3.12 is available but has no pytest installed; wheel, 3.12 test, and disposable-XDG verification remain pending, so status remains IN PROGRESS.

Progress log: 2026-08-16 America/Sao_Paulo — Resumed the interrupted worktree and audited the final section-read concurrency finding. The correction was already present: `profiles.configuration.section.get` serializes value and all revision metadata from one `ProfileService.get_profile()` aggregate transaction rather than combining `ProfileConfigService.get_section()` with a separate identity/configuration read. `test_section_read_uses_one_atomic_profile_aggregate` rejects the old split-read adapter. Analogous aggregate reads are single-transaction; section update is fail-closed through M001 identity/configuration revisions. Focused M003/M001/M002 regression selection passed (47 passed).

Progress log: 2026-08-16 America/Sao_Paulo — Final verification passed: CPython 3.12.13 and 3.14.4 each report unit 182, integration 84, migration 36, security 62, full 364; CPython 3.13 is unavailable. Predecessor-only selection passed 344 on both available interpreters. Ruff check, Ruff format check, strict mypy, and `git diff --check` pass. A fresh CPython 3.12 wheel built and clean-installed with `pip check`; it packages defaults and exactly migrations 0001/0002, has defaults versions 2/2, no runtime dependencies, and exactly `jarvisd`, `jarvis-config`, and `jarvis-help` console scripts. Disposable-XDG walkthrough used six mode-0700 roots, a clean installed daemon and terminal client, exercised Jarvis selection, Unicode alias create/resolve/rename, old-alias invalidation and section update, and verified no alias artifact or PATH mutation. M003 is DONE.

## Repository state and prerequisites

- Branch `new-jarvis`, HEAD `40ca480` (`feat: M002 Reviewed`); M000, M001, and M002 are committed.
- Schema version 2 with migrations `0001` and `0002`; defaults schema/product versions 2/2.
- No runtime dependencies. M003 and all later implementation remain not started.
- M001 supplies stable `ProfileId`, strict display-name/alias validation, logical alias persistence, profile configuration, revisions, clone semantics, and five-minute state-bound destructive intents.
- M001 configuration is limited to persona text, profile context text, three appearance colors, waiting/goodbye messages, visible logging mode, startup preference, and nine permission preferences. It has no models, history, memory, notes, runtimes, sessions, or chat logs.
- M002 supplies protocol v1, capability negotiation, request streams, safe errors, and read-only profile catalog/get operations. Clients must not import repositories or SQLite services.

## Implementation sequence

### 1. **DONE — Extend protocol v1 for profile management**

Add `profile-management-v1` without changing `IPC_PROTOCOL_VERSION = 1` or M002 behavior. Define typed validation for logical alias resolution and profile/configuration mutations. Validate protocol negotiation and M002 regressions. Recovery: no persistence change; clients that do not negotiate the capability remain unchanged.

### 2. **DONE — Route Core-owned profile/configuration operations**

Compose existing `ProfileService` and `ProfileConfigService` in Core. Add logical alias resolution, create/rename, section reads/writes, and destructive preview/confirm routing with metadata-only diagnostics. Validate fake/real Core integration, malformed payloads, revisions, and intents. Recovery: M001 immediate transactions and optimistic revisions roll back failed domain changes.

### 3. **DONE — Add thin terminal configuration/help clients**

Add only `jarvis-config` and `jarvis-help` package entry points. Implement selector/menu/input/confirmation presentation over `JarvisIpcClient`; do not expose public `--profile-id`. Validate terminal transcripts, help-without-Core, EOF/Ctrl+C, and non-TTY behavior. Recovery: presentation code owns no persistent state.

### 4. **DONE — Verify and document**

Add focused tests, predecessor regression coverage, wheel checks, and a disposable-XDG walkthrough. Update this plan with evidence. Recovery: no migration, launcher, PATH, or real-user-state operation exists.

## Exact files and components affected

Created: `src/jarvis/cli/__init__.py`, `src/jarvis/cli/__main__.py`, `src/jarvis/cli/application.py`, `src/jarvis/cli/presenter.py`, `tests/unit/test_cli_arguments.py`, `tests/unit/test_cli_rendering.py`, `tests/integration/test_profile_management_ipc.py`, `tests/integration/test_profile_config_client.py`, and `tests/security/test_profile_config_client_security.py`.

Modified: `AGENTS.md`, `README.md`, `ROADMAP.md`, `docs/architecture.md`, `docs/development.md`, `docs/ipc-protocol.md`, `pyproject.toml`, `src/jarvis/core/runtime.py`, `src/jarvis/ipc/client.py`, `src/jarvis/ipc/models.py`, `src/jarvis/ipc/server.py`, `src/jarvis/profiles/service.py`, `tests/security/test_core_ipc_security.py`, `tests/security/test_no_network_or_telemetry.py`, and `tests/support/ipc_client.py`.

Deliberately untouched: M001 repositories/migrations/defaults, installer, model/runtime/chat/tool/TUI packages, and all physical alias/launcher/PATH components.

## Contracts and interfaces

Protocol v1 gains optional capability `profile-management-v1`. `jarvis-config` requires `request-stream-v1`, `profile-catalog-v1`, and `profile-management-v1`; existing M002 clients remain compatible.

| Operation | Profile ID | Payload | Result |
|---|---|---|---|
| `profiles.resolve_alias` | forbidden | `{command_alias}` | Existing five-field profile entry |
| `profiles.create` | forbidden | `{display_name}` | Five-field profile entry |
| `profiles.rename` | required | `{display_name, expected_identity_revision}` | Five-field renamed entry |
| `profiles.configuration.section.get` | required | `{section}` | Section value and revisions |
| `profiles.configuration.section.update` | required | `{section, value, expected_identity_revision, expected_configuration_revision}` | Updated section/revisions |
| `profiles.reset.preview` | required | `{scope}` | Existing M001 destructive preview |
| `profiles.reset.confirm` | required | `{operation_id, scope, confirmation_token}` | Existing reset result |
| `profiles.delete.preview` | required | `{}` | Existing M001 delete preview |
| `profiles.delete.confirm` | required | `{operation_id, confirmation_token}` | Existing delete result |

`profiles.resolve_alias` accepts only canonical M001 alias syntax and resolves it to stable `ProfileId`; aliases are never ownership keys. After rename, the old alias fails and the new alias resolves to the unchanged ID. After deletion, the alias fails. Reserved-name and profile-alias collision policy remains exactly M001; M003 does not examine unrelated PATH executables.

Section updates are Core adapters: Core reads complete M001 configuration, replaces only the validated section, and invokes the existing revision-checked service. This preserves the hidden startup preference without exposing it in the M003 UI.

## Profile configuration and terminal UX

M003 edits only existing M001 data. Persona is profile-owned user persona text; profile context is persistent profile context text; appearance is the validated color triple; messages are presentation overrides; and permissions are stored `allow`/`ask`/`deny` preferences, explicitly labelled as unenforced until the future Policy Engine. Advanced exposes visible logging only.

Persona and profile context must not be conflated with future conversation history, episodic/semantic memory, model-private notes, temporary prompt context, or diagnostics. Startup preference is not displayed or edited because autostart belongs to M018B; whole-profile reset still truthfully previews all M001 categories it resets.

`jarvis-config` always begins with profile selection. `jarvis-config --help`, `-h`, and `--h`, plus `jarvis-help`, render locally without Core/model startup. Unsupported arguments or required non-interactive input exit 64; EOF/Ctrl+C before confirmation exit 130. The client uses numbered text choices, honors `NO_COLOR`, and escapes terminal control characters in stored user text.

## Database, migrations, and storage

No migration or defaults change is required: schema version remains 2, migrations remain `0001` and `0002`, and defaults schema/product versions remain 2/2. M001 `profiles` and `profile_aliases` remain authoritative. M003 adds no filesystem alias registry, registration-status table, external-operation journal, launcher metadata, or PATH state.

## Security and privacy considerations

- Core exclusively validates and mutates profile state; clients never import repositories or SQLite.
- M001 validation, reserved aliases, uniqueness, revisions, and destructive intent binding remain authoritative.
- IPC payloads are bounded/typed; malformed requests create no mutation state.
- Diagnostics exclude configuration values, display names, aliases, persona/context, tokens, raw payloads, paths, and raw errors.
- No executable aliases means no launcher, symlink, PATH, filesystem registry, or stale-command cleanup belongs to M003.
- No network, telemetry, sudo, installation mutation, model-content moderation, Policy Engine, or Tool Broker behavior is added.

## Tests

Add unit/integration/security coverage for profile-first selection, Jarvis selection, creation and current-Jarvis cloning; in-scope reads/writes/resets and permission wording; rename/reset identity behavior and Jarvis protection; normalized logical alias resolution/rename/delete/reserved cases; absence of command files/symlinks/launcher modules/PATH reads/PATH mutations; acceptance of a logical alias that matches unrelated PATH executable; concurrency/intents/malformed IPC/Core restart/capability mismatch; help, Ctrl+C, EOF, non-TTY, terminal escape safety, no direct DB access, no network/telemetry, no installation mutation, and no M004+ behavior.

Run all marker suites and full pytest on CPython 3.12 and 3.14, plus 3.13 when available; run Ruff, mypy, wheel build/install checks, predecessor regressions, `git diff --check`, and status review.

## Manual verification

1. Create disposable HOME and all five mode-0700 XDG roots; do not alter PATH.
2. Start `jarvisd`; run `jarvis-config`; select Jarvis and inspect normal/Advanced settings.
3. Change Jarvis appearance or permission preference; create `João Trabalho`; verify `joao-trabalho`, new stable ID, and exact M001 clone behavior.
4. Resolve `joao-trabalho` through IPC; verify no executable, symlink, or command file exists.
5. Rename it; verify unchanged ID, old alias failure, and new logical alias resolution.
6. Reset one section; preview/cancel then confirm whole reset.
7. Verify Jarvis deletion is rejected; delete the standard profile and verify its alias no longer resolves.
8. Create/rename a logical alias matching unrelated PATH command; verify no PATH inspection/mutation.
9. Restart Core; verify persistence, schema v2, no TCP/network behavior, and no physical command artifacts; clean up only the validated temporary root.

## Discoveries

- M001 already contains all profile configuration and logical alias structures M003 needs.
- M002 protocol v1 supports negotiated capability extension without breaking existing clients.
- Authority now supersedes earlier future-facing filesystem-reconciliation forecasts in completed plans without rewriting those historical records.
- M006B remains independently runnable/testable through `python -m jarvis.cli` plus Core-resolved `--profile-alias <alias> [request]`; final user PATH exposure remains M019A.
- The interrupted M003 review found that an earlier section-read adapter had combined values and revisions from two transactions. The final adapter uses one M001 aggregate snapshot; its regression specifically fails if the split `get_section()` path returns. This is a correctness/concurrency fix, not a migration or contract expansion.

## Architectural decisions

| Date | Decision | Rationale and consequence |
|---|---|---|
| 2026-08-14 | M003 owns logical aliases only | Avoids temporary command behavior and keeps executable exposure with installation ownership. |
| 2026-08-14 | M006B owns development/package CLI invocation | Makes the chat MVP runnable/testable before final installation. |
| 2026-08-14 | M019A owns physical commands/PATH lifecycle | Centralizes installer, collision, repair, cleanup, and uninstall responsibility. |
| 2026-08-14 | No migration/defaults/dependency | Existing M001 schema and standard-library infrastructure suffice. |

## Deviations from the original plan

Before implementation, authority superseded the earlier M003 forecast of physical launcher/symlink registration. This plan excludes filesystem alias materialization, PATH behavior, temporary `jarvis` configuration semantics, and public `--profile-id` coupling.

## Unresolved issues

None. The authority amendment is complete. M014 web-provider and M019B release-signing decisions are unrelated later milestones.

## Completion criteria and evidence

**DONE:** `jarvis-config` manages every in-scope M001 section through Core IPC, including revision-checked update and section/whole-profile destructive reset. Logical aliases resolve to stable IDs, preserve identity through rename, and fail after rename/delete. Capability/malformed-payload, forged/expired/replayed destructive-intent, concurrency, Core-restart, privacy, terminal, no-network/no-PATH/no-physical-alias, and no-M004 tests pass. CPython 3.12.13 and 3.14.4 full matrices are 364 passed each; 3.13 is not installed. The 344-test committed M000–M002 selection passes on both. The fresh wheel clean install passes `pip check`, imports/resources/version checks, and console-script audit; the disposable-XDG terminal/IPC walkthrough passes without creating alias artifacts or inspecting/modifying PATH. Schema remains 2, migration files remain exactly 0001/0002, and defaults schema/product remain 2/2.

## Handoff summary

M003 is complete and ready for independent review. No blocker remains. Do not begin M004 without its separately authorized ExecPlan.
