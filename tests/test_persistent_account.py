"""Module with tests for the PersistentAccount and SqliteRepository classes."""
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from budget_forecaster.account.account import Account, AccountParameters
from budget_forecaster.account.aggregated_account import AggregatedAccount
from budget_forecaster.account.persistent_account import PersistentAccount
from budget_forecaster.account.sqlite_repository import (
    CURRENT_SCHEMA_VERSION,
    SqliteRepository,
)
from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.types import Category


@pytest.fixture
def temp_db_path() -> Path:
    """Fixture that provides a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return Path(f.name)


@pytest.fixture
def sample_operations() -> tuple[HistoricOperation, ...]:
    """Fixture with sample operations."""
    return (
        HistoricOperation(
            unique_id=1,
            description="Salaire",
            amount=Amount(2500.0, "EUR"),
            category=Category.SALARY,
            date=datetime(2024, 1, 15),
        ),
        HistoricOperation(
            unique_id=2,
            description="Courses Carrefour",
            amount=Amount(-150.0, "EUR"),
            category=Category.GROCERIES,
            date=datetime(2024, 1, 20),
        ),
        HistoricOperation(
            unique_id=3,
            description="Loyer",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date=datetime(2024, 1, 5),
        ),
    )


@pytest.fixture
def sample_account(sample_operations: tuple[HistoricOperation, ...]) -> Account:
    """Fixture with a sample account."""
    return Account(
        name="Compte courant",
        balance=1550.0,
        currency="EUR",
        balance_date=datetime(2024, 1, 31),
        operations=sample_operations,
    )


class TestSqliteRepository:  # pylint: disable=protected-access
    """Tests for the SqliteRepository class."""

    def test_initialize_creates_schema(self, temp_db_path: Path) -> None:
        """Test that initialize creates the database schema."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        # Check schema version
        conn = repository._get_connection()
        cursor = conn.execute("SELECT version FROM schema_version")
        version = cursor.fetchone()["version"]
        assert version == CURRENT_SCHEMA_VERSION

        repository.close()

    def test_set_and_get_aggregated_account_name(self, temp_db_path: Path) -> None:
        """Test setting and getting aggregated account name."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        assert repository.get_aggregated_account_name() is None

        repository.set_aggregated_account_name("Mes comptes")
        assert repository.get_aggregated_account_name() == "Mes comptes"

        # Update name
        repository.set_aggregated_account_name("Tous mes comptes")
        assert repository.get_aggregated_account_name() == "Tous mes comptes"

        repository.close()

    def test_upsert_and_get_account(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """Test inserting and retrieving an account."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()
        repository.set_aggregated_account_name("Test")

        repository.upsert_account(sample_account)

        retrieved = repository.get_account_by_name("Compte courant")
        assert retrieved is not None
        assert retrieved.name == sample_account.name
        assert retrieved.balance == sample_account.balance
        assert retrieved.currency == sample_account.currency
        assert retrieved.balance_date == sample_account.balance_date
        assert len(retrieved.operations) == len(sample_account.operations)

        repository.close()

    def test_upsert_account_updates_existing(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """Test that upsert updates an existing account."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()
        repository.set_aggregated_account_name("Test")

        repository.upsert_account(sample_account)

        # Update with new balance
        updated_account = sample_account._replace(balance=2000.0)
        repository.upsert_account(updated_account)

        retrieved = repository.get_account_by_name("Compte courant")
        assert retrieved is not None
        assert retrieved.balance == 2000.0

        repository.close()

    def test_get_all_accounts(
        self, temp_db_path: Path, sample_operations: tuple[HistoricOperation, ...]
    ) -> None:
        """Test getting all accounts."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()
        repository.set_aggregated_account_name("Test")

        account1 = Account(
            name="Compte 1",
            balance=1000.0,
            currency="EUR",
            balance_date=datetime(2024, 1, 31),
            operations=sample_operations[:2],
        )
        account2 = Account(
            name="Compte 2",
            balance=500.0,
            currency="EUR",
            balance_date=datetime(2024, 1, 31),
            operations=(sample_operations[2],),
        )

        repository.upsert_account(account1)
        repository.upsert_account(account2)

        accounts = repository.get_all_accounts()
        assert len(accounts) == 2
        names = {acc.name for acc in accounts}
        assert names == {"Compte 1", "Compte 2"}

        repository.close()

    def test_update_operation(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """Test updating a single operation."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()
        repository.set_aggregated_account_name("Test")
        repository.upsert_account(sample_account)

        # Update operation category
        updated_op = sample_account.operations[1].replace(category=Category.OTHER)
        repository.update_operation(updated_op)

        retrieved = repository.get_account_by_name("Compte courant")
        assert retrieved is not None
        op = next(o for o in retrieved.operations if o.unique_id == 2)
        assert op.category == Category.OTHER

        repository.close()

    def test_operation_exists(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """Test checking if an operation exists."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()
        repository.set_aggregated_account_name("Test")
        repository.upsert_account(sample_account)

        assert repository.operation_exists(1) is True
        assert repository.operation_exists(999) is False

        repository.close()


class TestPersistentAccount:  # pylint: disable=protected-access
    """Tests for the PersistentAccount class."""

    def test_load_raises_when_no_account(self, temp_db_path: Path) -> None:
        """Test that load raises FileNotFoundError when no account exists."""
        persistent = PersistentAccount(temp_db_path)

        with pytest.raises(FileNotFoundError):
            persistent.load()

        persistent.close()

    def test_save_and_load(self, temp_db_path: Path, sample_account: Account) -> None:
        """Test saving and loading an aggregated account."""
        # Create and save
        persistent = PersistentAccount(temp_db_path)
        persistent._repository.initialize()
        persistent._aggregated_account = AggregatedAccount(
            "Mes comptes", [sample_account]
        )
        persistent.save()
        persistent.close()

        # Load in new instance
        persistent2 = PersistentAccount(temp_db_path)
        persistent2.load()

        assert persistent2.account.name == "Mes comptes"
        assert len(persistent2.accounts) == 1
        assert persistent2.accounts[0].name == "Compte courant"
        assert len(persistent2.accounts[0].operations) == 3

        persistent2.close()

    def test_account_raises_when_not_loaded(self, temp_db_path: Path) -> None:
        """Test that accessing account raises when not loaded."""
        persistent = PersistentAccount(temp_db_path)

        with pytest.raises(FileNotFoundError):
            _ = persistent.account

        persistent.close()

    def test_upsert_account(self, temp_db_path: Path, sample_account: Account) -> None:
        """Test upserting account through the interface."""
        persistent = PersistentAccount(temp_db_path)
        persistent._repository.initialize()
        persistent._aggregated_account = AggregatedAccount(
            "Mes comptes", [sample_account]
        )
        persistent.save()

        # Add new operation via upsert
        new_operation = HistoricOperation(
            unique_id=4,
            description="Nouvelle opération",
            amount=Amount(-50.0, "EUR"),
            category=Category.OTHER,
            date=datetime(2024, 2, 1),
        )
        new_account_params = AccountParameters(
            name="Compte courant",
            balance=1500.0,
            currency="EUR",
            balance_date=datetime(2024, 2, 1),
            operations=(new_operation,),
        )
        persistent.upsert_account(new_account_params)
        persistent.save()
        persistent.close()

        # Reload and verify
        persistent2 = PersistentAccount(temp_db_path)
        persistent2.load()

        account = persistent2.accounts[0]
        assert len(account.operations) == 4

        persistent2.close()
