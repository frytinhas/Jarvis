# AGENTS.md

# Jarvis-CLI — Authoritative Project Instructions

## 1. Purpose of This Document

This file is the authoritative architectural and behavioral specification for **Jarvis-CLI**.

Coding agents working in this repository must treat this document as a project contract.

When implementation details are unclear:

1. follow this document;
2. preserve its architectural invariants;
3. choose the safest deterministic behavior;
4. avoid inventing behavior that conflicts with stated requirements;
5. ask for clarification only when a genuinely unresolved product decision blocks correct implementation.

Do not preserve architectural decisions from previous Jarvis-CLI versions unless explicitly compatible with this file.

---

# 2. Project Overview

**Jarvis-CLI** is a fully local, privacy-first AI assistant for Linux.

It provides a safe orchestration layer between:

- the user;
- local GGUF models;
- the operating system;
- local files;
- installed applications;
- processes;
- scripts and executables;
- the desktop;
- the internet;
- conversation history;
- persistent memories;
- profile-specific personas;
- model-private notes;
- future voice and desktop interfaces.

The language model is a planner and conversational system.

It is **not** the operating-system authority.

Core rule:

```text
LLM proposes actions.
Jarvis validates actions.
Policy Engine authorizes actions.
Tool Broker executes actions.
Audit systems record actions.
```

The model must never directly gain unrestricted host access.

---

# 2A. Model-Content Neutrality and Host Authority

Jarvis must remain neutral about the generated-content behavior of user-selected local models.

For locally hosted models, Jarvis **MUST NOT** automatically inject behavioral rules derived from
OpenAI, Anthropic, Google, Meta, Microsoft or any other model provider merely because Jarvis or its
development tooling was created using those systems. Jarvis must not silently add instructions to
refuse harmful, cybersecurity or controversial requests, follow a hosted provider's policy, or
otherwise adopt a third party's acceptable-use rules. Such behavior is permitted only when the
user explicitly selects or configures it as profile persona, profile context or model/prompt
configuration.

Jarvis must not add a hidden semantic censorship or content-moderation layer for local inference.
Solely to enforce a third-party/provider content policy, it must not censor, rewrite, replace with a
refusal, suppress or prevent generation based on subject matter, purpose, opinion or generated
text. This includes cybersecurity, security research, reverse engineering, exploit analysis and
malware analysis. The selected local model remains responsible for its generated-content behavior
according to its training and native behavior together with the explicitly configured profile
persona, profile context and user-selected model/prompt settings. Subject to that behavior, the
model may generate arbitrary text without first obtaining host-capability authorization.

The governing distinction is:

```text
model output freedom != host execution authority
```

Conceptually:

```text
User
  |
  v
Profile persona/context and explicit user configuration
  |
  v
Local model
  |
  | generated text / structured tool request
  v
Tool Broker / Policy Engine
  |
  | capability decision
  v
Host / external capability
```

The Policy Engine is a **capability authorization engine**, not a content-moderation engine. It
decides whether a validated operation may use a host or external capability based on the requested
operation, the profile's configured `allow`/`ask`/`deny` state and explicit architectural integrity
constraints. It must not classify the model's topic, purpose, opinion or text as acceptable or
forbidden. For example, `DELETE = ask` requires approval because deletion is configured as `ask`,
not only when Jarvis semantically considers the reason dangerous. Likewise, a capability set to
`allow` must not silently become `ask` or `deny` because a provider-specific content policy would
disfavor the subject matter.

Content neutrality does not weaken any explicit Jarvis integrity boundary. Active-installation
protection, IPC/runtime integrity, profile and profile/model isolation, permission and confirmation
enforcement, filesystem/process/tool authority, secret handling, privacy, network controls,
resource bounds, update authenticity and authority, executable identity, and diagnostic/audit
isolation remain mandatory. These controls govern what Jarvis is technically authorized to do,
not what subjects a model may discuss. A structurally forbidden operation remains forbidden even
when the relevant profile capability is `allow`; every such exception must be documented as an
architectural integrity constraint and must not masquerade as semantic content moderation.

Users may intentionally configure behavioral restrictions in a profile's persona, context or
model/prompt settings. Jarvis does not need to remove alignment or refusal behavior intrinsic to a
selected model, and it does not promise that a model will comply with every prompt. The prohibition
is against Jarvis secretly imposing an additional provider-specific policy.

The provider architecture must remain behaviorally neutral. Local providers use Jarvis-owned
prompt/context construction and must follow this rule. A future optional external provider may
independently enforce server-side policies outside Jarvis's control; Jarvis cannot guarantee their
removal, and such provider-enforced behavior must not be represented as a Jarvis policy. Providers
must not be assumed to share identical behavioral policies.

Prompt construction must be auditable by source. Every persistent or system-level Jarvis-owned
prompt component must have identifiable provenance, limited to documented product protocol/tool
instructions, profile persona, profile context, explicit user-configured behavioral instructions,
and required technical formatting or tool-use instructions. Jarvis must not contain an
undocumented hidden provider-policy prompt layer. Prompt-inspection user experience may be added in
a future authorized milestone; this rule does not require it now.

---

# 3. Fundamental Product Requirements

Jarvis-CLI must be:

- fully local for inference;
- privacy-first;
- telemetry-free;
- multi-profile;
- local-user scoped;
- Wayland-oriented;
- modular;
- debuggable;
- auditable;
- configurable;
- safe by default;
- extensible to future interfaces.

No cloud AI service is required for normal operation.

No user conversation, profile context, model note, memory or private file may be silently uploaded to a third party.

---

# 4. Priority Order

When requirements compete, prefer:

1. Security
2. User control
3. Data isolation
4. Predictability
5. Correctness
6. Privacy
7. Debuggability
8. Modularity
9. User experience
10. Performance
11. Extensibility

Performance improvements must not bypass safety boundaries.

---

# 5. Initial Platform Scope

Initial supported systems:

- Ubuntu;
- Debian;
- Debian-derived Linux distributions.

Primary target:

```text
Linux
Ubuntu
Wayland
systemd
```

Jarvis must not be architected around X11-only mechanisms.

Do not assume GNOME exclusively.

Desktop integrations should support abstractions for:

- GNOME;
- KDE Plasma;
- wlroots-based compositors.

Prefer:

- XDG specifications;
- XDG Desktop Portal;
- D-Bus;
- standard desktop entries;
- accessibility APIs where appropriate.

---

# 6. Source Language

All internal project development must use English.

This applies to:

- source code;
- variable names;
- functions;
- classes;
- modules;
- comments;
- docstrings;
- database entities;
- configuration keys;
- internal events;
- log schemas;
- error identifiers;
- tests;
- developer documentation.

User-facing text must be localization-ready.

The AI assistant should normally respond using the language currently used by the user.

---

# 7. License

Jarvis-CLI uses:

```text
GPL-3.0
```

The repository must include an appropriate GPL-3.0 license file.

Dependencies must have compatible licenses.

---

# 8. High-Level Architecture

Jarvis-CLI uses a client/core architecture.

```text
                        User
                         │
               ┌─────────┴─────────┐
               │                   │
             CLI                  TUI
               │                   │
               └─────────┬─────────┘
                         │
                    Local IPC
                         │
                   Jarvis Core
                     jarvisd
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
   Profiles            Agent              Memory
      │                  │                  │
      └──────────────────┼──────────────────┘
                         │
                    Policy Engine
                         │
                     Tool Broker
                         │
   ┌──────────┬──────────┼──────────┬──────────┐
   │          │          │          │          │
 Files      Apps       Shell       Web      Desktop
   │          │          │          │          │
   └──────────┴──────────┴──────────┴──────────┘
                         │
                     Linux Host

                   Jarvis Core
                         │
                    localhost
                         │
                  llama-server
                         │
                    GGUF model
```

Future clients:

```text
CLI ─────────┐
TUI ─────────┤
Voice ───────┼──> Jarvis Core
Desktop App ─┘
```

CLI, TUI, Voice and Desktop App must not implement separate agent brains.

---

# 9. Initial User-Facing Commands

Installation should expose at minimum:

```text
jarvis
jarvis-config
jarvis-update
jarvis-clear
jarvis-manage
jarvis-help
```

Additional dynamically registered profile commands are described later.

Potential future management commands may be added when justified.

Avoid creating many unrelated executables when a coherent subcommand belongs under `jarvis-manage`.

