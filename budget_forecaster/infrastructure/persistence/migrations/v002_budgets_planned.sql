-- v1 -> v2: add budgets and planned_operations tables
CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    category TEXT NOT NULL,
    start_date TIMESTAMP NOT NULL,
    duration_value INTEGER,
    duration_unit TEXT,
    period_value INTEGER,
    period_unit TEXT,
    end_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS planned_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    category TEXT NOT NULL,
    start_date TIMESTAMP NOT NULL,
    period_value INTEGER,
    period_unit TEXT,
    end_date TIMESTAMP,
    description_hints TEXT,
    approximation_date_days INTEGER DEFAULT 5,
    approximation_amount_ratio REAL DEFAULT 0.05
);

CREATE INDEX IF NOT EXISTS idx_budgets_category ON budgets(category);
CREATE INDEX IF NOT EXISTS idx_budgets_start_date ON budgets(start_date);
CREATE INDEX IF NOT EXISTS idx_planned_operations_category ON planned_operations(category);
CREATE INDEX IF NOT EXISTS idx_planned_operations_start_date ON planned_operations(start_date);
