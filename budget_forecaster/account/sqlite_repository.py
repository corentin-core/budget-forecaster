"""SQLite repository for account data persistence."""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from budget_forecaster.account.account import Account
from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.types import Category

# Current schema version
CURRENT_SCHEMA_VERSION = 1

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


class SqliteRepository:
    """Repository for persisting account data in SQLite."""

    # Migration functions: version -> (from_version, migration_sql_or_callable)
    # Add new migrations here when schema evolves
    _migrations: dict[int, tuple[int, str | Callable[[sqlite3.Connection], None]]] = {
        1: (0, SCHEMA_V1),
        # Example for future migrations:
        # 2: (1, "ALTER TABLE operations ADD COLUMN notes TEXT;"),
        # 3: (2, lambda conn: conn.execute("UPDATE ...").commit()),
    }

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._connection: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create a database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(self._db_path)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def _get_schema_version(self) -> int:
        """Get the current schema version from the database."""
        conn = self._get_connection()
        try:
            cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()
            return row["version"] if row else 0
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return 0

    def _set_schema_version(self, version: int) -> None:
        """Set the schema version in the database."""
        conn = self._get_connection()
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        conn.commit()

    def initialize(self) -> None:
        """Initialize the database and run migrations if needed."""
        if (current_version := self._get_schema_version()) >= CURRENT_SCHEMA_VERSION:
            return

        conn = self._get_connection()

        # Apply migrations in order
        for target_version in range(current_version + 1, CURRENT_SCHEMA_VERSION + 1):
            if target_version not in self._migrations:
                raise ValueError(f"Missing migration for version {target_version}")

            from_version, migration = self._migrations[target_version]
            if from_version != target_version - 1:
                raise ValueError(
                    f"Invalid migration chain: {from_version} -> {target_version}"
                )

            print(f"Applying migration to schema version {target_version}...")

            if isinstance(migration, str):
                conn.executescript(migration)
            else:
                migration(conn)

            self._set_schema_version(target_version)

        print(f"Database schema is at version {CURRENT_SCHEMA_VERSION}")

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # Aggregated Account methods

    def get_aggregated_account_name(self) -> str | None:
        """Get the aggregated account name."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT name FROM aggregated_accounts LIMIT 1")
        row = cursor.fetchone()
        return row["name"] if row else None

    def set_aggregated_account_name(self, name: str) -> None:
        """Set or update the aggregated account name."""
        conn = self._get_connection()
        if self.get_aggregated_account_name() is None:
            conn.execute("INSERT INTO aggregated_accounts (name) VALUES (?)", (name,))
        else:
            conn.execute("UPDATE aggregated_accounts SET name = ?", (name,))
        conn.commit()

    # Account methods

    def get_all_accounts(self) -> list[Account]:
        """Get all accounts with their operations."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT id, name, balance, currency, balance_date FROM accounts"
        )
        accounts = []
        for row in cursor.fetchall():
            operations = self._get_operations_for_account(row["id"])
            accounts.append(
                Account(
                    name=row["name"],
                    balance=row["balance"],
                    currency=row["currency"],
                    balance_date=datetime.fromisoformat(row["balance_date"]),
                    operations=tuple(operations),
                )
            )
        return accounts

    def get_account_by_name(self, name: str) -> Account | None:
        """Get an account by name."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT id, name, balance, currency, balance_date FROM accounts WHERE name = ?",
            (name,),
        )
        if (row := cursor.fetchone()) is None:
            return None
        operations = self._get_operations_for_account(row["id"])
        return Account(
            name=row["name"],
            balance=row["balance"],
            currency=row["currency"],
            balance_date=datetime.fromisoformat(row["balance_date"]),
            operations=tuple(operations),
        )

    def _get_account_id(self, name: str) -> int | None:
        """Get the account id by name."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT id FROM accounts WHERE name = ?", (name,))
        row = cursor.fetchone()
        return row["id"] if row else None

    def upsert_account(self, account: Account) -> None:
        """Insert or update an account."""
        conn = self._get_connection()

        if (existing_id := self._get_account_id(account.name)) is None:
            # Get aggregated account id
            cursor = conn.execute("SELECT id FROM aggregated_accounts LIMIT 1")
            agg_row = cursor.fetchone()
            agg_id = agg_row["id"] if agg_row else 1

            cursor = conn.execute(
                """INSERT INTO accounts
                   (aggregated_account_id, name, balance, currency, balance_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    agg_id,
                    account.name,
                    account.balance,
                    account.currency,
                    account.balance_date.isoformat(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Failed to insert account")
            account_id = cursor.lastrowid
        else:
            conn.execute(
                """UPDATE accounts SET balance = ?, currency = ?, balance_date = ?
                   WHERE id = ?""",
                (
                    account.balance,
                    account.currency,
                    account.balance_date.isoformat(),
                    existing_id,
                ),
            )
            account_id = existing_id
            # Delete existing operations to replace them
            conn.execute("DELETE FROM operations WHERE account_id = ?", (account_id,))

        # Insert operations
        self._insert_operations(account_id, account.operations)
        conn.commit()

    def _insert_operations(
        self, account_id: int, operations: Iterable[HistoricOperation]
    ) -> None:
        """Insert operations for an account."""
        conn = self._get_connection()
        conn.executemany(
            """INSERT INTO operations
               (unique_id, account_id, description, category, date, amount, currency)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    op.unique_id,
                    account_id,
                    op.description,
                    op.category.value,
                    op.date.isoformat(),
                    op.amount,
                    op.currency,
                )
                for op in operations
            ],
        )

    def _get_operations_for_account(self, account_id: int) -> list[HistoricOperation]:
        """Get all operations for an account."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT unique_id, description, category, date, amount, currency
               FROM operations WHERE account_id = ?
               ORDER BY date DESC""",
            (account_id,),
        )
        return [
            HistoricOperation(
                unique_id=row["unique_id"],
                description=row["description"],
                category=Category(row["category"]),
                date=datetime.fromisoformat(row["date"]),
                amount=Amount(row["amount"], row["currency"]),
            )
            for row in cursor.fetchall()
        ]

    # Operation methods

    def update_operation(self, operation: HistoricOperation) -> None:
        """Update a single operation."""
        conn = self._get_connection()
        conn.execute(
            """UPDATE operations
               SET description = ?, category = ?, date = ?, amount = ?, currency = ?
               WHERE unique_id = ?""",
            (
                operation.description,
                operation.category.value,
                operation.date.isoformat(),
                operation.amount,
                operation.currency,
                operation.unique_id,
            ),
        )
        conn.commit()

    def operation_exists(self, unique_id: int) -> bool:
        """Check if an operation exists."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT 1 FROM operations WHERE unique_id = ?", (unique_id,)
        )
        return cursor.fetchone() is not None
