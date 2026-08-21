CREATE TABLE installation_runtime_config (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    model_directories_json TEXT NOT NULL,
    llama_server_path TEXT,
    revision INTEGER NOT NULL CHECK (revision > 0),
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE models (
    model_id TEXT PRIMARY KEY,
    fingerprint_sha256 TEXT NOT NULL UNIQUE,
    device INTEGER NOT NULL,
    inode INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    mtime_ns INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    availability TEXT NOT NULL CHECK (availability IN ('available','missing','unreadable','invalid')),
    availability_reason TEXT,
    last_scanned_at_utc TEXT NOT NULL
);
CREATE TABLE model_paths (
    model_id TEXT PRIMARY KEY REFERENCES models(model_id),
    canonical_path TEXT NOT NULL
);
CREATE INDEX model_paths_by_canonical_path ON model_paths(canonical_path);
CREATE TABLE profile_models (
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    model_id TEXT NOT NULL REFERENCES models(model_id),
    profile_model_revision INTEGER NOT NULL CHECK (profile_model_revision > 0),
    selected INTEGER NOT NULL CHECK (selected IN (0,1)),
    last_valid INTEGER NOT NULL CHECK (last_valid IN (0,1)),
    runtime_config_json TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    PRIMARY KEY (profile_id, model_id)
);
CREATE UNIQUE INDEX profile_models_one_selected ON profile_models(profile_id) WHERE selected = 1;
CREATE UNIQUE INDEX profile_models_one_last_valid ON profile_models(profile_id) WHERE last_valid = 1;