---

# 10. `jarvis`

`jarvis` is:

1. the command for the permanent default profile;
2. the main interactive Jarvis entry point;
3. the one-shot default-profile command.

Examples:

```bash
jarvis
```

opens the interactive interface for the default `jarvis` profile.

```bash
jarvis "open spotify"
```

executes a one-shot natural-language request using the `jarvis` profile.

```bash
jarvis "what is today's weather?"
```

may use authorized web tools.

---

# 11. Help Entry Points

Help must be easily discoverable.

All of the following must work:

```bash
jarvis -h
jarvis --help
jarvis --h
jarvis-help
```

`jarvis -h`, `jarvis --h` and `jarvis --help` must not start a model.

`jarvis-help` must provide equivalent general help.

Interactive sessions must also support:

```text
/help
```

Profile command aliases must support equivalent help behavior.

Example:

```bash
joao -h
joao --help
```

---

# 12. Profiles Are First-Class

Profiles define independent AI identities and environments.

Examples:

```text
jarvis
joao
work
programming
unreal
research
```

Every profile owns or references its own:

- persona;
- persistent profile context;
- selected model;
- per-model runtime configuration;
- permissions;
- interface colors;
- appearance preferences;
- visible logging mode;
- waiting messages;
- goodbye messages;
- learning state;
- conversation records;
- model-private notes;
- model chat logs;
- optional startup behavior;
- network permissions;
- tool permissions.

---

# 13. Permanent Default Profile

There is always a profile named:

```text
jarvis
```

This profile is created during first installation or first initialization.

The `jarvis` profile:

- can never be deleted;
- can never lose its canonical command name;
- may be reset;
- may be reconfigured;
- serves as the template for newly created profiles.

---

# 14. New Profile Creation

New profiles are created through:

```bash
jarvis-config
```

The configuration UI must include:

```text
Create new profile
```

Do not require the user to create profiles through command-line flags.

New profile creation flow:

```text
jarvis-config
    ↓
Create new profile
    ↓
Choose display name
    ↓
Validate and normalize command name
    ↓
Clone configurable defaults from jarvis profile
    ↓
Create profile
    ↓
Register profile command
```

---

# 15. New Profiles Clone Jarvis

A new profile starts from the current configurable state of the `jarvis` profile.

This means that creating a new profile must copy suitable configuration such as:

- permissions;
- visual settings;
- waiting messages;
- goodbye messages;
- default persona template;
- profile context template;
- profile-facing configuration;
- model selection if appropriate;
- compatible model settings.

Do **not** copy historical or learned data from Jarvis.

The following must start empty for the new profile:

```text
conversation history
private model notes
chat diagnostic logs
learning state history
episodic memories derived from prior sessions
profile-specific learned user data
```

A cloned profile inherits configuration, not Jarvis's historical identity data.

---

# 16. Profile Display Names

Profile creation may accept:

- uppercase letters;
- lowercase letters;
- numbers;
- spaces.

The user-facing display name may preserve capitalization and spaces.

Example:

```text
Display name:
João Trabalho
```

However the executable terminal command must be normalized.

---

# 17. Profile Command Name Normalization

Profile executable names must be deterministic.

Rules:

1. convert to lowercase;
2. normalize Unicode characters where necessary;
3. remove unsupported accents/diacritics when creating the shell-safe identifier;
4. convert spaces to hyphens;
5. allow only ASCII lowercase letters, digits and hyphens in the final executable identifier;
6. collapse consecutive hyphens;
7. remove leading and trailing hyphens.

Example:

```text
Display Name: João Trabalho
Command: joao-trabalho
```

Example:

```text
Display Name: MY AI 2
Command: my-ai-2
```

---

# 18. Profile Name Validation

A profile name must contain at least one alphanumeric character.

Names that normalize to an empty identifier are invalid.

The normalized command must not conflict with:

- an existing profile command;
- Jarvis core commands;
- installation management commands;
- protected executable names.

Reserved names include at minimum:

```text
jarvis
jarvis-config
jarvis-update
jarvis-clear
jarvis-manage
jarvis-help
jarvisd
```

The display name `Jarvis` belongs to the permanent default profile and may not be used for another profile.

---

# 19. Profile Commands

Every additional profile must be directly callable using its normalized command.

Logical alias persistence and resolution are separate from physical command exposure. Milestone 003
owns the normalized alias to stable ProfileId mapping only. Milestone 006B owns a runnable and
testable development/package-level invocation mechanism: `python -m jarvis.cli` selects the
default profile and `python -m jarvis.cli --profile-alias <alias> [request]` resolves a logical
alias through Core. This is not final user PATH exposure. Milestone 006B owns the
assistant-facing CLI semantics.
Milestone 019A owns final user-local executable exposure, including PATH integration and physical
alias lifecycle. Earlier milestones must not temporarily assign configuration semantics to
`jarvis` or a profile command.

Example profile:

```text
Display name: João
Command: joao
```

Usage:

```bash
joao
```

must open that profile.

```bash
joao "open spotify"
```

must execute the one-shot request under that profile.

The user should not normally need:

```bash
jarvis --profile joao
```

That is not the intended UX.

Internally, profile-aware APIs may still use explicit profile IDs.

---

# 20. Dynamic Profile Command Registration

Physical profile commands must be implemented using safe generated launchers, symlinks or
equivalent user-level dispatch when Milestone 019A exposes them through the user-local
installation.

They must resolve to the same installed Jarvis client.

Do not create separate copies of Jarvis for each profile.

M003 must not create executables, launchers, symlinks, wrappers, filesystem alias registries, or
PATH entries. M006B may provide a development/package-level invocation mechanism so its CLI MVP is
runnable and testable before installation: `python -m jarvis.cli` for Jarvis and
`python -m jarvis.cli --profile-alias <alias> [request]` for a logical alias. It must not claim
final PATH installation or dynamic physical profile-command management. M019A owns the final
strategy, external executable collision handling, reconciliation and repair, rename/delete cleanup,
and uninstall behavior.

Conceptually:

```text
jarvis      -> Jarvis CLI + profile_id=jarvis
joao        -> Jarvis CLI + profile_id=<joao-profile>
work        -> Jarvis CLI + profile_id=<work-profile>
```

Removing or renaming a profile must clean up its registered command safely.

---

# 21. Profile Renaming

Profiles other than `jarvis` may be renamed.

Renaming includes:

- changing display name;
- recalculating normalized command name;
- checking collisions;
- updating the logical alias immediately;
- replacing the physical command registration only when physical exposure exists;
- preserving profile identity and data.

The underlying profile should use a stable internal ID independent of its display name and command alias.

Do not key historical data exclusively by profile command string.

---

# 22. Jarvis Profile Naming

The permanent `jarvis` profile's canonical executable remains:

```text
jarvis
```

Its command name cannot be changed.

The UI may allow editing presentation metadata if later desired, but the canonical profile identity remains Jarvis.

---

# 23. Profile Deletion

Profiles other than `jarvis` may be deleted through a clearly destructive workflow.

Deletion must require explicit confirmation.

The permanent `jarvis` profile:

```text
MUST NEVER BE DELETABLE
```

This must be enforced in the profile service, not merely hidden in the UI.

---

# 24. Profile Reset

Every profile, including `jarvis`, must support reset.

Profile reset must:

1. restore persona to its default;
2. restore profile context to its default;
3. erase conversation history stored for models inside that profile;
4. erase private model notes inside that profile;
5. erase chat logs belonging to models inside that profile;
6. erase learned memory belonging to that profile;
7. clear active learning-session data;
8. reset profile-specific customization to defined defaults where the reset UI indicates it will do so.

Before execution, the UI must clearly display exactly which categories will be erased.

Reset must require confirmation.

Reset means restoration to the applicable centrally defined, versioned product defaults.

It does not mean cloning the current mutable configuration of the `jarvis` profile and it does not restore an undocumented creation-time snapshot.

Profile creation is a separate operation: new profiles clone the current configurable state of `jarvis` as described above.

Reset and deletion must be coordinated centrally across every profile-owned subsystem. Before destructive work begins, Jarvis must quiesce or explicitly cancel active profile sessions, generations and runtimes. Each participating store must report its planned and completed work so partial external cleanup cannot be reported as success.

---

# 25. Reset Options

Configuration menus should expose reset actions at sensible levels.

Examples:

