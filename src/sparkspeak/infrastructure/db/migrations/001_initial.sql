PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS decks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    target_cefr     TEXT NOT NULL DEFAULT 'B2',
    persona_prompt  TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS cards (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id             INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    front_prompt        TEXT NOT NULL,
    normalized_front    TEXT NOT NULL,
    back_reference      TEXT NOT NULL,
    context_example     TEXT,
    card_type           TEXT NOT NULL CHECK (card_type IN (
                            'vocab', 'phrasal_verb', 'grammar_fix', 'pronunciation', 'tech_scenario'
                        )),
    source_type         TEXT NOT NULL CHECK (source_type IN ('seed', 'manual', 'auto_extracted')),
    fsrs_state          INTEGER NOT NULL DEFAULT 1 CHECK (fsrs_state IN (1, 2, 3)),
    is_new              INTEGER NOT NULL DEFAULT 1 CHECK (is_new IN (0, 1)),
    stability           REAL,
    difficulty          REAL,
    step                INTEGER DEFAULT 0,
    reps                INTEGER NOT NULL DEFAULT 0,
    lapses              INTEGER NOT NULL DEFAULT 0,
    scheduled_days      INTEGER NOT NULL DEFAULT 0,
    due_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_review_at      TEXT,
    suspended           INTEGER NOT NULL DEFAULT 0 CHECK (suspended IN (0, 1)),
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (deck_id, normalized_front)
);

CREATE TABLE IF NOT EXISTS study_sessions (
    id                  TEXT PRIMARY KEY,
    deck_id             INTEGER REFERENCES decks(id) ON DELETE SET NULL,
    mode                TEXT NOT NULL CHECK (mode IN ('active_review', 'roleplay', 'mixed')),
    input_mode_default  TEXT NOT NULL CHECK (input_mode_default IN ('voice', 'text')),
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'ended')),
    started_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    ended_at            TEXT,
    cards_reviewed      INTEGER NOT NULL DEFAULT 0,
    errors_extracted    INTEGER NOT NULL DEFAULT 0,
    summary_notes       TEXT
);

CREATE TABLE IF NOT EXISTS review_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key     TEXT UNIQUE,
    card_id             INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    session_id          TEXT REFERENCES study_sessions(id) ON DELETE SET NULL,
    rating              INTEGER NOT NULL CHECK (rating IN (1, 2, 3, 4)),
    fsrs_state_before   INTEGER NOT NULL,
    fsrs_state_after    INTEGER NOT NULL,
    stability_after     REAL,
    difficulty_after    REAL,
    scheduled_days      INTEGER NOT NULL,
    user_response_raw   TEXT NOT NULL,
    input_mode          TEXT NOT NULL CHECK (input_mode IN ('voice', 'text')),
    duration_ms         INTEGER,
    reviewed_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS session_turns (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL REFERENCES study_sessions(id) ON DELETE CASCADE,
    turn_index          INTEGER NOT NULL,
    speaker             TEXT NOT NULL CHECK (speaker IN ('tutor', 'user')),
    raw_transcript      TEXT NOT NULL,
    input_mode          TEXT NOT NULL CHECK (input_mode IN ('voice', 'text')),
    audio_duration_ms   INTEGER,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (session_id, turn_index)
);

CREATE TABLE IF NOT EXISTS error_logs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL REFERENCES study_sessions(id) ON DELETE CASCADE,
    turn_id             INTEGER REFERENCES session_turns(id) ON DELETE SET NULL,
    deck_id             INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    category            TEXT NOT NULL CHECK (category IN (
                            'grammar', 'vocabulary', 'phrasal_verb', 'pronunciation_asr', 'register'
                        )),
    utterance_raw       TEXT NOT NULL,
    correction          TEXT NOT NULL,
    explanation         TEXT NOT NULL,
    fingerprint_hash    TEXT NOT NULL,
    occurrence_count    INTEGER NOT NULL DEFAULT 1,
    promoted_card_id    INTEGER REFERENCES cards(id) ON DELETE SET NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_seen_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_cards_due_queue
    ON cards (suspended, is_new, due_at, deck_id);

CREATE INDEX IF NOT EXISTS idx_review_logs_card_time
    ON review_logs (card_id, reviewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_logs_session
    ON review_logs (session_id);

CREATE INDEX IF NOT EXISTS idx_error_logs_fingerprint
    ON error_logs (fingerprint_hash);

CREATE INDEX IF NOT EXISTS idx_error_logs_session
    ON error_logs (session_id, promoted_card_id);
