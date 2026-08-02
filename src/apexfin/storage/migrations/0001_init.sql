-- APEXFIN initial schema. Single source of truth for docs/DATA_CONTRACT.md.
-- Editing this file after it has been applied is a checksum error, by design.

CREATE TABLE bronze_records (
    id            INTEGER PRIMARY KEY,
    source_name   TEXT    NOT NULL,
    domain        TEXT    NOT NULL,
    symbol        TEXT    NOT NULL,
    event_time    TEXT    NOT NULL,
    event_date    TEXT    NOT NULL,
    payload       TEXT    NOT NULL,
    payload_hash  TEXT    NOT NULL,
    revision      INTEGER NOT NULL DEFAULT 0,
    source_url    TEXT,
    run_id        TEXT    NOT NULL,
    ingested_at   TEXT    NOT NULL,
    UNIQUE (source_name, symbol, event_time)
);

CREATE INDEX idx_bronze_series_date ON bronze_records (source_name, symbol, event_date DESC);
CREATE INDEX idx_bronze_run ON bronze_records (run_id);

CREATE TABLE bronze_revisions (
    id             INTEGER PRIMARY KEY,
    bronze_id      INTEGER NOT NULL REFERENCES bronze_records(id) ON DELETE CASCADE,
    revision       INTEGER NOT NULL,
    payload        TEXT    NOT NULL,
    payload_hash   TEXT    NOT NULL,
    superseded_at  TEXT    NOT NULL,
    run_id         TEXT    NOT NULL
);

CREATE INDEX idx_bronze_rev_parent ON bronze_revisions (bronze_id, revision DESC);

CREATE TABLE silver_points (
    id              INTEGER PRIMARY KEY,
    bronze_id       INTEGER REFERENCES bronze_records(id) ON DELETE SET NULL,
    source_name     TEXT    NOT NULL,
    domain          TEXT    NOT NULL,
    symbol          TEXT    NOT NULL,
    event_time      TEXT    NOT NULL,
    event_date      TEXT    NOT NULL,
    value           REAL    NOT NULL,
    value_secondary REAL,
    unit            TEXT,
    quality_score   REAL    NOT NULL CHECK (quality_score >= 0 AND quality_score <= 1),
    is_filled       INTEGER NOT NULL DEFAULT 0 CHECK (is_filled IN (0, 1)),
    payload_json    TEXT,
    run_id          TEXT    NOT NULL,
    built_at        TEXT    NOT NULL,
    UNIQUE (source_name, symbol, event_time)
);

CREATE INDEX idx_silver_series_date ON silver_points (source_name, symbol, event_date DESC);
CREATE INDEX idx_silver_domain_date ON silver_points (domain, event_date DESC);

CREATE TABLE quality_findings (
    id           INTEGER PRIMARY KEY,
    run_id       TEXT NOT NULL,
    check_id     TEXT NOT NULL,
    severity     TEXT NOT NULL CHECK (severity IN ('INFO','WARNING','BLOCKING')),
    tier         TEXT NOT NULL CHECK (tier IN
                   ('risk_essential','support','display_only','research')),
    source_name  TEXT NOT NULL,
    symbol       TEXT,
    message      TEXT NOT NULL,
    observed     TEXT,
    expected     TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX idx_findings_run ON quality_findings (run_id, severity);
CREATE INDEX idx_findings_source ON quality_findings (source_name, created_at DESC);

CREATE TABLE series_health (
    source_name           TEXT NOT NULL,
    symbol                TEXT NOT NULL,
    last_event_date       TEXT,
    lag_trading_days      INTEGER,
    max_lag_trading_days  INTEGER NOT NULL CHECK (max_lag_trading_days >= 0),
    state                 TEXT NOT NULL CHECK (state IN
                            ('healthy','degraded','blocked','unknown')),
    last_checked_at       TEXT NOT NULL,
    consecutive_fails     INTEGER NOT NULL DEFAULT 0,
    note                  TEXT,
    PRIMARY KEY (source_name, symbol)
);

CREATE TABLE pipeline_runs (
    run_id        TEXT PRIMARY KEY,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    state         TEXT NOT NULL CHECK (state IN
                    ('RUNNING','PASS','DEGRADED','BLOCKED','FAILED')),
    manifest_hash TEXT NOT NULL,
    fixture_pack  TEXT,
    as_of_date    TEXT NOT NULL,
    exit_code     INTEGER,
    summary       TEXT
);

CREATE TABLE step_runs (
    id          INTEGER PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    step_name   TEXT NOT NULL,
    tier        TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('OK','FAILED','SKIPPED')),
    started_at  TEXT NOT NULL,
    duration_s  REAL NOT NULL,
    message     TEXT,
    metrics     TEXT
);

CREATE INDEX idx_step_runs_run ON step_runs (run_id);
CREATE INDEX idx_step_runs_perf ON step_runs (step_name, duration_s DESC);

CREATE TABLE decisions (
    id            INTEGER PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    as_of_date    TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    stance        TEXT NOT NULL CHECK (stance IN ('long','short','flat','no_call')),
    confidence    REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    strategy      TEXT NOT NULL,
    rationale     TEXT NOT NULL,
    inputs_json   TEXT NOT NULL,
    degraded      INTEGER NOT NULL DEFAULT 0 CHECK (degraded IN (0,1)),
    created_at    TEXT NOT NULL,
    UNIQUE (run_id, symbol, strategy)
);

CREATE TABLE opinion_ledger (
    id              INTEGER PRIMARY KEY,
    decision_id     INTEGER NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    symbol          TEXT NOT NULL,
    stated_on       TEXT NOT NULL,
    horizon_days    INTEGER NOT NULL,
    due_on          TEXT NOT NULL,
    stance          TEXT NOT NULL,
    reference_value REAL NOT NULL,
    settled_on      TEXT,
    settled_value   REAL,
    outcome         TEXT CHECK (outcome IN ('hit','miss','void','pending')),
    settled_note    TEXT
);

CREATE INDEX idx_ledger_due ON opinion_ledger (due_on) WHERE outcome = 'pending';
