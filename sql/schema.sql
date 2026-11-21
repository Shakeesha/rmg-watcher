-- Star schema for the transit delay telemetry device.

CREATE TABLE IF NOT EXISTS dim_stops (
    stop_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    latitude    REAL,
    longitude   REAL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_routes (
    route_id    TEXT PRIMARY KEY,
    short_name  TEXT NOT NULL,
    long_name   TEXT,
    mode        TEXT NOT NULL DEFAULT 'unknown',
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_stop_events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id         TEXT NOT NULL,
    route_id        TEXT NOT NULL REFERENCES dim_routes (route_id),
    stop_id         TEXT NOT NULL REFERENCES dim_stops (stop_id),
    scheduled_time  TEXT NOT NULL,
    expected_time   TEXT,
    delay_seconds   INTEGER,
    delay_category  TEXT NOT NULL,
    status          TEXT NOT NULL,
    observed_at     TEXT NOT NULL,
    UNIQUE (trip_id, stop_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_stop_events_stop_time
    ON fact_stop_events (stop_id, scheduled_time);

CREATE INDEX IF NOT EXISTS idx_fact_stop_events_route_time
    ON fact_stop_events (route_id, scheduled_time);

CREATE INDEX IF NOT EXISTS idx_fact_stop_events_observed
    ON fact_stop_events (observed_at);

CREATE TABLE IF NOT EXISTS quarantine (
    quarantine_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT NOT NULL,
    record_hash     TEXT NOT NULL,
    reason          TEXT NOT NULL,
    payload         TEXT NOT NULL,
    quarantined_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quarantine_batch
    ON quarantine (batch_id);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id              TEXT PRIMARY KEY,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    raw_count           INTEGER NOT NULL DEFAULT 0,
    valid_count         INTEGER NOT NULL DEFAULT 0,
    deduplicated_count  INTEGER NOT NULL DEFAULT 0,
    loaded_count        INTEGER NOT NULL DEFAULT 0,
    quarantined_count   INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL
);
