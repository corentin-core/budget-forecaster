-- v10 -> v11: record each bank-sync run for in-app alerting
CREATE TABLE IF NOT EXISTS sync_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ran_at          TEXT NOT NULL,   -- ISO 8601 UTC
    status          TEXT NOT NULL,   -- OK / FAILED
    new_count       INTEGER,
    duplicate_count INTEGER,
    balance         REAL,
    error           TEXT
);
