CREATE TABLE profiles (
    profile_id TEXT PRIMARY KEY
        CHECK (
            length(profile_id) = 36
            AND profile_id NOT GLOB '*[^0-9a-f-]*'
            AND substr(profile_id, 9, 1) = '-'
            AND substr(profile_id, 14, 1) = '-'
            AND substr(profile_id, 19, 1) = '-'
            AND substr(profile_id, 24, 1) = '-'
        ),
    profile_kind TEXT NOT NULL CHECK (profile_kind IN ('jarvis', 'standard')),
    display_name TEXT NOT NULL
        CHECK (
            length(display_name) BETWEEN 1 AND 128
            AND length(CAST(display_name AS BLOB)) <= 512
            AND instr(display_name, char(0)) = 0
        ),
    identity_revision INTEGER NOT NULL CHECK (identity_revision > 0),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE UNIQUE INDEX one_jarvis_profile
    ON profiles(profile_kind)
    WHERE profile_kind = 'jarvis';

CREATE TRIGGER protect_jarvis_profile_delete
BEFORE DELETE ON profiles
WHEN OLD.profile_kind = 'jarvis'
BEGIN
    SELECT RAISE(ABORT, 'protected jarvis profile');
END;

CREATE TRIGGER protect_jarvis_profile_kind
BEFORE UPDATE OF profile_kind ON profiles
WHEN OLD.profile_kind = 'jarvis' OR NEW.profile_kind = 'jarvis'
BEGIN
    SELECT RAISE(ABORT, 'protected jarvis profile kind');
END;

CREATE TABLE profile_aliases (
    profile_id TEXT PRIMARY KEY REFERENCES profiles(profile_id) ON DELETE CASCADE,
    command_alias TEXT NOT NULL UNIQUE
        CHECK (
            length(command_alias) BETWEEN 1 AND 63
            AND command_alias NOT GLOB '*[^a-z0-9-]*'
            AND command_alias NOT LIKE '-%'
            AND command_alias NOT LIKE '%-'
            AND instr(command_alias, '--') = 0
        ),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TRIGGER enforce_jarvis_alias_insert
BEFORE INSERT ON profile_aliases
WHEN
    (SELECT profile_kind FROM profiles WHERE profile_id = NEW.profile_id) = 'jarvis'
        AND NEW.command_alias <> 'jarvis'
    OR (SELECT profile_kind FROM profiles WHERE profile_id = NEW.profile_id) = 'standard'
        AND NEW.command_alias = 'jarvis'
BEGIN
    SELECT RAISE(ABORT, 'invalid jarvis alias');
END;

CREATE TRIGGER enforce_jarvis_alias_update
BEFORE UPDATE OF profile_id, command_alias ON profile_aliases
WHEN
    (SELECT profile_kind FROM profiles WHERE profile_id = OLD.profile_id) = 'jarvis'
    OR (SELECT profile_kind FROM profiles WHERE profile_id = NEW.profile_id) = 'jarvis'
        AND NEW.command_alias <> 'jarvis'
    OR (SELECT profile_kind FROM profiles WHERE profile_id = NEW.profile_id) = 'standard'
        AND NEW.command_alias = 'jarvis'
BEGIN
    SELECT RAISE(ABORT, 'protected jarvis alias');
END;

CREATE TRIGGER protect_jarvis_alias_delete
BEFORE DELETE ON profile_aliases
WHEN (SELECT profile_kind FROM profiles WHERE profile_id = OLD.profile_id) = 'jarvis'
BEGIN
    SELECT RAISE(ABORT, 'protected jarvis alias');
END;

CREATE TABLE profile_configurations (
    profile_id TEXT PRIMARY KEY REFERENCES profiles(profile_id) ON DELETE CASCADE,
    config_schema_version INTEGER NOT NULL CHECK (config_schema_version > 0),
    configuration_revision INTEGER NOT NULL CHECK (configuration_revision > 0),
    persona_text TEXT NOT NULL
        CHECK (length(CAST(persona_text AS BLOB)) <= 32768 AND instr(persona_text, char(0)) = 0),
    profile_context_text TEXT NOT NULL
        CHECK (
            length(CAST(profile_context_text AS BLOB)) <= 65536
            AND instr(profile_context_text, char(0)) = 0
        ),
    accent_color TEXT NOT NULL
        CHECK (accent_color GLOB '#[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    foreground_color TEXT NOT NULL
        CHECK (foreground_color GLOB '#[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    background_color TEXT NOT NULL
        CHECK (background_color GLOB '#[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    visible_logging_mode TEXT NOT NULL
        CHECK (
            visible_logging_mode IN
                ('full', 'server-essential', 'essential', 'essential-minimum', 'none')
        ),
    start_with_computer INTEGER NOT NULL CHECK (start_with_computer IN (0, 1)),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE profile_configuration_sections (
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    section_name TEXT NOT NULL
        CHECK (
            section_name IN (
                'persona',
                'profile-context',
                'appearance',
                'waiting-messages',
                'goodbye-messages',
                'visible-logging',
                'startup',
                'permissions'
            )
        ),
    defaults_version INTEGER NOT NULL CHECK (defaults_version > 0),
    section_revision INTEGER NOT NULL CHECK (section_revision > 0),
    PRIMARY KEY (profile_id, section_name)
);

CREATE TABLE profile_messages (
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    message_kind TEXT NOT NULL CHECK (message_kind IN ('waiting', 'goodbye')),
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0 AND ordinal < 16),
    message_text TEXT NOT NULL
        CHECK (
            length(message_text) BETWEEN 1 AND 256
            AND length(CAST(message_text AS BLOB)) <= 1024
            AND instr(message_text, char(0)) = 0
            AND instr(message_text, char(10)) = 0
            AND instr(message_text, char(13)) = 0
        ),
    PRIMARY KEY (profile_id, message_kind, ordinal)
);

CREATE TABLE profile_permissions (
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    capability TEXT NOT NULL
        CHECK (
            capability IN
                ('create', 'copy', 'read', 'screen', 'internet', 'execute', 'delete', 'modify', 'move')
        ),
    decision TEXT NOT NULL CHECK (decision IN ('allow', 'ask', 'deny')),
    PRIMARY KEY (profile_id, capability)
);

CREATE TABLE profile_operation_intents (
    operation_id TEXT PRIMARY KEY
        CHECK (
            length(operation_id) = 36
            AND operation_id NOT GLOB '*[^0-9a-f-]*'
            AND substr(operation_id, 9, 1) = '-'
            AND substr(operation_id, 14, 1) = '-'
            AND substr(operation_id, 19, 1) = '-'
            AND substr(operation_id, 24, 1) = '-'
        ),
    profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
    operation_kind TEXT NOT NULL CHECK (operation_kind IN ('delete-profile', 'reset-configuration')),
    scope TEXT NOT NULL
        CHECK (
            (operation_kind = 'delete-profile' AND scope = 'whole-profile')
            OR
            (
                operation_kind = 'reset-configuration'
                AND scope IN (
                    'persona',
                    'profile-context',
                    'appearance',
                    'waiting-messages',
                    'goodbye-messages',
                    'visible-logging',
                    'startup',
                    'permissions',
                    'whole-profile'
                )
            )
        ),
    expected_identity_revision INTEGER NOT NULL CHECK (expected_identity_revision > 0),
    expected_configuration_revision INTEGER NOT NULL CHECK (expected_configuration_revision > 0),
    state_digest_sha256 TEXT NOT NULL
        CHECK (length(state_digest_sha256) = 64 AND state_digest_sha256 NOT GLOB '*[^0-9a-f]*'),
    token_digest_sha256 TEXT NOT NULL
        CHECK (length(token_digest_sha256) = 64 AND token_digest_sha256 NOT GLOB '*[^0-9a-f]*'),
    created_at_utc TEXT NOT NULL,
    expires_at_utc TEXT NOT NULL,
    UNIQUE (profile_id, operation_kind, scope)
);

CREATE INDEX profile_operation_intents_expiry
    ON profile_operation_intents(expires_at_utc, operation_id);
