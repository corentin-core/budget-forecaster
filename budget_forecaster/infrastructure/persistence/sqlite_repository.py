"""SQLite repository for account data persistence."""

# pylint: disable=too-many-arguments,too-many-positional-arguments
# pylint: disable=too-many-public-methods

import json
import logging
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Iterable, Self

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    DateRangeInterface,
    RecurringDateRange,
    RecurringDay,
    SingleDay,
)
from budget_forecaster.core.types import Category, LinkType, OperationId, TargetId
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.exceptions import (
    AccountNotFoundError,
    BudgetNotFoundError,
    PersistenceError,
    PlannedOperationNotFoundError,
)
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)

logger = logging.getLogger(__name__)

# Current schema version
CURRENT_SCHEMA_VERSION = 4

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


class SqliteRepository(RepositoryInterface):
    """Repository for persisting account data in SQLite."""

    # Migration functions: version -> (from_version, migration_sql_or_callable)
    # Add new migrations here when schema evolves
    _migrations: dict[int, tuple[int, str | Callable[[sqlite3.Connection], None]]] = {
        1: (0, SCHEMA_V1),
        2: (1, SCHEMA_V2),
        3: (2, SCHEMA_V3),
        4: (3, SCHEMA_V4),
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

            logger.info("Applying migration to schema version %d", target_version)

            if isinstance(migration, str):
                conn.executescript(migration)
            else:
                migration(conn)

            self._set_schema_version(target_version)

        logger.info("Database schema is at version %d", CURRENT_SCHEMA_VERSION)

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> Self:
        """Enter the context manager."""
        self.initialize()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit the context manager."""
        self.close()

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

    def get_all_accounts(self) -> tuple[Account, ...]:
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
                    balance_date=date.fromisoformat(row["balance_date"]),
                    operations=tuple(operations),
                )
            )
        return tuple(accounts)

    def get_account_by_name(self, name: str) -> Account:
        """Get an account by name."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT id, name, balance, currency, balance_date FROM accounts WHERE name = ?",
            (name,),
        )
        if (row := cursor.fetchone()) is None:
            raise AccountNotFoundError(name)
        operations = self._get_operations_for_account(row["id"])
        return Account(
            name=row["name"],
            balance=row["balance"],
            currency=row["currency"],
            balance_date=date.fromisoformat(row["balance_date"]),
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
                raise PersistenceError("Failed to insert account")
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
                    op.operation_date.isoformat(),
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
                operation_date=date.fromisoformat(row["date"]),
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
                operation.operation_date.isoformat(),
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

    # Budget methods

    def get_all_budgets(self) -> tuple[Budget, ...]:
        """Get all budgets."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT id, description, amount, currency, category, start_date,
               duration_value, duration_unit, period_value, period_unit, end_date
               FROM budgets ORDER BY start_date"""
        )
        return tuple(self._row_to_budget(row) for row in cursor.fetchall())

    def get_budget_by_id(self, budget_id: int) -> Budget:
        """Get a budget by id."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT id, description, amount, currency, category, start_date,
               duration_value, duration_unit, period_value, period_unit, end_date
               FROM budgets WHERE id = ?""",
            (budget_id,),
        )
        if (row := cursor.fetchone()) is None:
            raise BudgetNotFoundError(budget_id)
        return self._row_to_budget(row)

    def upsert_budget(self, budget: Budget) -> int:
        """Insert or update a budget. Returns the budget id."""
        conn = self._get_connection()
        date_range_data = self._serialize_budget_date_range(budget.date_range)

        if budget.id is not None:
            # Update existing
            conn.execute(
                """UPDATE budgets SET description = ?, amount = ?, currency = ?,
                   category = ?, start_date = ?, duration_value = ?, duration_unit = ?,
                   period_value = ?, period_unit = ?, end_date = ?
                   WHERE id = ?""",
                (
                    budget.description,
                    budget.amount,
                    budget.currency,
                    budget.category.value,
                    date_range_data["start_date"],
                    date_range_data["duration_value"],
                    date_range_data["duration_unit"],
                    date_range_data["period_value"],
                    date_range_data["period_unit"],
                    date_range_data["end_date"],
                    budget.id,
                ),
            )
            conn.commit()
            return budget.id
        # Insert new
        cursor = conn.execute(
            """INSERT INTO budgets (description, amount, currency, category,
               start_date, duration_value, duration_unit, period_value,
               period_unit, end_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                budget.description,
                budget.amount,
                budget.currency,
                budget.category.value,
                date_range_data["start_date"],
                date_range_data["duration_value"],
                date_range_data["duration_unit"],
                date_range_data["period_value"],
                date_range_data["period_unit"],
                date_range_data["end_date"],
            ),
        )
        conn.commit()
        if cursor.lastrowid is None:
            raise PersistenceError("Failed to insert budget")
        return cursor.lastrowid

    def delete_budget(self, budget_id: int) -> None:
        """Delete a budget."""
        conn = self._get_connection()
        conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
        conn.commit()

    def _row_to_budget(self, row: sqlite3.Row) -> Budget:
        """Convert a database row to a Budget object."""
        dr = self._deserialize_budget_date_range(
            start_date=date.fromisoformat(row["start_date"]),
            duration_value=row["duration_value"],
            duration_unit=row["duration_unit"],
            period_value=row["period_value"],
            period_unit=row["period_unit"],
            end_date=(date.fromisoformat(row["end_date"]) if row["end_date"] else None),
        )
        return Budget(
            record_id=row["id"],
            description=row["description"],
            amount=Amount(row["amount"], row["currency"]),
            category=Category(row["category"]),
            date_range=dr,
        )

    # Planned Operation methods

    def get_all_planned_operations(self) -> tuple[PlannedOperation, ...]:
        """Get all planned operations."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT id, description, amount, currency, category, start_date,
               period_value, period_unit, end_date, description_hints,
               approximation_date_days, approximation_amount_ratio
               FROM planned_operations ORDER BY start_date"""
        )
        return tuple(self._row_to_planned_operation(row) for row in cursor.fetchall())

    def get_planned_operation_by_id(self, op_id: int) -> PlannedOperation:
        """Get a planned operation by id."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT id, description, amount, currency, category, start_date,
               period_value, period_unit, end_date, description_hints,
               approximation_date_days, approximation_amount_ratio
               FROM planned_operations WHERE id = ?""",
            (op_id,),
        )
        if (row := cursor.fetchone()) is None:
            raise PlannedOperationNotFoundError(op_id)
        return self._row_to_planned_operation(row)

    def upsert_planned_operation(self, op: PlannedOperation) -> int:
        """Insert or update a planned operation. Returns the operation id."""
        conn = self._get_connection()
        date_range_data = self._serialize_planned_op_date_range(op.date_range)
        hints = (
            json.dumps(list(op.matcher.description_hints))
            if op.matcher.description_hints
            else None
        )
        approx_days = int(op.matcher.approximation_date_range.total_seconds() / 86400)

        if op.id is not None:
            # Update existing
            conn.execute(
                """UPDATE planned_operations SET description = ?, amount = ?,
                   currency = ?, category = ?, start_date = ?, period_value = ?,
                   period_unit = ?, end_date = ?, description_hints = ?,
                   approximation_date_days = ?, approximation_amount_ratio = ?
                   WHERE id = ?""",
                (
                    op.description,
                    op.amount,
                    op.currency,
                    op.category.value,
                    date_range_data["start_date"],
                    date_range_data["period_value"],
                    date_range_data["period_unit"],
                    date_range_data["end_date"],
                    hints,
                    approx_days,
                    op.matcher.approximation_amount_ratio,
                    op.id,
                ),
            )
            conn.commit()
            return op.id
        # Insert new
        cursor = conn.execute(
            """INSERT INTO planned_operations (description, amount, currency,
               category, start_date, period_value, period_unit, end_date,
               description_hints, approximation_date_days, approximation_amount_ratio)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                op.description,
                op.amount,
                op.currency,
                op.category.value,
                date_range_data["start_date"],
                date_range_data["period_value"],
                date_range_data["period_unit"],
                date_range_data["end_date"],
                hints,
                approx_days,
                op.matcher.approximation_amount_ratio,
            ),
        )
        conn.commit()
        if cursor.lastrowid is None:
            raise PersistenceError("Failed to insert planned operation")
        return cursor.lastrowid

    def delete_planned_operation(self, op_id: int) -> None:
        """Delete a planned operation."""
        conn = self._get_connection()
        conn.execute("DELETE FROM planned_operations WHERE id = ?", (op_id,))
        conn.commit()

    def _row_to_planned_operation(self, row: sqlite3.Row) -> PlannedOperation:
        """Convert a database row to a PlannedOperation object."""
        dr = self._deserialize_planned_op_date_range(
            start_date=date.fromisoformat(row["start_date"]),
            period_value=row["period_value"],
            period_unit=row["period_unit"],
            end_date=(date.fromisoformat(row["end_date"]) if row["end_date"] else None),
        )
        if hints_str := row["description_hints"]:
            # Support both JSON (new) and semicolon-delimited (legacy) formats
            if hints_str.startswith("["):
                hints = set(json.loads(hints_str))
            else:
                hints = set(hints_str.split(";"))
        else:
            hints = set()

        op = PlannedOperation(
            record_id=row["id"],
            description=row["description"],
            amount=Amount(row["amount"], row["currency"]),
            category=Category(row["category"]),
            date_range=dr,
        )
        op.set_matcher_params(
            description_hints=hints,
            approximation_date_range=timedelta(days=row["approximation_date_days"]),
            approximation_amount_ratio=row["approximation_amount_ratio"],
        )
        return op

    # DateRange serialization helpers

    def _relativedelta_to_db(self, rd: relativedelta) -> tuple[int, str]:
        """Convert relativedelta to (value, unit) for database storage.

        Note: relativedelta.weeks is a computed property (days // 7), so we must
        check rd.days BEFORE rd.weeks to avoid losing precision.
        """
        if rd.years:
            return (rd.years, "years")
        if rd.months:
            return (rd.months, "months")
        if rd.days:
            # Check days before weeks because rd.weeks is computed as days // 7
            return (rd.days, "days")
        if rd.weeks:
            # Only reached if explicitly set as weeks with no days
            return (rd.weeks * 7, "days")
        # Default to days=0
        return (0, "days")

    def _db_to_relativedelta(
        self, value: int | None, unit: str | None
    ) -> relativedelta:
        """Convert (value, unit) from database to relativedelta."""
        if value is None or unit is None:
            return relativedelta()
        if unit == "years":
            return relativedelta(years=value)
        if unit == "months":
            return relativedelta(months=value)
        if unit == "weeks":
            return relativedelta(weeks=value)
        return relativedelta(days=value)

    def _serialize_budget_date_range(self, date_range: DateRangeInterface) -> dict:
        """Serialize a budget date range to database fields."""
        result: dict = {
            "start_date": date_range.start_date.isoformat(),
            "duration_value": None,
            "duration_unit": None,
            "period_value": None,
            "period_unit": None,
            "end_date": None,
        }

        if isinstance(date_range, RecurringDateRange):
            # Get duration from base date range
            dur_val, dur_unit = self._relativedelta_to_db(date_range.duration)
            result["duration_value"] = dur_val
            result["duration_unit"] = dur_unit
            # Get period
            per_val, per_unit = self._relativedelta_to_db(date_range.period)
            result["period_value"] = per_val
            result["period_unit"] = per_unit
            # Get end date
            if date_range.last_date != date.max:
                result["end_date"] = date_range.last_date.isoformat()
        elif isinstance(date_range, DateRange):
            # Get the relativedelta duration
            dur_val, dur_unit = self._relativedelta_to_db(date_range.duration)
            result["duration_value"] = dur_val
            result["duration_unit"] = dur_unit

        return result

    def _deserialize_budget_date_range(
        self,
        start_date: date,
        duration_value: int | None,
        duration_unit: str | None,
        period_value: int | None,
        period_unit: str | None,
        end_date: date | None,
    ) -> DateRangeInterface:
        """Deserialize budget date range from database fields."""
        duration = self._db_to_relativedelta(duration_value, duration_unit)
        inner_range = DateRange(start_date, duration)

        if period_value is not None and period_unit is not None:
            period = self._db_to_relativedelta(period_value, period_unit)
            expiration = end_date if end_date else date.max
            return RecurringDateRange(inner_range, period, expiration)

        return inner_range

    def _serialize_planned_op_date_range(self, date_range: DateRangeInterface) -> dict:
        """Serialize a planned operation date range to database fields."""
        result: dict = {
            "start_date": date_range.start_date.isoformat(),
            "period_value": None,
            "period_unit": None,
            "end_date": None,
        }

        if isinstance(date_range, RecurringDay):
            # period is inherited from RecurringDateRange
            per_val, per_unit = self._relativedelta_to_db(date_range.period)
            result["period_value"] = per_val
            result["period_unit"] = per_unit
            if date_range.last_date != date.max:
                result["end_date"] = date_range.last_date.isoformat()

        return result

    def _deserialize_planned_op_date_range(
        self,
        start_date: date,
        period_value: int | None,
        period_unit: str | None,
        end_date: date | None,
    ) -> SingleDay | RecurringDay:
        """Deserialize planned operation date range from database fields."""
        if period_value is not None and period_unit is not None:
            period = self._db_to_relativedelta(period_value, period_unit)
            expiration = end_date if end_date else date.max
            return RecurringDay(start_date, period, expiration)

        return SingleDay(start_date)

    # Operation Link methods

    def get_link_for_operation(
        self, operation_unique_id: OperationId
    ) -> OperationLink | None:
        """Get the link for a historic operation, if any."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT id, operation_unique_id, target_type, target_id, iteration_date,
               is_manual, notes
               FROM operation_links WHERE operation_unique_id = ?""",
            (operation_unique_id,),
        )
        if (row := cursor.fetchone()) is None:
            return None
        return self._row_to_operation_link(row)

    def get_all_links(self) -> tuple[OperationLink, ...]:
        """Get all operation links."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT id, operation_unique_id, target_type, target_id, iteration_date,
               is_manual, notes
               FROM operation_links
               ORDER BY target_type, target_id, iteration_date"""
        )
        return tuple(self._row_to_operation_link(row) for row in cursor.fetchall())

    def get_links_for_planned_operation(
        self, planned_op_id: int
    ) -> tuple[OperationLink, ...]:
        """Get all links targeting a planned operation."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT id, operation_unique_id, target_type, target_id, iteration_date,
               is_manual, notes
               FROM operation_links
               WHERE target_type = ? AND target_id = ?
               ORDER BY iteration_date""",
            (LinkType.PLANNED_OPERATION, planned_op_id),
        )
        return tuple(self._row_to_operation_link(row) for row in cursor.fetchall())

    def get_links_for_budget(self, budget_id: int) -> tuple[OperationLink, ...]:
        """Get all links targeting a budget."""
        conn = self._get_connection()
        cursor = conn.execute(
            """SELECT id, operation_unique_id, target_type, target_id, iteration_date,
               is_manual, notes
               FROM operation_links
               WHERE target_type = ? AND target_id = ?
               ORDER BY iteration_date""",
            (LinkType.BUDGET, budget_id),
        )
        return tuple(self._row_to_operation_link(row) for row in cursor.fetchall())

    def upsert_link(self, link: OperationLink) -> None:
        """Insert or update a link, preserving the id on update."""
        conn = self._get_connection()
        conn.execute(
            """INSERT INTO operation_links
               (operation_unique_id, target_type, target_id, iteration_date, is_manual, notes)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(operation_unique_id) DO UPDATE SET
                   target_type = excluded.target_type,
                   target_id = excluded.target_id,
                   iteration_date = excluded.iteration_date,
                   is_manual = excluded.is_manual,
                   notes = excluded.notes""",
            (
                link.operation_unique_id,
                link.target_type,
                link.target_id,
                link.iteration_date.isoformat(),
                link.is_manual,
                link.notes,
            ),
        )
        conn.commit()

    def delete_link(self, operation_unique_id: OperationId) -> None:
        """Delete the link for an operation."""
        conn = self._get_connection()
        conn.execute(
            "DELETE FROM operation_links WHERE operation_unique_id = ?",
            (operation_unique_id,),
        )
        conn.commit()

    def delete_automatic_links_for_target(
        self, target_type: LinkType, target_id: TargetId
    ) -> None:
        """Delete all automatic links for a given target."""
        conn = self._get_connection()
        conn.execute(
            """DELETE FROM operation_links
               WHERE target_type = ? AND target_id = ? AND is_manual = FALSE""",
            (target_type, target_id),
        )
        conn.commit()

    def delete_links_for_target(
        self, target_type: LinkType, target_id: TargetId
    ) -> None:
        """Delete all links for a given target (both manual and automatic)."""
        conn = self._get_connection()
        conn.execute(
            """DELETE FROM operation_links
               WHERE target_type = ? AND target_id = ?""",
            (target_type, target_id),
        )
        conn.commit()

    def _row_to_operation_link(self, row: sqlite3.Row) -> OperationLink:
        """Convert a database row to an OperationLink object."""
        return OperationLink(
            operation_unique_id=row["operation_unique_id"],
            target_type=LinkType(row["target_type"]),
            target_id=row["target_id"],
            iteration_date=date.fromisoformat(row["iteration_date"]),
            is_manual=bool(row["is_manual"]),
            notes=row["notes"],
            link_id=row["id"],
        )