```text
Reset this setting
Reset this section
Reset model configuration
Reset permissions
Reset appearance
Reset profile
```

Every configurable menu section should have a route to restore defaults.

A destructive full-profile reset must not occur accidentally when resetting one setting.

---

# 26. Profile Runtime Concurrency

Multiple profiles may run simultaneously.

Example:

```text
jarvis → model A
joao   → model B
work   → model A
```

This is valid.

The same GGUF model may be used by any number of different profiles.

However:

```text
ONE ACTIVE MODEL SERVER MAXIMUM PER PROFILE
```

A profile must never run two model-server instances simultaneously.

Initially, generations targeting the same profile runtime must be serialized through a deterministic FIFO queue. Different profiles may generate concurrently.

Changing the active model for a profile must wait for the active generation to finish or explicitly cancel it and record that outcome. Only after the old runtime is no longer active may the replacement runtime start.

---

# 27. Same Model Across Profiles

The same GGUF may run in several profiles simultaneously.

Example:

```text
jarvis -> qwen.gguf
work   -> qwen.gguf
joao   -> qwen.gguf
```

These are different profile runtimes.

Their:

- conversations;
- private notes;
- logs;
- persona;
- context;
- learning state;

must remain isolated.

---

# 28. Per-Profile / Per-Model Storage

Every model that has operated inside a profile gets a dedicated private storage namespace.

Conceptually:

```text
profiles/
└── jarvis/
    └── models/
        ├── model-id-a/
        │   ├── notes/
        │   ├── conversations/
        │   ├── chat-logs/
        │   └── state/
        │
        └── model-id-b/
            ├── notes/
            ├── conversations/
            ├── chat-logs/
            └── state/
```

The exact physical persistence may use SQLite and structured files rather than literal folders for everything, but the isolation semantics must be equivalent.

---

# 29. Profile + Model Identity

Private model data belongs to:

```text
profile_id + model_id
```

Never only:

```text
model_id
```

Example:

```text
profile=jarvis + model=qwen
```

is independent from:

```text
profile=work + model=qwen
```

---

# 30. Persona and Context Ownership

Persona and profile context belong to the profile.

Models working inside that profile must follow the active profile's:

- persona;
- persistent context;
- language behavior;
- permissions;
- presentation configuration.

Models do not bring a persona from another profile.

---

# 31. Model-Private Data

Each model working inside a profile gets its own:

- private notes;
- chat conversations;
- chat diagnostic logs;
- model learning state;
- model-specific memory where applicable.

Model-private notes must not automatically cross model boundaries.

Initial learned and derived private data, including learning history, episodic memory and semantic memory, must also remain scoped to `profile_id + model_id`. A future explicitly designed profile-shared memory class may be added, but it must not be inferred implicitly from model-private data.

---

# 32. Model Log Isolation

Language models must never have direct access to:

- their own raw diagnostic logs;
- another model's diagnostic logs;
- another profile's logs;
- Jarvis infrastructure logs;
- audit logs.

Logs are not a memory source.

They must not be added to model context.

---

# 33. Purpose of Diagnostic Logs

Detailed logs primarily exist for:

- developers;
- debugging;
- external development assistants;
- Codex;
- Claude;
- maintainers;
- troubleshooting.

They are not intended as conversational memory.

When the user explicitly provides logs to a development tool, that is outside Jarvis model-context behavior.

---

# 34. Diagnostic Logs Are Always Persisted

Every chat session must produce complete diagnostic logs sufficient for troubleshooting.

These logs must be persisted locally.

The user-visible logging level does **not** decide whether core diagnostic logs are created.

Instead it controls how much execution information is shown interactively to the user.

This resolves the distinction between:

```text
diagnostic persistence
```

and:

```text
interactive logging verbosity
```

Profile/model chat diagnostics are owned by `profile_id + model_id` and additionally carry session/request/turn identifiers where applicable. Installation and infrastructure diagnostics are stored separately and are not model-private data. Audit records are a third operational store.

None of these diagnostic or audit stores may implement a model-context or memory-retrieval interface. Human-facing diagnostic access must use a dedicated Core-to-client route that cannot be passed to the Context Builder.

---

# 35. User-Facing Logging Modes

Every profile has its own visible logging mode.

Supported values:

```text
full
server-essential
essential
essential-minimum
none
```

Default:

```text
essential-minimum
```

These are Jarvis product modes.

---

# 36. `essential-minimum`

Default mode.

Display only concise descriptions of what is happening.

Examples:

```text
Reading ~/Documents/report.txt
Opening Spotify
Searching installed applications
Creating ~/Projects/test.txt
Searching the web
Running build.sh
```

Do not expose unnecessary implementation details.

---

# 37. `essential`

Show:

```text
tool-name: simple action (elapsed / timeout)
```

Example:

```text
filesystem.read: Reading ~/Documents/report.txt (0.4s / 30s)
```

Example:

```text
apps.launch: Opening Spotify (0.2s / 10s)
```

Tool output should remain understandable to ordinary users.

---

# 38. `server-essential`

Show useful model-runtime and server information in addition to essential operational events.

Examples:

```text
model startup
model shutdown
health state
generation start
server failure
restart attempt
runtime timeout
```

Do not automatically dump every low-level llama.cpp message.

---

# 39. `full`

Show detailed interactive diagnostic information intended for advanced debugging.

May include:

```text
tool identifiers
tool duration
model request events
runtime state transitions
memory retrieval summary
permission evaluation
network request metadata
server events
```

Secrets must still be redacted.

---

# 40. `none`

Do not display operational logging during normal conversation.

Necessary prompts such as:

- user approvals;
- errors;
- destructive-action confirmation;
- critical failures;

must still appear.

Diagnostic logs are still persisted locally.

---

# 41. Diagnostic Log Contents

Complete diagnostic logs should support correlation through identifiers such as:

```text
profile_id
model_id
runtime_id
session_id
request_id
turn_id
tool_call_id
```

They may include:

- model server output;
- model lifecycle;
- request metadata;
- tool calls;
- tool results;
- timings;
- errors;
- permission decisions;
- memory retrieval metadata;
- active configuration metadata;
- sanitized runtime details.

Do not unnecessarily store huge content blobs when metadata plus bounded excerpts are sufficient for troubleshooting.

---

# 42. Log Security

Logs must redact or avoid storing:

- passwords;
- authentication tokens;
- cookies;
- private keys;
- API credentials;
- secret environment variables;
- bearer tokens;
- authorization headers;
- credentials embedded in URLs.

Use centralized redaction.

Do not rely on every call site to sanitize manually.

---

# 43. Storage Limits

Every profile must have configurable local storage limits.

Safe defaults must be provided at installation.

Limits must include at least:

```text
maximum total diagnostic log storage
maximum chat log size
maximum retained conversation storage
maximum private notes storage
maximum downloadable file size
maximum tool-created temporary file size
maximum cache storage
```

Where appropriate, limits may also support:

```text
maximum per-file size
maximum per-session size
maximum per-model size
maximum per-profile size
retention age
```

---

# 44. Storage Limit Behavior

When a limit is reached, behavior must be deterministic.

Do not silently corrupt or arbitrarily delete active data.

Prefer policies such as:

```text
rotate oldest eligible logs
archive or prune oldest conversation records
refuse oversized downloads
refuse oversized generated temporary artifacts
warn before storage exhaustion
```

Critical active-session data must not be deleted while being written.

Deletion policies must be documented.

Quota defaults, accounting and reservation primitives must exist before the first data-producing subsystem. Each subsystem must enforce its applicable limits from the moment that subsystem is introduced; enforcement must not be deferred until a later cleanup interface exists.

Before a chat starts, Jarvis must be able to reserve enough bounded storage for the minimum diagnostic record required for that session. It may rotate only closed, eligible records. If it cannot preserve a sufficient auditable record, it must fail safely before unlogged work begins. Large payloads may be replaced by bounded excerpts plus explicit truncation metadata, while structural lifecycle and error events remain recorded.

---

# 45. Model Configuration Ownership

Models are configured in the context of a profile.

A GGUF file may be configured differently in different profiles.

Example:

```text
jarvis + qwen:
    reasoning = high
    context = 32768

work + qwen:
    reasoning = low
    context = 16384
```

Do not assume one global configuration per GGUF.

---

# 46. Required Model Settings

Per-profile/per-model settings must include at least:

