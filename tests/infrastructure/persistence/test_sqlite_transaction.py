"""Tests for SqliteRepository.transaction: all-or-nothing writes."""

import sqlite3
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)


@pytest.fixture(name="db_path")
def db_path_fixture(tmp_path: Path) -> Path:
    """An initialized database file."""
    path = tmp_path / "test.db"
    with SqliteRepository(path):
        pass
    return path


@pytest.fixture(name="repository")
def repository_fixture(db_path: Path) -> Iterator[SqliteRepository]:
    """The repository under test."""
    with SqliteRepository(db_path) as repo:
        yield repo


def _stored_setting(db_path: Path, key: str) -> str | None:
    """Read a setting through a second connection, as another process would."""
    with SqliteRepository(db_path) as other:
        return other.get_setting(key)


class TestTransaction:
    """Writes inside a block are committed together or not at all."""

    def test_commits_on_success(
        self, repository: SqliteRepository, db_path: Path
    ) -> None:
        """Both writes are stored once the block exits."""
        with repository.transaction():
            repository.set_setting("a", "1")
            repository.set_setting("b", "2")
        assert (_stored_setting(db_path, "a"), _stored_setting(db_path, "b")) == (
            "1",
            "2",
        )

    def test_method_commits_wait_for_the_block(
        self, repository: SqliteRepository, db_path: Path
    ) -> None:
        """A method's own commit does not publish the write mid-block."""
        with repository.transaction():
            repository.set_setting("a", "1")
            assert _stored_setting(db_path, "a") is None

    def test_rolls_back_on_error(
        self, repository: SqliteRepository, db_path: Path
    ) -> None:
        """An error in the block discards every write made in it."""
        with pytest.raises(RuntimeError), repository.transaction():
            repository.set_setting("a", "1")
            raise RuntimeError("boom")
        assert _stored_setting(db_path, "a") is None
        assert repository.get_setting("a") is None

    def test_nested_block_joins_the_outer_one(
        self, repository: SqliteRepository, db_path: Path
    ) -> None:
        """A completed inner block is still rolled back when the outer one fails."""
        with pytest.raises(RuntimeError), repository.transaction():
            with repository.transaction():
                repository.set_setting("a", "1")
            raise RuntimeError("boom")
        assert _stored_setting(db_path, "a") is None

    def test_usable_after_a_rollback(
        self, repository: SqliteRepository, db_path: Path
    ) -> None:
        """A rolled-back block leaves the repository ready for the next write."""
        with pytest.raises(RuntimeError), repository.transaction():
            raise RuntimeError("boom")
        repository.set_setting("a", "1")
        assert _stored_setting(db_path, "a") == "1"


def _account(*operation_ids: int) -> Account:
    """An account whose operations carry the given ids."""
    return Account(
        name="BNP",
        balance=0.0,
        currency="EUR",
        balance_date=date(2024, 2, 1),
        operations=tuple(
            HistoricOperation(
                unique_id=unique_id,
                description=f"Op {unique_id}",
                amount=Amount(-10.0, "EUR"),
                category=Category.GROCERIES,
                operation_date=date(2024, 2, 1),
            )
            for unique_id in operation_ids
        ),
    )


class TestAtomicMethods:
    """A writing method that fails midway stores nothing and leaves no transaction open."""

    def test_failed_write_keeps_the_stored_account(
        self, repository: SqliteRepository, db_path: Path
    ) -> None:
        """The delete before a failing reinsert is rolled back with it."""
        repository.set_aggregated_account_name("All")
        repository.upsert_account(_account(1, 2))
        with pytest.raises(sqlite3.IntegrityError):
            repository.upsert_account(_account(3, 3))
        with SqliteRepository(db_path) as other:
            stored = other.get_account_by_name("BNP")
        assert {op.unique_id for op in stored.operations} == {1, 2}

    def test_next_transaction_works_after_a_failed_write(
        self, repository: SqliteRepository, db_path: Path
    ) -> None:
        """A failed write does not leave a transaction open behind it."""
        repository.set_aggregated_account_name("All")
        with pytest.raises(sqlite3.IntegrityError):
            repository.upsert_account(_account(3, 3))
        with repository.transaction():
            repository.set_setting("a", "1")
        assert _stored_setting(db_path, "a") == "1"
