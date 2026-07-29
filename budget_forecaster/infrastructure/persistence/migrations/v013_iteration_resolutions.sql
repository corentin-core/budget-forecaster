-- v12 -> v13: record the user's decision about an unmatched planned iteration
CREATE TABLE IF NOT EXISTS iteration_resolutions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    planned_operation_id  INTEGER NOT NULL REFERENCES planned_operations(id) ON DELETE CASCADE,
    iteration_date        TEXT NOT NULL,
    action                TEXT NOT NULL,   -- skip / postpone
    postponed_to          TEXT,
    note                  TEXT,
    decided_at            TEXT NOT NULL,   -- ISO 8601 UTC
    UNIQUE(planned_operation_id, iteration_date),
    CHECK ((action = 'postpone') = (postponed_to IS NOT NULL))
);
