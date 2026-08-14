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

Profile catalog entries contain exactly `profile_id`, `kind`, `display_name`, `command_alias`, and
`identity_revision`. They contain no profile configuration, persona/context, permissions,
messages, private data, timestamps, repository details, or database paths.

For shutdown, Core stores and drains the terminal `request.completed` event before entering
`STOPPING` or server-driven closure of a healthy requester.

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

Runtime artifacts are `core.lock`, `core.sock`, and informational `core-runtime.json`. The exclusive
nonblocking `flock` held on a verified `core.lock` descriptor for the complete Core lifetime is the
single-instance authority. Metadata, PID, process start ticks, executable identity, and boot ID are
diagnostic corroboration only. A lock loser never cleans artifacts. A lock winner can remove only
validated stale artifacts through directory-relative identity rechecks. No recovery path signals
or kills a PID recovered from metadata.

No database migration accompanies protocol version 1. Schema remains version 2 with only packaged
migrations 0001 and 0002.