```text
reasoning level
context window size
```

Supported reasoning levels:

```text
off
low
medium
high
max
```

The provider layer maps these conceptual levels to model-specific behavior.

---

# 47. Advanced Model Settings

Advanced configuration may include:

```text
temperature
top_p
top_k
min_p
repeat penalty
GPU layers
threads
batch size
flash attention
llama-server arguments
startup timeout
generation timeout
tool timeout
network timeout
shutdown timeout
model-specific chat-template options
```

Do not expose unsafe free-form shell concatenation.

Runtime arguments must be represented as structured values.

---

# 48. `jarvis-config`

`jarvis-config` is the primary configuration interface for ordinary users.

The first step must always be profile selection.

Example:

```text
Jarvis Configuration

Select a profile:

> Jarvis
  João
  Work

  + Create new profile
```

Once a profile is selected, configuration edits apply to that profile.

---

# 49. `jarvis-config` Main Menu

The normal user menu should prioritize common options.

Suggested sections:

```text
Model
Reasoning
Context window
Persona
Profile context
Permissions
Appearance
Colors
Waiting messages
Goodbye messages
Startup behavior
Internet access
Learning
Profile management
Advanced
Reset
```

The UI must remain intuitive.

Do not surface dozens of low-level llama.cpp settings on the main page.

---

# 50. Advanced Configuration

Advanced settings remain accessible from `jarvis-config`, but under an explicitly separate:

```text
Advanced
```

section.

Advanced options include:

```text
visible logging mode
diagnostic storage limits
temperature
sampling
GPU layers
threads
batch size
timeouts
runtime arguments
server diagnostics
cache limits
conversation limits
log limits
network limits
```

Advanced configuration must still be safe and structured.

---

# 51. Configuration Reset

Every configuration category must offer a reasonable:

```text
Reset to default
```

action.

Examples:

```text
Reset colors
Reset permissions
Reset model settings
Reset storage limits
Reset timeouts
Reset persona
Reset context
Reset advanced settings
```

Defaults must be defined centrally and versioned.

---

# 52. Installation-Level Configuration

Jarvis should minimize truly installation-wide configuration.

Anything that can logically belong to a profile should belong to the profile.

Only settings that inherently describe the installed Jarvis environment may be installation-level.

Examples may include:

```text
GGUF model search directories
llama.cpp binary path
installation version
installation health
update source
update-check mechanism
installed command registrations
core daemon management
repair actions
```

---

# 53. `jarvis-manage`

Installation-specific settings and maintenance belong under:

```bash
jarvis-manage
```

rather than ordinary profile configuration.

Possible menu:

```text
Installation status
Model directories
llama.cpp runtime
Registered profiles
Update settings
Repair installation
Daemon status
Version
Diagnostics
Uninstall
```

Do not move ordinary profile preferences into `jarvis-manage`.

---

# 54. Model Directory

The user provides the directory or directories containing downloaded GGUF files.

Jarvis must not require downloading models itself.

`jarvis-manage` should allow managing model search directories.

Example:

```text
/home/user/models
/mnt/models
```

---

# 55. GGUF Discovery

Jarvis must scan configured model locations for:

```text
*.gguf
```

The scanner must:

- detect GGUF files;
- safely recurse according to configured behavior;
- avoid duplicate logical entries;
- retain canonical paths;
- expose file size;
- expose available GGUF metadata when reasonably parseable;
- detect missing files;
- refresh when requested;
- avoid modifying model files;
- avoid moving model files;
- avoid renaming model files.

Model files are user-owned.

---

# 56. Model Identification

A stable local `model_id` must be used internally.

Do not depend exclusively on filename.

Do not hash an entire multi-gigabyte GGUF file every startup.

Use a stable combination of appropriate information such as:

- canonical path;
- file metadata;
- parsed GGUF metadata;
- cached fingerprint.

---

# 57. llama.cpp Backend

Initial inference backend:

```text
llama.cpp / llama-server
```

Hide implementation behind a provider interface.

Example:

```python
class LLMProvider(Protocol):
    async def start(self, config: ModelRuntimeConfig) -> RuntimeHandle:
        ...

    async def stop(self, runtime: RuntimeHandle) -> None:
        ...

    async def health(self, runtime: RuntimeHandle) -> RuntimeHealth:
        ...

    async def chat(self, request: ChatRequest) -> ChatResponse:
        ...
```

Initial provider:

```text
LlamaCppProvider
```

Future providers may include local-compatible systems without changing the agent architecture.

---

# 58. Runtime States

Model runtimes should use explicit states:

```text
STARTING
READY
BUSY
ERROR
STOPPING
STOPPED
```

Optional additional states may be added when useful.

Clients must receive meaningful state events.

---

# 59. Runtime Lock

A profile runtime must be protected by a robust lock.

Use a combination where appropriate:

- PID;
- runtime lock;
- Unix socket;
- health check;
- runtime ID.

Do not rely on only a process-name search.

Stale runtime artifacts must be detectable and recoverable.

Exactly one Jarvis Core owner may coordinate a given user's XDG state at a time. Core startup must use atomic ownership of its lock and Unix socket and must distinguish a live owner from stale artifacts.

Runtime recovery and process actions must bind identity using more than a PID or process name. Use runtime IDs plus appropriate process evidence such as PID start time, executable identity, owned endpoint and health response. Jarvis must never terminate an unrelated process because a PID was reused or a stale record was trusted.

Port allocation and ownership must be race-safe. A runtime may become `READY` only after Jarvis verifies that the expected owned process is serving the expected local endpoint.

---

# 60. Profile Autostart

Each profile must have an optional:

```text
Start with computer
```

setting.

When enabled:

1. the profile runtime starts after the user's session starts;
2. it uses the last valid model associated with that profile;
3. if that model no longer exists, Jarvis must fail gracefully and record the condition;
4. it must not silently select an unrelated model unless explicitly designed and communicated.

Autostart is per profile.

Autostart does not create a second Core or a separate owner of a profile runtime. One user-level Jarvis Core owns runtime coordination. Per-profile autostart is desired state consumed by that Core, or by a thin activation request sent to that Core.

Runtime startup, health checks and autostart do not consume first-run learning state.

---

# 61. User-Level Autostart

Autostart must be installed as user-level behavior.

Prefer:

```text
systemd --user
```

Do not require root merely to start Jarvis with the user's session.

---

# 62. Installation Scope

Jarvis installs only for the local user who runs the installer.

The installation must not become a machine-wide system installation by default.

Jarvis configuration, profiles and data belong only to that user.

Different Linux users must have isolated Jarvis installations and profile data.

---

# 63. XDG Storage

Use XDG paths.

Recommended semantics:

```text
$XDG_CONFIG_HOME/jarvis-cli/
$XDG_DATA_HOME/jarvis-cli/
$XDG_STATE_HOME/jarvis-cli/
$XDG_CACHE_HOME/jarvis-cli/
$XDG_RUNTIME_DIR/jarvis-cli/
```

with standards-compliant fallbacks.

Do not mix persistent configuration with ephemeral runtime state.

---

# 64. Installation Protection

The installed Jarvis instance is immutable from the agent's perspective.

Jarvis models and tools must never modify the currently active Jarvis installation.

This includes:

- source files belonging to the active installation;
- installed Python package files;
- installed executables;
- runtime code;
- active configuration implementation files;
- update infrastructure.

---

# 65. Self-Modification Prohibition

Jarvis must not use tools to:

- patch itself;
- replace its own installed files;
- edit its own active source;
- update itself;
- modify its currently executing package;
- bypass `jarvis-update`.

The Tool Broker must protect the active installation path.

This must be a real policy boundary.

---

# 66. Cloned Repository Exception

The user may separately clone the Jarvis-CLI GitHub repository into an ordinary development directory.

Example:

```text
~/Projects/Jarvis-CLI
```

If this path is not the currently active installation, Jarvis may work on it like any other user project, subject to normal permissions.

Example:

```text
Active installation:
~/.local/...

Development clone:
~/Projects/Jarvis-CLI
```

Jarvis may edit the development clone.

It may not edit the active installation.

---

# 67. Updates

Only:

```bash
jarvis-update
```

may apply application updates.

Jarvis conversational tools cannot invoke an internal self-patch path that bypasses this boundary.

---

# 68. Update Checks

The installation should support periodic checking for new released versions.

Default:

