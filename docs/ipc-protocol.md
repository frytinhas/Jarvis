# Jarvis local IPC protocol version 1

Milestone 002 introduces a client-neutral local protocol between thin clients and the single
user-level Jarvis Core. It uses only a mode-`0600` Unix-domain socket under the validated
mode-`0700` XDG runtime directory. Linux `SO_PEERCRED` UID equality is mandatory. There is no TCP,
HTTP, control-token file, outbound networking, telemetry, or durable request history.

## Framing and bounds

Each message is a four-byte unsigned big-endian length followed by one strict UTF-8 JSON object.
The encoded payload limit is 1,048,576 bytes; zero, truncated, or oversized frames fail safely.
The standard-library JSON parser rejects duplicate keys, floats, nonstandard constants, and
integers outside signed 64-bit range. Iterative validation then enforces depth 32, 4,096 total
nodes, 256 entries per container, 128 UTF-8 bytes per key, and 65,536 UTF-8 bytes per string.

Header/body/handshake and outbound drain deadlines are five seconds. Established connections have
a 300-second idle deadline. The server admits at most 32 physical transports, 16 in-flight
requests per logical session, 128 globally, 64 queued outbound frames and 2 MiB queued bytes per
transport.
At most 128 resumable logical sessions (attached or retained after disconnect) exist at once.

## Negotiation

The first frame is `hello` with supported protocol versions, required and optional capabilities,
a bounded client name, and either `null` or a resume proof. The current protocol version is `1`.
The current capability vocabulary is:

```text
request-stream-v1
request-cancel-v1
core-health-v1
profile-catalog-v1
profile-management-v1
model-registry-v1
runtime-manager-v1
chat-v1
session-resume-v1
event-replay-v1
core-control-v1
```

`core-control-v1` is an explicit semantic opt-in, not another security principal. Same-UID peer
credentials remain the lifecycle-control boundary.

## Requests and events

A request contains `protocol_version`, a canonical UUID4 `request_id`, an operation, optional
canonical `profile_id`, and an object payload. Unknown fields and operations fail before
acceptance. A retained RequestId collision never replaces, exposes, cancels, or aliases existing
state.

Accepted requests emit per-request sequences starting at one:

```text
request.accepted
request.started        # absent when cancelled before start
request.completed | request.cancelled | error
```

The terminal event is sequenced. State-lock arbitration selects exactly one terminal and prohibits
later events. Cancellation, status, and replay require ownership by the same resumable logical
session. Disconnect never means cancellation.

Production M002 operations are only:

- `core.health`, with payload `{}` and no `profile_id`;
- `profiles.list`, with payload `{}` and no `profile_id`;
- `profiles.get`, with payload `{}` and a stable M001 `ProfileId`;
- `core.shutdown`, with payload `{}`, no `profile_id`, same-UID peer credentials, and negotiated
  `core-control-v1`.

M003 adds the optional `profile-management-v1` capability without changing protocol version 1.
When negotiated, it authorizes Core-owned `profiles.resolve_alias`, create/rename, configuration
section reads and updates, and reset/delete preview/confirmation operations. Alias resolution
accepts only an already canonical M001 alias and returns the normal five-field catalog entry; it
never creates a launcher or examines PATH. Profile-management mutations retain M001 validation,
optimistic revisions, and state-bound destructive confirmation intents. The startup configuration
section remains stored and resettable but is not exposed by the M003 client API.

Profile catalog entries contain exactly `profile_id`, `kind`, `display_name`, `command_alias`, and
`identity_revision`. They contain no profile configuration, persona/context, permissions,
messages, private data, timestamps, repository details, or database paths.

M004 adds optional `model-registry-v1` without changing protocol version 1. It owns
`installation.runtime.get/update`, `models.refresh/list/get`, `profiles.models.list/select`, and
`profiles.models.config.get/update`. These operations require only `model-registry-v1` (plus the
base request stream), not `profile-management-v1`. Installation/model catalog operations forbid a
profile ID; profile-model operations require a stable profile ID. Syntactically malformed payloads
fail before acceptance, while model availability and optimistic-revision domain failures use the
normal accepted/started/single-error lifecycle.

