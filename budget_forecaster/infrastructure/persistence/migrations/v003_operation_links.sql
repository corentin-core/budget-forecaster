-- v2 -> v3: add operation_links table
CREATE TABLE IF NOT EXISTS operation_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_unique_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    iteration_date TIMESTAMP NOT NULL,
    is_manual BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    UNIQUE(operation_unique_id)
);

CREATE INDEX IF NOT EXISTS idx_operation_links_operation ON operation_links(operation_unique_id);
CREATE INDEX IF NOT EXISTS idx_operation_links_target ON operation_links(target_type, target_id);
