CREATE TABLE runtime_events (
    event_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    model_id TEXT NOT NULL REFERENCES models(model_id),
    runtime_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('STARTING','READY','BUSY','ERROR','STOPPING','STOPPED')),
    event_kind TEXT NOT NULL CHECK (event_kind IN (
        'start_requested','ready','busy','health_checked','stop_requested','stopped',
        'error','recovered','switch_requested','quiesced'
    )),
    reason_class TEXT,
    occurred_at_utc TEXT NOT NULL
);
CREATE INDEX runtime_events_by_profile_time
    ON runtime_events(profile_id, occurred_at_utc, event_id);

CREATE TABLE profile_runtime_last_valid (
    profile_id TEXT PRIMARY KEY REFERENCES profiles(profile_id) ON DELETE CASCADE,
    model_id TEXT NOT NULL REFERENCES models(model_id),
    profile_model_revision INTEGER NOT NULL CHECK (profile_model_revision > 0),
    runtime_id TEXT NOT NULL,
    ready_at_utc TEXT NOT NULL
);

CREATE TABLE installation_runtime_policy (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    max_concurrent_runtimes INTEGER NOT NULL CHECK (max_concurrent_runtimes BETWEEN 1 AND 16),
    revision INTEGER NOT NULL CHECK (revision > 0),
    updated_at_utc TEXT NOT NULL
);
