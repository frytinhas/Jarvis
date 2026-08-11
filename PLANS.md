# Jarvis-CLI ExecPlan Standard

## Purpose

Every milestone in `ROADMAP.md` requires one active ExecPlan before implementation begins. An ExecPlan is the durable handoff and execution record for that milestone, not a speculative design document created in bulk.

Do not create all milestone ExecPlans in advance. Create only the plan for the next authorized milestone (or a specifically authorized active milestone), immediately before its implementation work starts. Creating an ExecPlan does not itself authorize implementation.

`AGENTS.md` is the product and architecture authority. `ROADMAP.md` defines milestone order and boundaries. This file defines the planning discipline. An ExecPlan may refine implementation details but may not weaken or reinterpret either document. A genuine conflict or unresolved product choice must be surfaced to the user before dependent implementation.

## Location and naming

ExecPlans live under `docs/plans/` and use a zero-padded stable milestone identifier plus a short stable slug. An unsplit milestone uses its three-digit number. A roadmap milestone deliberately split before implementation uses that number plus a lowercase letter:

```text
docs/plans/000-foundation.md
docs/plans/001-profile-system.md
docs/plans/006a-chat-core.md
docs/plans/006b-simple-cli-chat.md
```

Use the exact stable identifier from `ROADMAP.md`, lowercased in the filename (`006A` becomes `006a`). Each submilestone has its own independent ExecPlan and completion evidence; never combine `006A` and `006B` into one plan merely because they share a number. Do not renumber completed milestones. If the roadmap is intentionally revised, record how existing plans map to the revision.

## Self-contained continuation rule

An ExecPlan must be self-contained enough that a fresh Codex session with no prior conversation history can continue safely using only:

- `AGENTS.md`;
- `ROADMAP.md`;
- `PLANS.md`;
- the active ExecPlan;
- the current repository state.

It must not depend on remembered chat discussion, an unavailable external note, or unexplained shorthand. Include exact repository-relative paths, commands, invariants, expected outcomes, and the reasoning behind non-obvious choices. Reference relevant `AGENTS.md` sections rather than copying the whole specification.

## Required status model

Every discrete plan item must be marked exactly one of:

- **DONE** — implemented and verified, with evidence recorded;
- **IN PROGRESS** — currently being implemented or verified;
- **NOT STARTED** — no implementation work has begun.

Normally only one sequence item should be **IN PROGRESS**. “DONE” means its stated tests or evidence succeeded; code existing is not enough. If work must be revisited, change its status and explain why. Never use approximate percentages as a substitute for these states.

The plan must include a prominent current-status summary and a timestamped progress log. Use absolute dates and include the timezone when timing matters.

## Required ExecPlan contents

Every ExecPlan must contain all of the following sections.

### 1. Purpose and user outcome

State the milestone objective, why it exists now, and what a user or maintainer can observe when it is complete. Define unfamiliar milestone-specific terminology.

### 2. Scope

List exact included behavior and deliverables. Tie them to the milestone in `ROADMAP.md` and relevant invariants in `AGENTS.md`.

### 3. Non-goals

List deferred capabilities and forbidden shortcuts. Explicitly preserve later milestone boundaries, particularly where an attractive shortcut would bypass Core, profile isolation, the Policy Engine, the Tool Broker, logging separation, or installation protection.

### 4. Current progress

Provide:

- a summary of what is **DONE**, **IN PROGRESS**, and **NOT STARTED**;
- a checkbox or table of discrete work items using those exact labels;
- a timestamped progress log describing meaningful edits, tests, blockers, and handoff state.

Update this section continuously while work proceeds, not only at the end.

### 5. Repository state and prerequisites

Describe the relevant current tree, prior milestone contracts being consumed, required local tools, feature flags, fixtures, and assumptions verified from the repository. Note existing user changes that must be preserved. Do not assume a clean worktree.

### 6. Implementation sequence

Provide small ordered steps, each independently checkable. For every step state:

- status;
- exact change and repository-relative locations;
- prerequisite steps;
- validation command or observable result;
- safe rollback/recovery considerations where mutation or migrations are involved.

Security controls must precede the capability that consumes them. Database migrations must precede code that assumes the new schema. Tests should be added alongside the behavior they constrain.

### 7. Exact files and components affected

List files expected to be created, modified, or deliberately left untouched, plus the owning subsystem. Update the list when discoveries change it. Avoid placeholder layers and premature files.

### 8. Contracts and interfaces

Specify typed boundaries, inputs, outputs, errors, ownership, lifecycle, versioning, event ordering, concurrency, cancellation, and compatibility behavior introduced or changed. Include enough detail for tests and later consumers. State which subsystem is authoritative for each contract.

### 9. Database, migrations, and storage

Document schema changes, keys and isolation constraints, migration numbering/order, transaction behavior, backfill/default behavior, downgrade/recovery strategy, XDG location, retention/limit effects, and test fixtures. Explicitly address `profile_id` and `model_id` ownership wherever relevant.

If there is no database or storage change, say so and explain why.

### 10. Security and privacy considerations

Threat-model the milestone in proportion to its risk. At minimum consider:

