-- Base schema (version 0 -> 1)
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS aggregated_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aggregated_account_id INTEGER NOT NULL REFERENCES aggregated_accounts(id),
    name TEXT NOT NULL UNIQUE,
    balance REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    balance_date TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS operations (
    unique_id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR'
);

CREATE INDEX IF NOT EXISTS idx_operations_account ON operations(account_id);
CREATE INDEX IF NOT EXISTS idx_operations_date ON operations(date);
CREATE INDEX IF NOT EXISTS idx_operations_category ON operations(category);
