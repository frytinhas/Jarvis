CREATE TABLE chat_sessions (
    session_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    model_id TEXT NOT NULL REFERENCES models(model_id),
    state TEXT NOT NULL CHECK (state IN ('open','closed')),
    next_message_ordinal INTEGER NOT NULL DEFAULT 0 CHECK (next_message_ordinal >= 0),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    UNIQUE (profile_id, model_id, session_id)
);
CREATE INDEX chat_sessions_resume
    ON chat_sessions(profile_id, model_id, state, updated_at_utc DESC, session_id DESC);

CREATE TABLE chat_turns (
    turn_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN ('queued','generating','completed','failed','cancelled')
    ),
    failure_code TEXT,
    partial_text TEXT NOT NULL DEFAULT '',
    partial_truncated INTEGER NOT NULL DEFAULT 0 CHECK (partial_truncated IN (0,1)),
    created_at_utc TEXT NOT NULL,
    started_at_utc TEXT,
    completed_at_utc TEXT,
    FOREIGN KEY (profile_id, model_id, session_id)
        REFERENCES chat_sessions(profile_id, model_id, session_id) ON DELETE CASCADE,
    CHECK (
        (state IN ('queued','generating') AND completed_at_utc IS NULL)
        OR (state IN ('completed','failed','cancelled') AND completed_at_utc IS NOT NULL)
    )
);
CREATE INDEX chat_turns_session_time
    ON chat_turns(profile_id, model_id, session_id, created_at_utc, turn_id);
CREATE INDEX chat_turns_active ON chat_turns(profile_id, state)
    WHERE state IN ('queued','generating');

CREATE TABLE chat_messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    turn_id TEXT NOT NULL REFERENCES chat_turns(turn_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    role TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content TEXT NOT NULL,
    content_bytes INTEGER NOT NULL CHECK (content_bytes >= 0),
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (profile_id, model_id, session_id)
        REFERENCES chat_sessions(profile_id, model_id, session_id) ON DELETE CASCADE,
    UNIQUE (session_id, ordinal)
);
CREATE INDEX chat_messages_context
    ON chat_messages(profile_id, model_id, session_id, ordinal);

CREATE TABLE learning_state (
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    model_id TEXT NOT NULL REFERENCES models(model_id),
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','FINISHED')),
    started_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    finished_at_utc TEXT,
    revision INTEGER NOT NULL CHECK (revision > 0),
    PRIMARY KEY (profile_id, model_id),
    CHECK (
        (status = 'ACTIVE' AND finished_at_utc IS NULL)
        OR (status = 'FINISHED' AND finished_at_utc IS NOT NULL)
    )
);

CREATE TABLE chat_diagnostics (
    diagnostic_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    model_id TEXT NOT NULL REFERENCES models(model_id),
    session_id TEXT NOT NULL,
    request_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('info','warning','error')),
    summary TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    closed INTEGER NOT NULL CHECK (closed IN (0,1)),
    reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved IN (0,1)),
    occurred_at_utc TEXT NOT NULL,
    closed_at_utc TEXT,
    FOREIGN KEY (profile_id, model_id, session_id)
        REFERENCES chat_sessions(profile_id, model_id, session_id) ON DELETE CASCADE,
    FOREIGN KEY (turn_id) REFERENCES chat_turns(turn_id) ON DELETE CASCADE
);
CREATE INDEX chat_diagnostics_rotation
    ON chat_diagnostics(profile_id, model_id, closed, reserved, closed_at_utc, diagnostic_id);
CREATE INDEX chat_diagnostics_turn
    ON chat_diagnostics(profile_id, model_id, session_id, turn_id, occurred_at_utc);