- profile and profile/model isolation;
- model authority versus Core authority;
- policy/broker enforcement where applicable;
- active-installation protection;
- canonical paths, links, races, and bounds where applicable;
- approval and destructive-action semantics;
- secret redaction and diagnostic/model-context separation;
- network scope and outbound data;
- user-local privileges and sudo denial;
- telemetry/dependency behavior.

Record abuse cases and the tests or design controls that address them. Do not defer a required security foundation to a later milestone that already depends on it.

### 11. Tests

List exact unit, integration, contract, migration, security, and end-to-end tests. Include commands, fixtures/fakes, expected results, and relevant failure paths. Tests must use temporary directories, temporary XDG roots, test databases, fake LLM providers, small GGUF fixtures, controlled local network services, or disposable systems as appropriate. They must never alter real profiles, homes, model files, installations, or user services.

### 12. Manual verification

Give a reproducible, numbered procedure starting from stated prerequisites. Include expected output/behavior and cleanup. Manual verification supplements automated tests; it does not replace them.

### 13. Discoveries

Continuously record unexpected repository facts, dependency behavior, platform limitations, test findings, and specification implications. Include evidence such as a concise command result or file reference. A discovery that invalidates the sequence must update the plan before work continues.

### 14. Architectural decisions

Record each non-trivial decision with:

- date;
- decision and status (proposed, accepted, superseded);
- context and alternatives;
- rationale under the `AGENTS.md` priority order;
- consequences and later milestones affected;
- user approval when the choice is a product decision.

Prefer the smallest decision necessary for the active milestone. Do not decide future implementation details prematurely.

### 15. Deviations from the original plan

Record any change from the initial ExecPlan or roadmap scope, why it occurred, who authorized a product/scope change, files/tests affected, and whether `ROADMAP.md` or architecture documentation also changed. Never hide scope drift by editing old text without a record.

### 16. Unresolved issues

List open questions, blockers, owners, impact, safest current behavior, and the exact condition for resolution. Distinguish implementation discoveries from genuine product decisions. If an issue blocks correct work, stop the dependent step rather than inventing behavior.

### 17. Completion criteria and evidence

Restate the roadmap definition of done as verifiable checks. For each check link or point to test commands, output summaries, manual verification results, and relevant files. Include repository status and documentation updates. The milestone is complete only when every required check is **DONE** and no unresolved issue blocks its objective.

### 18. Handoff summary

At every pause and at completion, state the exact next action, current failing tests (if any), important local state, pending approvals, and hazards. A fresh session should be able to resume without reconstructing intent from Git history.

## Required working practice

Before implementing a milestone, the agent must:

1. read `AGENTS.md` in full;
2. inspect `ROADMAP.md`, `PLANS.md`, the active ExecPlan, and repository state;
3. verify every exact milestone or submilestone dependency named by `ROADMAP.md` and the predecessor definitions of done on which the active work relies;
4. create or update only the active milestone’s ExecPlan;
5. resolve or explicitly block on conflicts before changing implementation files.

During implementation, the agent must:

1. update the active ExecPlan whenever a step starts, finishes, changes, or becomes blocked;
2. record discoveries and decisions when they occur;
3. keep exact affected-file and test lists current;
4. run focused tests after each meaningful step and record evidence;
5. preserve unrelated user changes;
6. update architecture/user/developer documentation in the same milestone when contracts change;
7. stop if required authority or a genuine product decision is missing.

At milestone completion, the agent must:

1. run the complete milestone verification set and relevant regression tests;
2. perform and record manual verification;
3. reconcile the implementation against `AGENTS.md` and the roadmap scope;
4. mark all completion criteria **DONE** with evidence;
5. document remaining non-blocking follow-up in the appropriate future roadmap milestone rather than silently carrying it;
6. leave a final handoff summary and coherent repository state.

## Scope and amendment rules

- One ExecPlan covers exactly one roadmap milestone or explicitly identified submilestone. If a milestone proves too large, revise `ROADMAP.md` deliberately before splitting it; assign stable lettered identifiers and do not create hidden subprojects inside one ExecPlan.
- Do not pull work from a later milestone merely because it is convenient. Add only the minimum compatibility contract required now, and record the later implementation as out of scope.
- A security fix required to keep the active milestone safe is not optional scope. Document it and update affected plans/roadmap if its impact crosses milestones.
- Changes to an authoritative product rule require user direction and then a corresponding `AGENTS.md` update. An ExecPlan cannot authorize such a change.
- Completed ExecPlans remain historical records. Correct factual mistakes transparently and append decisions/deviations; do not rewrite history to make execution look linear.

## Minimal template

Use this as a structural starting point, expanding it to be genuinely self-contained:

```markdown
# Milestone NNN or NNNA — Name ExecPlan

Status: NOT STARTED
Last updated: YYYY-MM-DD TZ

## Purpose and user outcome
## Scope
## Non-goals
## Current progress
## Repository state and prerequisites
## Implementation sequence
## Exact files and components affected
## Contracts and interfaces
## Database, migrations, and storage
## Security and privacy considerations
## Tests
## Manual verification
## Discoveries
## Architectural decisions
## Deviations from the original plan
## Unresolved issues
## Completion criteria and evidence
## Handoff summary
```

The headings are mandatory, but the content—not the template—is what makes an ExecPlan usable.