Protocol v1 excludes JSON floating-point scalars. Under the negotiated M004 capability, the four
sampling decimals (`temperature`, `top_p`, `min_p`, and `repeat_penalty`) therefore use bounded
decimal strings at the IPC boundary. Core converts and validates them as finite domain numbers;
storage and service contracts remain numeric. Completion envelopes are validated before terminal
arbitration, so an invalid handler result becomes one deliverable terminal error rather than an
undeliverable recorded completion.

`models.refresh` returns the authoritative registry records plus `partial_reason`. A null reason
means reconciliation may mark unseen records missing. A bounded or interrupted scan reports a
sanitized reason class and preserves previously known records that the partial scan did not visit.

M005 adds optional `runtime-manager-v1`, retaining protocol version 1. Runtime management also
requires the base request stream and `model-registry-v1`. Profile operations
`profiles.runtime.start/status/stop/switch` require a stable profile ID; switch carries a target
`model_id` and expected profile-model revision. Installation operations
`installation.runtime.policy.get/update` forbid a profile ID and expose a revision-checked capacity
from 1 through 16 (default 2). Runtime lifecycle requests may emit pre-encoded
`runtime.state_changed` events before their one terminal event. Safe snapshots contain only runtime
and model IDs, state/health classes, and timestamps—never PID, port, path, argv, configuration,
server output, or authentication material. Disconnect does not cancel accepted runtime work;
explicit cancellation invokes cleanup.

For shutdown, Core stores and drains the terminal `request.completed` event before entering
`STOPPING` or server-driven closure of a healthy requester.

M006A adds optional `chat-v1` while retaining protocol version 1. Profile-scoped operations are
`chat.submit`, `chat.session.resolve`, `chat.turn.status`, `chat.turn.attach`,
`chat.learning.status/start/finish`, and the human-only `chat.diagnostics.summary`. Chat submission
emits `response_started`, zero or more `text_delta` events, and exactly one terminal
`response_completed` or `error`. Submission accepts bounded `content`, an optional canonical
session UUID, and optional `new_session`; the physical connection owns neither the durable session
nor accepted generation. Status/attach returns the authoritative bounded durable turn snapshot.
Reconnect uses the existing same-owner resume/replay contracts. Diagnostic summaries use a
dedicated bounded result type and are never Context Builder contributions.

Chat auto-starts the selected runtime through RuntimeManager. One generation is active per profile,
at most 16 are queued FIFO excluding active, and different profiles may generate concurrently.
Explicit cancellation owns queued/active cancellation; disconnect does not cancel. Model switch
drains the old generation, while whole-profile reset/delete and Core shutdown cancel and durably
record active work before cleanup.

## Resume and replay

Handshake returns a random 256-bit resume token bound to one logical `connection_id`. Tokens are
memory-only, never logged or persisted, compared in constant time, and rotated after every
successful resume. Only one physical transport may attach at a time. Resume proves logical-session
ownership; it does not create an OS authorization principal.

Replay is same-Core and memory-only. Each request retains at most 64 events/256 KiB, each logical
session 256 events/2 MiB, and Core 16 MiB globally. Eviction is deterministic. Sequence numbers do
not change or restart when earlier events are dropped. A missing required gap returns
`ipc.replay_unavailable` with authoritative state, terminal status, and retained sequence range.
Resume never survives a new `CoreInstanceId`.

## Runtime ownership

Core artifacts are `core.lock`, `core.sock`, and informational `core-runtime.json`. The exclusive
nonblocking `flock` held on a verified `core.lock` descriptor for the complete Core lifetime is the
single-instance authority. Metadata, PID, process start ticks, executable identity, and boot ID are
diagnostic corroboration only. A lock loser never cleans artifacts. A lock winner can remove only
validated stale artifacts through directory-relative identity rechecks. No recovery path signals
or kills a PID recovered from Core metadata. M005 model-runtime recovery is a separate stricter
contract: it signals an orphan process group only after boot ID, PID start ticks, executable
device/inode, process group, model descriptor identity, owned IPv4-loopback listener,
runtime/profile identity, and private artifact validation all match. Ambiguous evidence is retained
and never signalled.

Protocol version 1 itself has no database ownership. The current M006A product schema is version 5
with packaged migrations `0001_migration_ledger.sql`, `0002_profile_system.sql`,
`0003_model_registry.sql`, `0004_runtime_manager.sql`, and `0005_chat_pipeline.sql`.
