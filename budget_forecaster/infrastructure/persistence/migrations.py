"""SQLite schema migrations.

Each migration is either a SQL script or a callable, keyed by the target
version. MIGRATIONS maps target_version -> (from_version, sql_or_callable).
"""

import sqlite3
from datetime import date
from typing import Callable, NamedTuple

from budget_forecaster.domain.operation.content_ref import content_ref


class Migration(NamedTuple):
    """A schema migration: the version it upgrades from and how to apply it."""

    from_version: int
    run: str | Callable[[sqlite3.Connection], None]


# Current schema version
CURRENT_SCHEMA_VERSION = 8

# Base schema (version 0 -> 1)
SCHEMA_V1 = """
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
"""

# Schema migration v1 -> v2: add budgets and planned_operations tables
SCHEMA_V2 = """
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
"""

# Schema migration v2 -> v3: add operation_links table
SCHEMA_V3 = """
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
"""


# Schema migration v3 -> v4: convert datetime strings to date strings
SCHEMA_V4 = """
UPDATE accounts SET balance_date = SUBSTR(balance_date, 1, 10)
    WHERE LENGTH(balance_date) > 10;
UPDATE operations SET date = SUBSTR(date, 1, 10)
    WHERE LENGTH(date) > 10;
UPDATE planned_operations SET start_date = SUBSTR(start_date, 1, 10)
    WHERE LENGTH(start_date) > 10;
UPDATE planned_operations SET end_date = SUBSTR(end_date, 1, 10)
    WHERE end_date IS NOT NULL AND LENGTH(end_date) > 10;
UPDATE budgets SET start_date = SUBSTR(start_date, 1, 10)
    WHERE LENGTH(start_date) > 10;
UPDATE budgets SET end_date = SUBSTR(end_date, 1, 10)
    WHERE end_date IS NOT NULL AND LENGTH(end_date) > 10;
UPDATE operation_links SET iteration_date = SUBSTR(iteration_date, 1, 10)
    WHERE LENGTH(iteration_date) > 10;
"""


# Schema migration v4 -> v5: convert French category values to language-neutral keys
# Maps old French enum values to new lowercase English keys
_CATEGORY_MIGRATION_MAP: dict[str, str] = {
    "Non catégorisé": "uncategorized",
    "Salaire": "salary",
    "Crédit d'impot": "tax_credit",
    "Allocations": "benefits",
    "Prêt maison": "house_loan",
    "Prêt travaux": "works_loan",
    "Loyer": "rent",
    "Assurance prêt": "loan_insurance",
    "Travaux": "house_works",
    "Mobilier, electromenager, deco.": "furniture",
    "Epargne": "savings",
    "Assurance auto": "car_insurance",
    "Assurance habitation": "house_insurance",
    "Autre assurance": "other_insurance",
    "Enfants": "childcare",
    "Pension alimentaire": "child_support",
    "Divertissement": "entertainment",
    "Loisirs": "leisure",
    "Voyages, vacances": "holidays",
    "Electricité": "electricity",
    "Eau": "water",
    "Internet": "internet",
    "Téléphone": "phone",
    "Courses": "groceries",
    "Habillement": "clothing",
    "Santé": "health_care",
    "Coiffeur, cosmétique, soins": "care",
    "Transports publics": "public_transport",
    "Carburant": "car_fuel",
    "Stationnement": "parking",
    "Péage": "toll",
    "Entretien automobile": "car_maintenance",
    "Crédit auto": "car_loan",
    "Cadeaux": "gifts",
    "Frais professionnels": "professional_expenses",
    "Autre": "other",
    "Dons": "charity",
    "Commissions bancaires": "bank_fees",
    "Impôts, taxes": "taxes",
}


# Schema migration v5 -> v6: add settings key-value table
SCHEMA_V6 = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT INTO settings (key, value) VALUES ('margin_threshold', '0');
"""


def _migrate_v5(conn: sqlite3.Connection) -> None:
    """Migrate category values from French to language-neutral keys."""
    for old_value, new_value in _CATEGORY_MIGRATION_MAP.items():
        for table in ("operations", "budgets", "planned_operations"):
            conn.execute(
                f"UPDATE {table} SET category = ? WHERE category = ?",  # noqa: S608
                (new_value, old_value),
            )
    conn.commit()


# Schema migration v6 -> v7: add expense_breakdown_threshold setting
SCHEMA_V7 = """
INSERT OR IGNORE INTO settings (key, value) VALUES ('expense_breakdown_threshold', '2');
"""


def _migrate_v8(conn: sqlite3.Connection) -> None:
    """Add the source_ref dedup key and backfill existing rows with their content ref.

    The column stays nullable (SQLite cannot add a NOT NULL column without a
    default); it is always populated by the app.
    """
    conn.execute("ALTER TABLE operations ADD COLUMN source_ref TEXT")
    rows = conn.execute(
        "SELECT unique_id, description, amount, date FROM operations"
    ).fetchall()
    for row in rows:
        ref = content_ref(
            row["description"], row["amount"], date.fromisoformat(row["date"])
        )
        conn.execute(
            "UPDATE operations SET source_ref = ? WHERE unique_id = ?",
            (ref, row["unique_id"]),
        )
    conn.commit()


# Migration registry, keyed by target version.
# Add new migrations here when the schema evolves.
MIGRATIONS: dict[int, Migration] = {
    1: Migration(0, SCHEMA_V1),
    2: Migration(1, SCHEMA_V2),
    3: Migration(2, SCHEMA_V3),
    4: Migration(3, SCHEMA_V4),
    5: Migration(4, _migrate_v5),
    6: Migration(5, SCHEMA_V6),
    7: Migration(6, SCHEMA_V7),
    8: Migration(7, _migrate_v8),
}