```text
update checks enabled
```

Checking for updates must be transparent.

It must not upload user data.

Only minimal version/repository information should be exchanged.

Update checking is installation-scoped. It is not a profile INTERNET tool and it must use a narrowly configured update-check network path that cannot apply an update or transmit profile data.

---

# 69. Update Application

Finding an update and installing an update are different operations.

Update checks may detect a new release automatically.

Actual installation must happen through:

```text
jarvis-update
```

according to the updater's explicit workflow.

Do not silently replace the active installation while the user is chatting.

Jarvis Core must expose no IPC or conversational operation capable of applying an application update.

Only the separately invoked `jarvis-update` executable may acquire update authority and mutate protected installation files.

---

# 70. Update Source

`jarvis-update` updates from the official configured Jarvis-CLI GitHub release source.

The updater must:

1. inspect installed version;
2. query releases;
3. identify the latest appropriate stable release;
4. validate compatibility;
5. download the release artifact;
6. validate the artifact;
7. apply the update;
8. preserve user profiles and data;
9. perform post-update validation;
10. provide clear failure diagnostics.

Do not use:

```bash
curl URL | bash
```

as the normal updater.

---

# 71. Tool Permissions Defaults

Default profile permissions:

```text
CREATE   = allow
COPY     = allow
READ     = allow
SCREEN   = allow
INTERNET = allow
EXECUTE  = allow

DELETE   = ask
MODIFY   = ask
MOVE     = ask
```

These represent capability categories.

More granular tools inherit from these categories unless overridden.

---

# 72. Meaning of CREATE

CREATE includes creation of new user-owned resources such as:

```text
new files
new directories
new generated local artifacts
```

It does not imply permission to overwrite an existing file.

Overwriting existing content is MODIFY.

---

# 73. Meaning of COPY

COPY includes copying existing files or directories to a new destination.

If copying would overwrite an existing resource, MODIFY permission is also required.

---

# 74. Meaning of READ

READ includes:

```text
listing directories
reading files
inspecting metadata
searching filenames
searching file contents
reading system information
listing processes
```

when no mutation occurs.

`process.list` and other non-mutating process inspection inherit READ.

Sensitive future read categories may have more specific permission rules.

---

# 75. Meaning of SCREEN

SCREEN permits Jarvis to obtain allowed screen/context information through supported desktop mechanisms.

Screen access must still obey Wayland/portal requirements.

The permission does not imply bypassing compositor security.

---

# 76. Meaning of INTERNET

INTERNET permits explicit Jarvis web tools to access external resources.

It does not grant unrestricted outbound network access to the LLM runtime.

Network access for an explicitly executed program is denied by default at the execution boundary. An execution request must explicitly declare that network access is required; only then may Jarvis evaluate both EXECUTE and INTERNET. Omitting that declaration keeps process networking disabled even when both profile categories are configured as `allow`.

The Tool Broker must not claim that it can prevent arbitrary data upload after granting a process unrestricted network access. Networked execution therefore requires explicit bounded execution semantics and must still preserve the prohibition on silently uploading conversations, profile context, notes, memories or private files.

---

# 77. Meaning of EXECUTE

EXECUTE permits supported:

- application launches;
- explicit executable launches;
- explicit script execution.

Execution must still pass Tool Broker validation.

It does not grant sudo.

EXECUTE authorizes the ordinary side effects of the explicitly selected executable or script. Internal side effects performed by that program are not reinterpreted as separate Jarvis MODIFY, MOVE or DELETE tool calls.

This does not override absolute Jarvis security boundaries. Executed programs remain subject to:

- active Jarvis installation protection;
- sudo and elevation denial;
- controlled executable identity;
- controlled working directory;
- a filtered environment;
- resource, time and output limits;
- no conversational access to `jarvis-update` or protected installation lifecycle paths;
- the separate INTERNET requirement for process network access.

Process termination requires both EXECUTE and DELETE. Authorization must bind to a fresh process identity, including appropriate start-time/executable evidence, and never only to a PID.

---

# 78. Meaning of DELETE

DELETE covers deletion of existing resources.

Default:

```text
ask
```

Deletion must clearly identify its target.

Recursive or highly destructive deletion requires stronger handling.

---

# 79. Meaning of MODIFY

MODIFY covers changes to existing content.

Examples:

```text
editing a file
appending to a file
overwriting a file
changing existing configuration
```

Default:

```text
ask
```

---

# 80. Meaning of MOVE

MOVE includes:

```text
moving an existing file
moving a directory
renaming an existing resource
```

Default:

```text
ask
```

---

# 81. Permission Engine

Permissions must be centralized.

Supported decisions:

```text
allow
ask
deny
```

The model cannot change its own effective permissions.

Permission logic must not be duplicated ad hoc inside individual tools.

---

# 82. Approvals

When policy returns:

```text
ask
```

the UI must display:

- action;
- target;
- concise consequence;
- relevant arguments.

Example:

```text
Jarvis wants to modify:

~/Projects/example/config.toml

Action: Modify existing file

[y] Allow once
[a] Always allow matching action
[n] Deny
```

Permanent permission changes require explicit intent.

---

# 83. Sudo

Default:

```text
sudo = deny
```

Jarvis must never:

- silently use sudo;
- request or capture a sudo password for storage;
- save a sudo password;
- bypass user elevation mechanisms.

Elevated operations require a separately designed future authorization flow.

---

# 84. Tool Broker

All operating-system capabilities must go through the Tool Broker.

Initial namespaces may include:

```text
filesystem.*
system.*
process.*
apps.*
shell.*
web.*
desktop.*
clipboard.*
memory.*
```

The LLM must not receive unrestricted arbitrary code execution APIs.

---

# 85. Structured Tools First

Prefer structured tools over shell commands.

Use:

```text
filesystem.read
```

instead of:

```bash
cat
```

Use:

```text
filesystem.delete
```

instead of:

```bash
rm
```

Use:

```text
apps.launch
```

instead of model-generated desktop commands.

Shell execution is a fallback capability.

---

# 86. Filesystem Capabilities

Jarvis should support:

- current directory;
- home;
- Documents;
- Downloads;
- Desktop;
- user-configured directories;
- directory listing;
- metadata;
- bounded file reading;
- glob search;
- content search;
- create files;
- create directories;
- copy;
- edit;
- append;
- move;
- rename;
- delete files;
- delete empty directories.

Recursive destructive deletion must be explicitly designed and guarded.

Authorization based only on a previously canonicalized path is insufficient. Path-sensitive operations must use execution-time, descriptor-relative resolution and appropriate no-follow/link checks. Existing targets must be checked against expected identity/version metadata immediately before mutation.

Mutating tools must reject unsafe symlink swaps, hardlinks into the protected installation, changed targets, unexpected special files and stale path decisions. Protected-installation checks must account for protected file identity, not only path spelling.

---

# 87. File Size Protection

Reading and writing tools must obey configured file limits.

The model should not accidentally load a multi-gigabyte file into context.

File reading should support:

- bounded chunks;
- offsets;
- line ranges;
- metadata-first inspection.

Oversized operations must return typed errors or require explicit alternative handling.

---

# 88. Shell Execution

Shell execution should support:

- explicit `.sh` files;
- explicit executable files;
- known application binaries;
- structured argument arrays.

Prefer:

```python
[
    "/path/program",
    "--option",
    "value",
]
```

Do not build commands through unsafe string concatenation.

Avoid:

```python
shell=True
```

unless explicitly justified.

Validation and execution must refer to the same executable identity. Jarvis must fail safely if the executable, script, interpreter, working directory or relevant target changes between validation and execution. Where Linux facilities permit, execution should remain bound to an already validated file descriptor or equivalent stable identity.

Execution must not inherit an interactive privilege prompt, unrestricted stdin, secret environment variables or update authority. Network access remains disabled unless both EXECUTE and INTERNET authorize the bounded execution.

---

# 89. Application Discovery

Jarvis must find installed applications using user-friendly names.

Support:

- exact names;
- case-insensitive matching;
- accent-insensitive matching;
- reasonable aliases;
- minor spelling errors;
- `.desktop` metadata.

Example:

```text
Spotify
spotify
spotfy
```

may resolve to Spotify when confidence is sufficient.

---

# 90. Application Launch Priority

Prefer:

1. desktop entry;
2. XDG mechanism;
3. D-Bus;
4. official application CLI;
5. accessibility interface;
6. visual automation.

