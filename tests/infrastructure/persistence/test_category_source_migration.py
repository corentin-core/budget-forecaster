"""Tests for the v15 migration recording how categories were set."""

import sqlite3
from datetime import date
from pathlib import Path

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category, CategorySource
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.infrastructure.persistence.migrations import MIGRATIONS
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)

_DAY = date(2025, 1, 31)


def _op(
    unique_id: int, category: Category, source: CategorySource | None
) -> HistoricOperation:
    return HistoricOperation(
        unique_id=unique_id,
        description="op",
        amount=Amount(-1.0),
        category=category,
        operation_date=_DAY,
        category_source=source,
    )


def test_existing_categories_become_manual(tmp_path: Path) -> None:
    """Every category stored before v15 was the user's; uncategorized has no source."""
    conn = sqlite3.connect(tmp_path / "test.db")
    for version in range(1, 15):
        migration = MIGRATIONS[version]
        if isinstance(migration, str):
            conn.executescript(migration)
        else:
            migration(conn)
    conn.execute("INSERT INTO aggregated_accounts (id, name) VALUES (1, 'All')")
    conn.execute(
        "INSERT INTO accounts (id, aggregated_account_id, name, balance, currency, "
        "balance_date) VALUES (1, 1, 'BNP', 0.0, 'EUR', '2025-01-31')"
    )
    conn.executemany(
        "INSERT INTO operations (unique_id, account_id, description, category, "
        "date, amount, currency) VALUES (?, 1, 'op', ?, '2025-01-10', -1.0, 'EUR')",
        [(1, "groceries"), (2, "uncategorized")],
    )

    conn.executescript(MIGRATIONS[15])

    assert dict(
        conn.execute("SELECT unique_id, category_source FROM operations").fetchall()
    ) == {1: "manual", 2: None}


def test_category_source_round_trips(tmp_path: Path) -> None:
    """The source is saved and read back with the operation."""
    with SqliteRepository(tmp_path / "test.db") as repository:
        repository.set_aggregated_account_name("All")
        repository.upsert_account(
            Account(
                name="BNP",
                balance=0.0,
                currency="EUR",
                balance_date=_DAY,
                operations=(
                    _op(1, Category.GROCERIES, CategorySource.RULE),
                    _op(2, Category.UNCATEGORIZED, None),
                ),
            )
        )

        accounts = repository.get_all_accounts()

    assert {op.unique_id: op.category_source for op in accounts[0].operations} == {
        1: CategorySource.RULE,
        2: None,
    }
