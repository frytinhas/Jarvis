# Milestone 006D — Context Auto and First-Run Runtime Compatibility Hotfix ExecPlan

Status: IMPLEMENTED — verification complete  
Last updated: 2026-08-22 America/Sao_Paulo

## Purpose and user outcome

This hotfix follows completed M006C and precedes M007. It corrects Jarvis context-window
semantics so `0` means Auto and lets llama-server use its model-derived context. It also makes
the real M006C first-run runtime failure understandable without weakening provider, process,
listener, executable-identity, timeout, or cleanup validation.

When complete, fresh/default model configuration displays Auto, persists `context_window = 0`,
omits `--ctx-size`, and uses the effective context reported by a ready llama-server. Existing
explicit values remain explicit. Setup accepts blank/0 as Auto, `/context` distinguishes Auto
from numeric tokens, and startup failures expose only bounded generic reason classes.

## Scope

- Change `ModelRuntimeConfig` to accept `0..1_000_000`; `0` is Auto and `1..1_000_000` is explicit.
- Replace the true product default 8192 with 0 in packaged/fresh configuration.
- Bump `product_defaults_version` 5→6; retain `defaults_schema_version` 5; add no SQL migration.
- Preserve every existing persisted nonzero context value without rewriting it.
- Omit `--ctx-size` for Auto and emit exact `--ctx-size <value>` for explicit values.
- Obtain Auto's effective context after readiness from bounded authenticated llama-server `GET
  /props`, reading `default_generation_settings.n_ctx` only.
- Make Context Builder use effective runtime context and never treat numeric zero as a prompt
  budget.
- Require the existing quiesced stop/update/start lifecycle for Auto↔explicit changes.
- Update setup and human presentation; retain numeric 0 in machine-readable configuration.
- Preserve bounded allowlisted startup-failure classification and safe human-readable setup errors.
- Reproduce/verify the reported GGUF failure and add permanent regression coverage.

## Non-goals

- No M007 or later behavior, tools, web, memory, aliases, updater, autostart, TUI, downloads, or
  new host capabilities.
- No VRAM/RAM estimation, automatic clamping to metadata, or rewriting explicit user values.
- No model-family/filename special cases and no broad “all runtime settings Auto” redesign.
- No speculative GPU/thread/batch/default changes. A further change is permitted only if a
  compatible GGUF proves one single generic forced-argument defect.
- No raw stderr, paths, tensor names, argv, secrets, prompts, or model output through IPC or model
  context.
- No weakening of health, process/listener ownership, executable identity, timeout, descriptor,
  cleanup, installation-protection, privacy, or profile/model isolation invariants.
- Do not modify completed M000–M006C ExecPlans, commit, push, or start M007.

## Current progress

Summary: implementation and verification are complete; final adversarial-review corrections are
recorded in the progress log.

| Work item | Status |
|---|---|
| Roadmap M006D entry and this ExecPlan materialization | DONE |
| Domain validation and Auto/default version design | DONE |
| Persistence compatibility/default transition implementation | DONE |
| Conditional llama-server argv and effective-context contract | DONE |
| Setup/UI Auto presentation | DONE |
| Runtime transition enforcement | DONE |
| Bounded startup failure classification/presentation | DONE |
| Focused and permanent regression tests | DONE |
| Full, marker, lint, type, wheel, installed acceptance | DONE |

Progress log: 2026-08-22 America/Sao_Paulo — verified clean branch `new-jarvis` at `4debfbf`;
read AGENTS.md, ROADMAP.md, PLANS.md, architecture and M006C authority; inspected M004/M005/
M006A/M006B implementation and tests. No source or completed-plan changes were made.

Progress log: 2026-08-22 America/Sao_Paulo — upstream and local llama-server contract confirmed:
`--ctx-size` defaults to 0 and 0 loads context from the model; local `/usr/bin/llama-server` is
Debian b8681. A bounded exact-configuration reproduction failed during tensor loading with a
missing required tensor, establishing a generic model-load incompatibility rather than a
context-size defect.

Progress log: 2026-08-22 America/Sao_Paulo — implemented the approved Auto value across the
domain and packaged defaults. `ModelRuntimeConfig` accepts only integer 0..1,000,000 (with bool
rejected), defaults schema remains 5, product defaults are 6, and all retained default-version
transitions preserve stored values without a SQL migration or model-row rewrite.

Progress log: 2026-08-22 America/Sao_Paulo — implemented conditional argv and authenticated
effective-context handoff. Auto omits `--ctx-size`; explicit values emit exactly one flag/value
pair. After healthy loopback readiness, the provider performs a bounded authenticated `/props`
request, duplicate-key-safe parses only positive bounded `default_generation_settings.n_ctx`, and
discards the payload. Runtime snapshots retain only that integer. Agent context construction waits
for this ready budget for Auto and rejects a nonpositive Context Builder budget.

Progress log: 2026-08-22 America/Sao_Paulo — setup now treats blank and 0 as Auto, retains
numeric 0 on the wire, and `/context` renders `Auto (model default)` rather than zero tokens.
Active IPC model-config updates now use the existing `runtime.switch_required` boundary, requiring
the established stop/update/start lifecycle instead of silently diverging from the active server.

Progress log: 2026-08-22 America/Sao_Paulo — startup diagnostics now retain an 8 KiB in-memory
stderr tail only long enough to classify a failed process as `model_load_failed`,
`argument_incompatible`, `resource_exhausted`, `startup_timeout`, or `process_exit`. No raw tail
is persisted or placed in a runtime snapshot, IPC payload, setup error, or model input. The prior
reported missing-tensor case remains generic `model_load_failed`; no model-specific change or
forced-default change was made.

Progress log: 2026-08-22 America/Sao_Paulo — verification passed: focused M006D tests; unit
(312), integration (145), migration (47), security (85), full pytest (589) on CPython 3.12 and
3.14; Ruff check/format; strict mypy; clean wheel build; private Python 3.14 installed-wheel pip
check; and fixed `jarvis`, `jarvis-help`, and module help acceptance. `git diff --check` passed.
No local GGUF was discoverable for the optional real-model acceptance, so no model was downloaded
or changed.

Progress log: 2026-08-22 America/Sao_Paulo — adversarial review found and fixed two in-scope
defects. The stderr tail continued collecting after readiness; it now has an explicit capture gate
and is cleared/disabled after readiness and after classification. A timed-out `/props` request
previously mapped to `process_exit`; it now retains `startup_timeout`. Authenticated loopback
`/props`, duplicate-key rejection, timeout classification, and tail clearing have permanent tests.

## Repository state and prerequisites

- M006C is complete at the current HEAD and supplies installed dispatchers, socket activation,
  setup-v1, and first-run continuation.
- M004 owns `profile_models.runtime_config_json`, model associations, and `ModelRuntimeConfig`.
- M005 owns `LlamaCppProvider`, `RuntimeManager`, one runtime per profile, readiness, process and
  listener identity, and bounded aggregate diagnostics.
- M006A owns Context Builder and generation coordination; M006B owns `/context`, setup-related
  simple-client presentation, and safe client error rendering.
- Existing database migrations are 0001–0005. No migration is required for this hotfix.
- Tests use temporary XDG/HOME/PATH roots, fake providers, bounded fake server responses, and
  small GGUF fixtures. Real GGUF acceptance is opt-in and must never download or mutate models.
- Required local checks are the existing CPython 3.12/3.14 matrix, marker suites, Ruff, strict
  mypy, wheel, installed-M006C acceptance, and `git diff --check`.

## Implementation sequence

1. **DONE — Domain and defaults.** Updated `ModelRuntimeConfig` validation/defaults and
   packaged model defaults. Change the defaults parser to accept zero only for context. Bump
   product defaults to 6, keep schema 5, and add all supported unchanged transition paths to 6.
   Validate with domain/default tests and confirm no SQL migration is introduced.

2. **DONE — Persistence and compatibility.** Existing JSON values are preserved on read and
   write; ensure fresh associations use 0. Verify reset-then-reselect produces 0 and existing
   8192/other explicit values remain unchanged. Add migration/default-version tests and inspect
   initialization markers for 5/6.

3. **DONE — Provider argv and effective context.** `build_argv` omits `--ctx-size` for
   zero and emit the exact pair for positive values. Add a bounded authenticated `/props` read
   after readiness, parse only positive `default_generation_settings.n_ctx`, reject malformed or
   oversized data safely, and expose the effective context in the typed runtime readiness result.
   Fake providers must provide a deterministic effective context. Preserve all existing process,
   descriptor, loopback, health, and secret-boundary checks.

4. **DONE — Context/runtime coordination.** Readiness is established before Auto prompt
   construction and pass the effective runtime context to Context Builder. Ensure zero is never
   used as a budget. Treat Auto and explicit configs as unequal runtime-affecting values. Prevent
   active configuration updates from silently diverging from the running server; use the existing
   quiesced stop/update/start lifecycle and verify runtime IDs/argv across both transitions.

5. **DONE — Setup and human presentation.** Setup wording/default handling makes blank
   and explicit 0 select Auto, numeric values remain numeric, and invalid bounds remain typed
   failures. Render `/context` as Auto or `<n> tokens`. Preserve numeric zero in machine-readable
   IPC/configuration responses.

6. **DONE — Startup diagnostics.** A bounded in-memory stderr tail exists only long enough
   to classify startup failures into allowlisted classes such as model load failure, argument
   incompatibility, resource exhaustion, timeout, and generic process exit. Preserve the typed
   reason through setup/client errors and render bounded human messages. Do not persist or expose
   raw provider output.

7. **DONE — Compatibility investigation.** The reported GGUF was reproduced with exact saved
   arguments, Auto, and a compatible local GGUF where available. Compare batch, ubatch, GPU-layer,
   thread, flash-attention, timeout, and argument behavior against current llama-server defaults.
   Apply no additional runtime-default change unless a compatible GGUF proves one specific forced
   argument is the generic cause; record any such discovery before implementation continues.

8. **DONE — Verification and handoff.** Focused tests and the complete
   marker/full/lint/type/wheel/installed acceptance matrix. Update this plan's evidence and leave
   M007 untouched.

## Exact files and components affected

Expected modifications:

- `src/jarvis/models/models.py`, `src/jarvis/config/defaults.py`,
  `src/jarvis/config/defaults.toml` — domain/default/version contracts.
- `src/jarvis/llm/provider.py`, `src/jarvis/llm/llama_cpp.py`, `src/jarvis/runtimes/manager.py` —
  argv, bounded `/props`, effective-context readiness, and lifecycle coordination.
- `src/jarvis/chat/agent.py`, `src/jarvis/chat/context.py` — effective Auto prompt budgeting.
- `src/jarvis/setup.py`, `src/jarvis/cli/application.py`, `src/jarvis/cli/chat_application.py` —
  typed reason projection, setup prompts, and Auto presentation.
- Relevant existing unit/integration/migration/security tests and real-GGUF support acceptance.
- `docs/architecture.md`, `docs/ipc-protocol.md`, `docs/development.md`, and README only where
  user-visible defaults or contracts are documented.

Expected documentation addition already materialized:

- `ROADMAP.md` M006D entry.
- This file, `docs/plans/006d-context-auto-runtime-compatibility-hotfix.md`.

Deliberately untouched: `AGENTS.md` (no contradiction found), all completed M000–M006C ExecPlans,
all SQL migration files, M007 and later implementation files, installation/alias/updater/TUI/tool/
web/memory subsystems.

## Contracts and interfaces

- `ModelRuntimeConfig.context_window`: integer `0..1_000_000`; zero is Auto, positive values are
  explicit. Domain and wire serialization preserve the integer exactly.
- Defaults: product version 6, schema version 5. Defaults transitions preserve persisted values;
  no model configuration backfill or destructive rewrite occurs.
- Provider argv: Auto emits no `--ctx-size`; explicit emits exactly `--ctx-size`, followed by the
  decimal value. All other managed flags retain their existing security contract.
- Provider readiness: a bounded authenticated `GET /props` result may provide an effective context
  integer from `default_generation_settings.n_ctx`. Unknown/untrusted payloads fail safely and are
  never passed upward as raw data.
- Context Builder receives a positive effective context budget. It must never receive configured
  zero as its budget or infer a provider policy from model text.
- Runtime-affecting config changes use the existing profile quiescence and stop/update/start
  lifecycle. There is one active model server maximum per profile and no silent live divergence.
- Startup errors expose only typed, bounded, allowlisted reason classes. Human diagnostics remain
  a Core-to-client route and cannot enter Context Builder/model memory.
- Setup accepts blank/0 as Auto, persists zero, and returns typed validation failures for negatives,
  overflow, malformed values, or unsafe runtime readiness.

## Database, migrations, and storage

No database migration or table change is planned. `profile_models.runtime_config_json` already
stores the complete typed configuration, and zero is representable without a SQL constraint change.
Fresh association creation consumes product defaults version 6. Existing rows are read and written
unchanged; no 8192→0 backfill occurs. Reset behavior remains centrally versioned: whole-profile
reset removes model associations, and subsequent selection creates the current Auto default.

The bounded `/props` payload and startup stderr classification are ephemeral/provider-boundary
data. Persisted diagnostics retain only existing bounded aggregate stream metadata and safe reason
classes. Quota, reservation, XDG ownership, retention, and profile/model storage isolation remain
unchanged.

## Security and privacy considerations

- Core remains the sole runtime authority; clients and models cannot start processes or mutate
  repositories directly.
- Model output freedom remains separate from host execution authority; no content moderation or
  provider-policy prompt is added.
- `/props` is read only, bounded, loopback-only, authenticated where supported, and parsed without
  retaining model paths, templates, or arbitrary response fields.
- Process/executable identity, model descriptor identity, API-key descriptor handling, listener
  ownership, health validation, timeouts, cleanup, and one-runtime-per-profile invariants remain
  mandatory.
- Startup stderr is classified in bounded memory and reduced to allowlisted reason classes. Raw
  stderr, paths, tensor names, argv, secrets, prompts, responses, and credentials never enter IPC,
  persisted diagnostics, or model context.
- Existing profile/model isolation and reset/delete quiescence remain authoritative.
- No downloads, outbound telemetry, cloud inference, root/system mutation, or active-installation
  bypass is introduced.

## Tests

Unit tests:

- `ModelRuntimeConfig` accepts 0; rejects negatives, booleans, and values over 1,000,000.
- Domain default is 0; packaged defaults are product 6/schema 5; reset/default transitions are
  immutable and preserve explicit values.
- Wire serialization/deserialization of 0 is exact.
- Auto argv omits `--ctx-size`; explicit argv includes exact `--ctx-size <value>`.
- `/props` parsing accepts bounded valid payloads and rejects malformed, duplicate-key, missing,
  non-integer, nonpositive, and oversized effective context values.
- Fake provider effective-context handoff and Context Builder rejection of numeric zero.
- Auto/explicit dataclass equality and active lifecycle transition guards.
- Setup input parsing and Auto/numeric presentation.
- Safe startup reason classification remains bounded and excludes raw text.

Integration/migration/security tests:

- Existing persisted explicit 8192/other values survive initialization and restart unchanged.
- Fresh association and reset-then-reselect use 0; no migration 0006 is present.
- Setup blank→Auto, explicit 0→Auto, numeric preservation, invalid negatives/overflow, readiness,
  cancellation, and safe failure rendering.
- Auto and explicit runtime starts use distinct runtime IDs and exact argv; active config changes
  cannot silently leave an old server serving a new configuration.
- Effective Auto context is used for a chat after readiness; explicit context remains authoritative.
- Provider process/health/listener/descriptor/security regressions remain green.
- Reported Qwen GGUF fails as generic model-load incompatibility with no filename/tensor/raw stderr
  leak; compatible local GGUF reaches READY/chat when environment permits.
- No raw diagnostics enter model context, IPC payloads, persisted diagnostic content, or audit data.
- M004–M006C predecessor tests, setup-v1, installed command/source-independence, socket activation,
  profile isolation, reset/delete, and cancellation regressions remain green.

Required commands:

```text
pytest -m unit
pytest -m integration
pytest -m migration
pytest -m security
pytest
ruff check .
ruff format --check .
mypy src tests
python -m pip wheel --no-deps --no-build-isolation --wheel-dir <validated-temp-dir> .
python -m pip check
git diff --check
```

The wheel must retain only the Jarvis package/resources, GPL-3.0-only metadata, Python >=3.12,
zero runtime dependencies, and all M006C fixed commands. Installed acceptance uses disposable
HOME/XDG/PATH and controlled user-systemd fixtures; it must verify fresh Auto setup and help
without inference. CPython 3.12 and 3.14 are required; report 3.13 availability without
downloading it.

## Manual verification

1. Create disposable HOME, XDG, PATH, installation, runtime, model, and service roots.
2. Initialize fresh state and inspect defaults: schema 5, product 6, model context Auto/0.
3. Complete first-run setup with blank context and confirm persisted zero and Auto presentation.
4. Repeat with explicit 0 and explicit numeric context; confirm wire values and display.
5. Inspect exact provider argv for Auto and explicit values.
6. Start a compatible local GGUF where available, confirm readiness `/props` effective context and
   successful Auto chat. Do not download or modify model files.
7. Start the reported GGUF with the saved configuration and confirm a bounded generic model-load
   incompatibility message, with no raw stderr/path/tensor disclosure.
8. Change Auto↔explicit through the existing stop/update/start lifecycle and verify runtime IDs,
   argv, and prompt budget.
9. Build/install the wheel in disposable roots, run M006C fixed help and chat/setup paths, and
   confirm source independence and no unrelated PATH/service mutation.
10. Run the complete verification commands, record evidence here, and remove only validated
    disposable roots.

## Discoveries

- The current branch is clean at `4debfbf`; M006C is complete despite a stale roadmap sentence
  that previously called it the next not-started milestone. This materialization corrects only the
  roadmap status and adds M006D.
- Upstream and local llama-server b8681 document `--ctx-size` default 0 as model-loaded context.
- Jarvis currently defaults to 8192 and unconditionally emits `--ctx-size`.
- The reported 12.7 GiB Qwen3.8 GGUF reproduces `missing tensor 'blk.64.ssm_conv1d.weight'` during
  llama-server loading. This is a generic model/runtime incompatibility, not evidence that 32768
  context caused startup failure.
- Current llama-server defaults are batch 2048, ubatch 512, GPU layers auto, threads CPU-auto, and
  flash-attention auto. Jarvis currently forces GPU layers 0 and threads 1, but no compatible-GGUF
  A/B failure currently authorizes changing them.

## Architectural decisions

- **2026-08-22 — Accepted — Auto value:** `context_window = 0` is Jarvis Auto; positive values
  through 1,000,000 are explicit. This is the approved product decision.
- **2026-08-22 — Accepted — Defaults versioning:** bump product defaults 5→6, retain schema 5,
  add no SQL migration, and preserve existing persisted explicit values.
- **2026-08-22 — Accepted — Native context argv:** omit `--ctx-size` for Auto and let llama-server
  load model-derived context; emit the exact flag/value for explicit configuration.
- **2026-08-22 — Accepted — Effective Auto budget:** read bounded `GET /props` after readiness and
  pass `default_generation_settings.n_ctx` to Context Builder; never use numeric zero as budget.
- **2026-08-22 — Accepted — Lifecycle:** Auto↔explicit changes are runtime-affecting and use the
  existing stop/update/start lifecycle; no silent live reconfiguration is introduced.
- **2026-08-22 — Accepted — Setup/presentation:** blank and explicit 0 mean Auto; human UI says
  Auto; machine-readable configuration retains numeric zero.
- **2026-08-22 — Accepted — Error quality:** preserve bounded allowlisted startup reason classes,
  render safe human messages, and exclude raw provider output from IPC/model context.
- **2026-08-22 — Accepted — Runtime-default restraint:** do not change GPU/thread/batch/timeout
  defaults unless a compatible GGUF proves one single generic forced-argument defect.
- **2026-08-22 — Accepted — Incident classification:** the reproduced Qwen GGUF is a generic
  model-load incompatibility and receives no model-specific exception.

## Deviations from the original plan

No implementation deviation. The optional real-GGUF matrix could not run because no local GGUF was
available; no download was permitted. This ExecPlan is the approved M006D compatibility/UX hotfix scope. The roadmap status sentence
was corrected to reflect completed M006C, and M006D was inserted before M007 as an explicitly
authorized not-started submilestone.

## Unresolved issues

None at materialization. A compatible-GGUF A/B test may discover one single generic forced-argument
defect; that discovery must be recorded here before any additional runtime default is changed. If
no such evidence appears, no additional default change is permitted.

## Completion criteria and evidence

M006D is complete only when all are DONE:

- Auto/domain/default/product-version/wire/reset/persistence compatibility passes.
- Auto and explicit argv contracts are exact and permanently tested.
- Effective Auto context is obtained after readiness and used by Context Builder.
- Setup, `/context`, configuration inspection, and machine-readable wire semantics distinguish Auto.
- Auto↔explicit changes follow safe runtime lifecycle semantics.
- Startup failures expose bounded generic reason classes without raw provider data.
- Reported incompatible GGUF and compatible local GGUF acceptance paths are recorded where possible.
- All predecessor marker suites, full pytest, Ruff, format, strict mypy, wheel, pip check, installed
  M006C acceptance, and `git diff --check` pass.
- Repository status is clean except deliberate, reviewable M006D documentation/source changes;
  no commit or push is performed by this plan.

## Handoff summary

Current state: implementation and automated verification are complete. No M007 work was begun.
The only unavailable optional evidence is real-local-GGUF acceptance because the environment had no
GGUF. Preserve the established installation/security boundaries and do not add runtime-default
changes without independent compatible-model evidence.