Do not click icons visually when a structured launch mechanism exists.

---

# 91. Wayland

Desktop capabilities must be Wayland-oriented.

Prefer:

- XDG Desktop Portal;
- D-Bus;
- accessibility APIs;
- compositor adapters.

Do not assume unrestricted global screen or input access.

---

# 92. Screen Reading

Screen understanding must be a dedicated tool path.

Concept:

```text
Desktop Adapter
      ↓
Screen Capture
      ↓
Local processing / local VLM
      ↓
Structured screen information
      ↓
Agent
```

Screenshots must never be sent to external AI services.

---

# 93. Internet Architecture

The LLM process does not need unrestricted internet access.

Provide explicit tools such as:

```text
web.search
web.fetch
web.download
```

Network policy belongs to Jarvis.

---

# 94. Telemetry

Jarvis-CLI must contain no:

- analytics SDK;
- behavior tracking;
- usage tracking;
- advertising;
- crash-report upload;
- hidden telemetry;
- remote configuration system.

No telemetry.

---

# 95. First-Run Learning Session

Every model's first run inside a profile starts in:

```text
Learning Session
```

This includes:

- the first ever run of the default `jarvis` profile;
- a model newly assigned to an existing profile;
- the first model used by a newly created profile.

The user must be clearly informed that learning mode is active.

For lifecycle purposes, the first run is the first user-facing Agent Engine chat transaction for a `profile_id + model_id` pair. Learning state must be initialized transactionally before that generation begins.

Model discovery, runtime startup, health checks and autostart do not consume or complete first-run learning state.

---

# 96. Learning Session Scope

Learning state belongs to:

```text
profile_id + model_id
```

Example:

```text
jarvis + qwen
```

may have completed learning.

But:

```text
work + qwen
```

is a separate first-run learning session.

---

# 97. Learning Session Purpose

During learning, the assistant may focus on learning useful interaction preferences and generating local private notes.

It must still follow the profile persona and context.

Learning mode must not weaken tool permissions.

---

# 98. Ending Learning

The user must be able to explicitly finish learning with an interactive command.

Canonical command:

```text
/learning finish
```

Aliases may be added, but this behavior must exist.

The assistant should confirm that learning has ended.

---

# 99. Restarting Learning

The user may restart learning whenever desired.

Canonical command:

```text
/learning start
```

It does not automatically erase previous memories unless the user explicitly chooses a reset option.

A separate action may offer:

```text
/learning reset
```

which must clearly describe what it will erase.

---

# 100. Learning Status

Support:

```text
/learning status
```

The interface should visibly identify an active learning session, especially at session start.

---

# 101. Learning Data

Learning may produce:

- profile/model private notes;
- summarized preferences;
- locally stored observations;
- relevant semantic memories.

All data remains local.

It must be:

- inspectable;
- erasable;
- resettable;
- isolated per profile/model where appropriate.

---

# 102. Persona

The default Jarvis persona should be inspired by the sophisticated AI-assistant behavior associated with Iron Man's Jarvis.

Do not reproduce copyrighted movie dialogue.

Default personality:

- polite;
- composed;
- professional;
- competent;
- respectful;
- concise when appropriate;
- subtly sophisticated;
- proactive without being intrusive.

In Portuguese, Jarvis may naturally address the user as:

```text
senhor
```

when appropriate.

Do not repeat it excessively.

---

# 103. Language Matching

Default persona behavior:

```text
User writes Portuguese -> respond in Portuguese
User writes English -> respond in English
User changes language -> follow the change
```

Profiles may override this behavior through explicit persona/context configuration.

---

# 104. Memory Layers

Jarvis distinguishes:

```text
Working Memory
Conversation History
Episodic Memory
Semantic Memory
Profile Context
Persona
Model-Private Notes
Diagnostic Logs
```

Diagnostic logs are not conversational memory.

---

# 105. Working Memory

Working memory contains only relevant active context.

It may include:

- recent chat turns;
- current tool results;
- active workspace;
- retrieved memories;
- relevant private notes;
- current user request.

It must be context-budget aware.

---

# 106. Conversation History

Conversation history is persisted locally per:

```text
profile + model + session
```

Users should eventually be able to search by:

- text;
- date;
- model;
- profile;
- session.

---

# 107. Episodic Memory

Contains locally generated summaries of relevant previous sessions.

Do not inject all episodes into every context.

Retrieve selectively.

---

# 108. Semantic Memory

Contains durable useful facts/preferences derived locally.

Semantic memory must be retrievable selectively.

External embedding APIs are forbidden.

If embeddings are used, they must be generated locally.

---

# 109. Private Notes

Private notes belong to a model operating inside a specific profile.

They may contain locally generated observations intended to improve future interactions.

They are not diagnostic logs.

---

# 110. Logs Are Not Model Input

Raw diagnostic logs must never be automatically:

- searched by the model;
- retrieved as memory;
- inserted into context;
- summarized into private notes.

This separation is mandatory.

---

# 111. Database

Use SQLite initially.

Suggested responsibilities:

```text
profiles
profile_aliases
models
profile_models
sessions
messages
memories
private_notes
learning_state
tool_calls
approvals
audit_events
runtime_events
settings
storage_usage
```

Use migrations.

---

# 112. FTS

SQLite FTS5 is preferred initially for local text search.

Use it for suitable:

- conversations;
- memories;
- notes.

Vector search is optional later.

---

# 113. Context Builder

Prompt/context construction must be centralized.

Potential order:

```text
documented product protocol/tool instructions
profile persona
profile context
explicit user-configured behavioral instructions
relevant capability and permission description
relevant model-private notes
relevant semantic memories
relevant episodic memories
workspace context
recent conversation
current request
```

Do not let unrelated modules append unlimited prompt text independently.

Every persistent or system-level prompt contribution must retain identifiable provenance. The
Context Builder must not inject an undocumented provider content policy or use a hidden semantic
moderation instruction. Capability/permission descriptions exist to explain available tools and
host authority; they are not topic-level content rules.

---

# 114. Interactive Commands

Interactive sessions should support at minimum:

```text
/help
/quit
/exit
/clear

/model
/reasoning
/context
/permissions

/history
/memory
/notes

/learning

/status
/server
/logs
/config
/license
```

Slash commands are handled by the client/core command system.

Do not send them blindly to the LLM.

---

# 115. `/model`

Support:

```text
/model
/model list
/model current
/model use <model>
```

Changing model must cleanly transition the profile runtime.

---

# 116. `/reasoning`

Support inspection and modification of active model reasoning behavior.

Example:

```text
/reasoning
/reasoning high
```

Validation must occur against supported conceptual levels.

---

# 117. `/permissions`

Must provide access to the current profile's permission state.

Complex editing may open a dedicated configuration view.

---

# 118. `/config`

Should open or direct the user to configuration for the active profile.

Equivalent external entry:

```text
jarvis-config
```

which always asks for profile first.

---

# 119. `/logs`

May display safe session/debug status according to UX policy.

It must not expose raw internal log content to the LLM itself.

The client may render logs directly for the human user.

---

# 120. `/license`

Must display or locate the GPL-3.0 license information.

---

# 121. `jarvis-clear`

`jarvis-clear` is a dedicated cleanup interface.

It must open an interactive menu showing categories that may be cleaned.

Potential categories:

```text
Private model notes
Old conversations
Diagnostic logs
Chat logs
Caches
Downloaded temporary files
Learning data
Inactive runtime artifacts
```

The user must be able to choose:

- profile;
- model where applicable;
- category;
- age/range where applicable;
- full category cleanup.

---

# 122. `jarvis-clear` Safety

Cleanup must clearly distinguish:

```text
temporary/cache data
historical conversation data
private learning data
diagnostic logs
```

Do not combine everything into one ambiguous:

```text
Clear all
```

without detailed confirmation.

Destructive cleanup requires confirmation.

---

# 123. TUI

The TUI is installed as part of Jarvis-CLI but remains architecturally independent from the simple CLI presentation.

Recommended stack:

```text
Textual
Rich
```

The TUI communicates with Jarvis Core through the same local protocol.

It must not bypass:

- Tool Broker;
- Policy Engine;
- profile isolation;
- runtime manager.

---

# 124. TUI Goals

Eventually support:

- beautiful chat layout;
- streamed output;
- Markdown;
- tool execution status;
- confirmations;
- profile name;
- model name;
- learning status;
- reasoning status;
- context usage;
- custom themes;
- profile-specific colors;
- debug panel;
- session history;
- permission editor;
- model selector;
- keyboard shortcuts.

---

# 125. Profile-Specific Appearance

Every profile has its own interface appearance configuration.

This includes at minimum:

```text
colors
accent
waiting messages
goodbye messages
```

Additional theme settings may be added.

Changing one profile's appearance must not change another profile.

---

# 126. Waiting Messages

Waiting messages are customizable per profile.

Possible phases:

```text
model startup
generation
tool execution
memory search
internet search
shutdown
```

Messages must never falsely claim an operation occurred when it did not.

---

# 127. Goodbye Messages

Goodbye messages are configurable per profile.

Default Jarvis examples should reflect its persona without reproducing movie dialogue.

---

# 128. Timeouts

Timeouts are advanced per-profile/per-model configuration where applicable.

Separate timeout classes:

```text
model startup
model health
generation
tool execution
shell execution
network request
screen capture
graceful shutdown
```

Do not use one global timeout for everything.

---

# 129. Error Types

Use typed errors such as:

```text
ProfileNotFound
ProfileNameConflict
ProtectedProfile
ModelNotFound
ModelAlreadyRunning
ModelStartTimeout
ModelRuntimeFailed
ToolPermissionDenied
ToolExecutionFailed
InvalidPath
FileTooLarge
StorageLimitExceeded
NetworkDenied
DatabaseError
IPCProtocolError
ProtectedInstallationPath
```

Do not expose raw internal tracebacks as ordinary user errors.

---

# 130. IPC

Clients communicate with Jarvis Core through local IPC.

Preferred:

```text
Unix domain socket
```

Use structured versioned messages.

Never use `pickle` for untrusted IPC serialization.

IPC operations and payloads must be client-neutral; Core business contracts must not contain CLI-formatted presentation data. Protocol negotiation must include version and capability negotiation so CLI, TUI, Voice and Desktop clients can share the same Core without assuming identical presentation features.

---

# 131. Streaming IPC

Protocol must support events such as:

```text
response_started
text_delta
tool_call_started
tool_progress
approval_requested
tool_call_completed
response_completed
error
```

Do not assume model responses arrive as one final block.

Events for a request must carry a monotonically ordered sequence and every accepted request must produce exactly one terminal `response_completed` or `error` event. Approval requests must expire and bind to the originating validated request and tool call.

Reconnect and replay support, when available, must be bounded and explicit. When replay is unavailable, the client must receive an authoritative status instead of guessing whether an operation completed.

---

# 132. Cancellation

Client cancellation should propagate to active model generation where supported.

Tool cancellation must be explicit and safe.

Closing a terminal must not silently interrupt partially completed destructive operations without recording the result.

Disconnect does not imply cancellation. Core retains ownership of accepted work until it reaches a recorded terminal state or processes an explicit valid cancellation request.

---

# 133. Daemon

Jarvis Core may run as:

```text
jarvisd
```

through user-level systemd.

Responsibilities:

- IPC;
- profiles;
- model runtimes;
- agent loop;
- Tool Broker;
- Policy Engine;
- memory;
- persistence;
- logging;
- runtime coordination.

It does not own CLI/TUI rendering.

There is exactly one user-level Core owner for a user's Jarvis XDG state. Multiple clients and multiple profile runtimes share that owner.

---

# 134. User Installation

Installation is scoped to the current Linux user.

Do not require root for normal installation when avoidable.

Do not place mutable user profile data into system-global directories.

---

# 135. Uninstallation

Uninstalling application binaries must be separate from deleting user data.

Default uninstall should preserve:

- profiles;
- conversations;
- memories;
- model-private notes;

unless the user explicitly chooses purge.

---

# 136. Suggested Package Structure

```text
Jarvis-CLI/
├── AGENTS.md
├── README.md
├── LICENSE
├── pyproject.toml
│
├── src/
│   └── jarvis/
│       ├── cli/
│       ├── tui/
│       ├── core/
│       ├── ipc/
│       ├── profiles/
│       ├── llm/
│       ├── tools/
│       ├── permissions/
│       ├── memory/
│       ├── storage/
│       ├── desktop/
│       ├── network/
│       ├── logging/
│       ├── config/
│       ├── updater/
│       ├── installer/
│       └── util/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── packaging/
│   ├── systemd/
│   └── desktop/
│
└── docs/
```

Do not create empty layers simply to mimic this tree.

---

# 137. Recommended Python Stack

Initial preference:

```text
Python 3.12+
asyncio
Pydantic
Textual
Rich
Typer or Click
httpx
SQLite
pytest
pytest-asyncio
```

Keep dependency count controlled.

---

# 138. Dependency Rules

Before adding a dependency check:

- whether it sends telemetry;
- whether it performs network activity;
- whether it is maintained;
- whether its license is GPL-compatible;
- whether it significantly increases installation burden;
- whether the feature can be implemented safely with the standard library.

Avoid large agent frameworks unless explicitly justified.

---

# 139. Testing Requirements

Core features require automated tests.

At minimum:

```text
profile name normalization
profile command collision handling
Jarvis profile deletion protection
profile reset
profile creation from Jarvis defaults
profile isolation
profile/model private-data isolation
model discovery
runtime locking
same GGUF across profiles
permissions
installation path protection
file size limits
storage limits
learning first-run state
learning restart/finish
visible logging modes
diagnostic log persistence
log isolation from model context
IPC serialization
timeouts
update boundary
single-Core ownership and stale socket recovery
per-profile FIFO generation serialization
model switch during active generation
profile reset/delete with active runtime
quota reservation and storage exhaustion
human-only diagnostic IPC routes
hardlink, symlink-swap and changed-target protection
executable identity replacement races
autostart duplicate activation
IPC event ordering and exactly-one terminal event
```

---

# 140. Security-Sensitive Tests

Test:

```text
model cannot access logs
model cannot alter active installation
model cannot bypass Tool Broker
model cannot grant itself permission
model cannot bypass ASK
model cannot invoke sudo silently
model cannot overwrite via CREATE permission alone
model cannot MOVE when MOVE is ASK without approval
model cannot MODIFY existing file under CREATE permission
model cannot invoke jarvis-update through conversational execution
executed process cannot access the network under EXECUTE alone
process termination requires EXECUTE and DELETE
process termination cannot trust a reused PID
executed process cannot alter the active installation
diagnostic and audit response types cannot enter the Context Builder
```

---

# 141. Test Isolation

Tests must use temporary directories and test databases.

Never manipulate:

- real home files;
- real profiles;
- real installation data;
- real user model files.

Do not require a multi-gigabyte GGUF for ordinary CI.

Provide a fake LLM provider.

---

# 142. Suggested Implementation Order

## Phase 1 — Foundation

Implement:

```text
package
GPL-3.0 license
XDG paths
configuration schemas
SQLite
migrations
logging foundation
installation path detection
quota/accounting/reservation primitives
```

---

## Phase 2 — Profile System

Implement:

```text
permanent Jarvis profile
profile creation
name normalization
rename
delete protection
reset
profile cloning
```

---

## Phase 2A — Core and Profile Clients

Implement:

```text
single user-level Core ownership
versioned client-neutral IPC
profile/configuration Core operations
Jarvis-config profile selector over IPC
logical profile aliases and alias-to-ProfileId resolution
help without model startup
```

No real client may access repositories or the database directly.

---

## Phase 3 — Model Registry

Implement:

```text
model directories
minimum jarvis-manage model/runtime settings
GGUF scanning
stable model IDs
model metadata
per-profile model association
```

---

## Phase 4 — Runtime

Implement:

```text
llama.cpp provider
runtime manager
single runtime per profile
same GGUF in multiple profiles
health checks
shutdown
timeouts
```

---

## Phase 5 — Chat

Implement:

```text
Core chat pipeline first
central Context Builder
conversation and diagnostic persistence
first-chat learning activation
per-profile FIFO generation scheduling
then simple one-shot and interactive CLI
streaming and client commands over IPC
```

---

## Phase 6 — Learning

Implement:

```text
first-run learning mode
profile/model learning state
/learning start
/learning finish
/learning status
private notes
```

---

## Phase 7 — Policy and Safe Tools

Implement:

