"""PersistentAccount saves all or nothing, and never reuses a referenced id."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.account.account import Account, AccountParameters
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)


@pytest.fixture(name="temp_db_path")
def temp_db_path_fixture(tmp_path: Path) -> Path:
    """A database path under the test's temporary directory."""
    return tmp_path / "test.db"


@pytest.fixture(name="sample_account")
def sample_account_fixture() -> Account:
    """An account with three categorized operations."""
    return Account(
        name="Compte courant",
        balance=1550.0,
        currency="EUR",
        balance_date=date(2024, 1, 31),
        operations=(
            HistoricOperation(
                unique_id=1,
                description="Salaire",
                amount=Amount(2500.0, "EUR"),
                category=Category.SALARY,
                operation_date=date(2024, 1, 15),
            ),
            HistoricOperation(
                unique_id=2,
                description="Courses Carrefour",
                amount=Amount(-150.0, "EUR"),
                category=Category.GROCERIES,
                operation_date=date(2024, 1, 20),
            ),
            HistoricOperation(
                unique_id=3,
                description="Loyer",
                amount=Amount(-800.0, "EUR"),
                category=Category.RENT,
                operation_date=date(2024, 1, 5),
            ),
        ),
    )


def _operation(unique_id: int, description: str) -> HistoricOperation:
    """A categorized operation with the given id."""
    return HistoricOperation(
        unique_id=unique_id,
        description=description,
        amount=Amount(-10.0, "EUR"),
        category=Category.GROCERIES,
        operation_date=date(2024, 2, 1),
    )


def _by_id(operations: tuple[HistoricOperation, ...]) -> tuple[HistoricOperation, ...]:
    """The operations in id order, whatever order storage returns them in."""
    return tuple(sorted(operations, key=lambda op: op.unique_id))


def _account(name: str, *operations: HistoricOperation) -> Account:
    """An account holding the given operations."""
    return Account(
        name=name,
        balance=0.0,
        currency="EUR",
        balance_date=date(2024, 2, 1),
        operations=operations,
    )


class TestAtomicSave:
    """A save that fails midway leaves the stored accounts exactly as they were."""

    def test_id_collision_keeps_the_stored_operations(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """A second writer took one of the new ids: nothing of the sync is stored.

        The failed run is recorded afterwards; its commit used to persist the
        operations inserted before the collision, leaving half a sync stored.
        """
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("All")
            repository.upsert_account(sample_account)

        with SqliteRepository(temp_db_path) as repository:
            persistent = PersistentAccount(repository)
            factory = persistent.next_operation_factory()
            with SqliteRepository(temp_db_path) as other_writer:
                other_writer.upsert_account(_account("Swile", _operation(5, "Cantine")))
            persistent.upsert_account(
                AccountParameters(
                    name="Compte courant",
                    balance=1520.0,
                    currency="EUR",
                    balance_date=date(2024, 2, 1),
                    operations=tuple(
                        factory.create_operation(
                            description=description,
                            amount=Amount(-10.0, "EUR"),
                            category=Category.UNCATEGORIZED,
                            operation_date=date(2024, 2, 1),
                        )
                        for description in ("Boulangerie", "Pharmacie")
                    ),
                )
            )
            with pytest.raises(sqlite3.IntegrityError):
                persistent.save()
            repository.set_setting("after_failure", "committed")

            with SqliteRepository(temp_db_path) as reader:
                stored = reader.get_account_by_name("Compte courant")
            assert _by_id(stored.operations) == _by_id(sample_account.operations)
            # The failed merge is dropped from memory too.
            assert persistent.accounts == repository.get_all_accounts()

    def test_failed_link_move_rolls_the_accounts_back(
        self, temp_db_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The link move fails after the accounts are written: both are undone."""
        file_op = _operation(1, "VIR ELUM")
        link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=7,
            iteration_date=date(2024, 2, 1),
            is_manual=True,
        )
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("All")
            repository.upsert_account(_account("BNP", file_op))
            repository.upsert_link(link)

        with SqliteRepository(temp_db_path) as repository:
            persistent = PersistentAccount(repository)
            api_op = HistoricOperation(
                unique_id=2,
                description="VIR SEPA ELUM",
                amount=Amount(-10.0, "EUR"),
                category=Category.UNCATEGORIZED,
                operation_date=date(2024, 2, 1),
                source_ref="ref-1",
            )
            persistent.upsert_account(
                AccountParameters(
                    name="BNP",
                    balance=0.0,
                    currency="EUR",
                    balance_date=date(2024, 2, 1),
                    operations=(api_op,),
                )
            )

            def failing_upsert_link(_link: OperationLink) -> None:
                raise sqlite3.OperationalError("disk I/O error")

            monkeypatch.setattr(repository, "upsert_link", failing_upsert_link)
            with pytest.raises(sqlite3.OperationalError):
                persistent.save()
            repository.set_setting("after_failure", "committed")

        with SqliteRepository(temp_db_path) as repository:
            assert repository.get_account_by_name("BNP") == _account("BNP", file_op)
            stored_link = repository.get_link_for_operation(1)
        assert stored_link is not None
        assert stored_link._replace(link_id=None) == link


def test_new_ids_skip_ids_still_referenced_by_a_link(
    temp_db_path: Path, sample_account: Account
) -> None:
    """A link left on a deleted operation never attaches to a new one."""
    with SqliteRepository(temp_db_path) as repository:
        repository.set_aggregated_account_name("All")
        repository.upsert_account(sample_account)
        repository.upsert_link(
            OperationLink(
                operation_unique_id=10,
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=date(2024, 1, 1),
            )
        )
        factory = PersistentAccount(repository).next_operation_factory()

    new_op = factory.create_operation(
        description="Boulangerie",
        amount=Amount(-10.0, "EUR"),
        category=Category.UNCATEGORIZED,
        operation_date=date(2024, 2, 1),
    )
    assert new_op.unique_id == 11