```text
Tool Broker
Policy Engine
CREATE/COPY/READ/SCREEN/INTERNET/EXECUTE
DELETE/MODIFY/MOVE
approval flow
audit events
```

Begin with read-only/non-destructive tools.

---

## Phase 8 — Mutating Tools

Implement:

```text
create
copy
modify
move
delete
script execution
EXECUTE-owned ordinary program side effects
networked execution requires EXECUTE + INTERNET
process termination requires EXECUTE + DELETE
```

with strong tests.

---

## Phase 9 — Memory

Implement:

```text
conversation retrieval
FTS and ownership-filtered search first
semantic memory
episodic memory
private note retrieval
context budgeting
```

---

## Phase 10 — Internet

Implement:

```text
web search
web fetch
web download
network controls
download size limits
```

---

## Phase 11 — TUI

Build polished Textual client on top of the stable IPC/Core.

---

## Phase 12 — Desktop / Wayland

Implement:

```text
desktop portals
screen access
desktop context
Wayland adapters
```

---

## Phase 13 — Management

Implement:

```text
jarvis-manage
update checking
diagnostics
repair
installation health
then one-Core per-profile autostart
```

---

## Phase 14 — Distribution

Implement:

```text
installer
uninstaller
jarvis-clear
desktop entry
systemd user services
release packaging
then separate authenticated jarvis-update
```

---

# 143. Existing Previous-Version Features

The old Jarvis-CLI contained useful ideas including:

- GGUF chat through llama.cpp;
- interactive and one-shot CLI;
- reasoning levels;
- context sizing;
- profiles;
- model switching;
- personas;
- persistent context;
- learning;
- history search;
- filesystem tools;
- process inspection;
- hardware/system info;
- script execution;
- application lookup;
- fuzzy application matching;
- managed model server;
- diagnostic logs;
- notes;
- auditing;
- updater;
- installer;
- desktop launcher;
- Debian/Ubuntu support.

These are feature references only.

Do not reuse the previous architecture blindly.

---

# 144. Architectural Invariants

These rules are mandatory:

```text
THE DEFAULT PROFILE IS ALWAYS JARVIS

JARVIS PROFILE CAN NEVER BE DELETED

NEW PROFILES ARE CREATED THROUGH JARVIS-CONFIG

NEW PROFILES CLONE CONFIGURATION FROM JARVIS, NOT ITS HISTORY

WHEN PHYSICALLY EXPOSED, PROFILE COMMANDS ARE DIRECT EXECUTABLE NAMES

PROFILE COMMAND NAMES ARE NORMALIZED TO LOWERCASE ASCII WITH HYPHENS

ONE ACTIVE MODEL SERVER MAXIMUM PER PROFILE

MULTIPLE PROFILES MAY RUN SIMULTANEOUSLY

THE SAME GGUF MAY RUN IN MULTIPLE PROFILES

PROFILE STATE IS ISOLATED

MODEL PRIVATE DATA IS PROFILE + MODEL SPECIFIC

PERSONA AND CONTEXT BELONG TO THE PROFILE

DIAGNOSTIC LOGS ARE NEVER MODEL MEMORY

MODELS NEVER RECEIVE RAW DIAGNOSTIC LOG ACCESS

FULL DIAGNOSTIC CHAT LOGS ARE STORED LOCALLY

VISIBLE LOGGING DEFAULT IS ESSENTIAL-MINIMUM

CREATE, COPY, READ, SCREEN, INTERNET AND EXECUTE DEFAULT TO ALLOW

DELETE, MODIFY AND MOVE DEFAULT TO ASK

SUDO DEFAULTS TO DENY

FIRST MODEL RUN IN A PROFILE/MODEL PAIR STARTS LEARNING MODE

FIRST RUN MEANS THE FIRST USER-FACING AGENT ENGINE CHAT TRANSACTION

RUNTIME STARTUP, HEALTH CHECKS AND AUTOSTART DO NOT CONSUME FIRST-RUN STATE

LEARNING MODE IS EXPLICITLY VISIBLE TO THE USER

THE ACTIVE JARVIS INSTALLATION IS PROTECTED FROM MODEL MODIFICATION

ONLY JARVIS-UPDATE MAY UPDATE THE INSTALLED APPLICATION

A SEPARATE DEVELOPMENT CLONE MAY BE EDITED NORMALLY

UPDATE CHECKING DEFAULTS TO ENABLED

INSTALLATION IS USER-LOCAL

CONFIGURATION IS PROFILE-FIRST

INSTALLATION-ONLY SETTINGS BELONG TO JARVIS-MANAGE

JARVIS-CONFIG ALWAYS STARTS BY SELECTING A PROFILE

ALL CONFIGURATION SECTIONS SUPPORT RESET TO DEFAULT

NORMAL USERS SEE COMMON SETTINGS FIRST

ADVANCED SETTINGS LIVE UNDER AN ADVANCED SECTION

CLI AND TUI ARE CLIENTS OF JARVIS CORE

FUTURE VOICE AND DESKTOP APP REUSE THE SAME CORE

THE LLM NEVER DIRECTLY EXECUTES HOST OPERATIONS

ALL OS CAPABILITIES GO THROUGH THE TOOL BROKER

EXECUTE OWNS ORDINARY SIDE EFFECTS OF THE EXPLICITLY SELECTED PROGRAM

EXECUTED PROGRAM NETWORK ACCESS REQUIRES EXECUTE AND INTERNET

PROCESS INSPECTION REQUIRES READ

PROCESS TERMINATION REQUIRES EXECUTE AND DELETE

PERMISSIONS ARE ENFORCED BY THE POLICY ENGINE

THE POLICY ENGINE AUTHORIZES CAPABILITIES, NOT MODEL CONTENT

MODEL OUTPUT FREEDOM DOES NOT GRANT HOST EXECUTION AUTHORITY

JARVIS DOES NOT SECRETLY IMPOSE PROVIDER-SPECIFIC CONTENT POLICY ON LOCAL MODELS

JARVIS-OWNED SYSTEM AND PERSISTENT PROMPT COMPONENTS HAVE IDENTIFIABLE PROVENANCE

MODEL FILES ARE USER OWNED

NO TELEMETRY

NO CLOUD AI REQUIREMENT

PROJECT INTERNAL LANGUAGE IS ENGLISH

LICENSE IS GPL-3.0
```

---

# 145. Coding-Agent Rules

When modifying Jarvis-CLI:

1. Read this file first.
2. Inspect current code before making architectural changes.
3. Preserve profile isolation.
4. Preserve profile/model private-data isolation.
5. Preserve the permanent Jarvis profile.
6. Preserve installation self-protection.
7. Do not give the LLM direct host access.
8. Do not expose diagnostic logs to model context.
9. Do not introduce telemetry.
10. Do not introduce required cloud AI services.
11. Do not bypass permission checks.
12. Do not use shell execution when a structured tool exists.
13. Do not silently widen network access.
14. Do not silently change user permission defaults.
15. Do not make system-wide installation the default.
16. Do not silently delete persistent data.
17. Do not hardcode user-facing strings into business logic.
18. Keep configuration defaults centralized.
19. Use typed interfaces at subsystem boundaries.
20. Add tests for security-sensitive behavior.
21. Do not make implementation-specific llama.cpp assumptions leak through the entire codebase.
22. Keep CLI/TUI presentation separate from the Core.
23. Avoid unnecessary dependencies.
24. Keep developer code and documentation in English.
25. Explain intentional deviations from this document before implementing them.
26. Do not add hidden provider-specific content rules or semantic moderation to local-model prompt
    or response paths.
27. Keep capability authorization and architectural integrity constraints separate from judgments
    about model-generated subject matter.
28. Preserve identifiable provenance for Jarvis-owned system and persistent prompt components.

---

# 146. Guiding Principle

Jarvis should feel powerful because it has well-designed capabilities.

It must not feel powerful merely because an LLM received unrestricted system access.

Always prefer:

```text
Typed Capability
       +
Validated Arguments
       +
Central Permission
       +
Bounded Execution
       +
Structured Result
       +
Audit Record
```

over:

```text
LLM-generated arbitrary command
        +
unrestricted execution
```

The long-term goal is a local AI assistant that can operate the user's computer with substantial autonomy while remaining:

- understandable;
- inspectable;
- private;
- reversible where possible;
- configurable;
- debuggable;
- secure;
- under the user's control.
