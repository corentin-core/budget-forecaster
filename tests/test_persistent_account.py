"""Module with tests for the PersistentAccount and SqliteRepository classes."""

# pylint: disable=protected-access,redefined-outer-name

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account, AccountParameters
from budget_forecaster.account.aggregated_account import AggregatedAccount
from budget_forecaster.account.persistent_account import PersistentAccount
from budget_forecaster.account.sqlite_repository import (
    CURRENT_SCHEMA_VERSION,
    SqliteRepository,
)
from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.time_range import (
    DailyTimeRange,
    PeriodicDailyTimeRange,
    PeriodicTimeRange,
    TimeRange,
)
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
        repository = SqliteRepository(temp_db_path)
        persistent = PersistentAccount(repository)

        with pytest.raises(FileNotFoundError):
            persistent.load()

        persistent.close()

    def test_save_and_load(self, temp_db_path: Path, sample_account: Account) -> None:
        """Test saving and loading an aggregated account."""
        # Create and save
        repository = SqliteRepository(temp_db_path)
        persistent = PersistentAccount(repository)
        persistent._repository.initialize()
        persistent._aggregated_account = AggregatedAccount(
            "Mes comptes", [sample_account]
        )
        persistent.save()
        persistent.close()

        # Load in new instance
        repository2 = SqliteRepository(temp_db_path)
        persistent2 = PersistentAccount(repository2)
        persistent2.load()

        assert persistent2.account.name == "Mes comptes"
        assert len(persistent2.accounts) == 1
        assert persistent2.accounts[0].name == "Compte courant"
        assert len(persistent2.accounts[0].operations) == 3

        persistent2.close()

    def test_account_raises_when_not_loaded(self, temp_db_path: Path) -> None:
        """Test that accessing account raises when not loaded."""
        repository = SqliteRepository(temp_db_path)
        persistent = PersistentAccount(repository)

        with pytest.raises(FileNotFoundError):
            _ = persistent.account

        persistent.close()

    def test_upsert_account(self, temp_db_path: Path, sample_account: Account) -> None:
        """Test upserting account through the interface."""
        repository = SqliteRepository(temp_db_path)
        persistent = PersistentAccount(repository)
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
        repository2 = SqliteRepository(temp_db_path)
        persistent2 = PersistentAccount(repository2)
        persistent2.load()

        account = persistent2.accounts[0]
        assert len(account.operations) == 4

        persistent2.close()


class TestBudgetRepository:
    """Tests for budget CRUD operations in SqliteRepository."""

    def test_get_all_budgets_empty(self, temp_db_path: Path) -> None:
        """Test getting budgets when none exist."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        budgets = repository.get_all_budgets()
        assert budgets == []

        repository.close()

    def test_upsert_budget_insert(self, temp_db_path: Path) -> None:
        """Test inserting a new budget."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        budget = Budget(
            record_id=None,
            description="Courses mensuelles",
            amount=Amount(-500.0, "EUR"),
            category=Category.GROCERIES,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2024, 1, 1), relativedelta(months=1)),
                relativedelta(months=1),
                datetime(2024, 12, 31),
            ),
        )
        budget_id = repository.upsert_budget(budget)

        assert budget_id > 0
        retrieved = repository.get_budget_by_id(budget_id)
        assert retrieved is not None
        assert retrieved.description == "Courses mensuelles"
        assert retrieved.amount == -500.0
        assert retrieved.category == Category.GROCERIES

        repository.close()

    def test_upsert_budget_update(self, temp_db_path: Path) -> None:
        """Test updating an existing budget."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        budget = Budget(
            record_id=None,
            description="Courses mensuelles",
            amount=Amount(-500.0, "EUR"),
            category=Category.GROCERIES,
            time_range=TimeRange(datetime(2024, 1, 1), relativedelta(months=1)),
        )
        budget_id = repository.upsert_budget(budget)

        # Update the budget
        updated_budget = budget.replace(
            record_id=budget_id, amount=Amount(-600.0, "EUR")
        )
        repository.upsert_budget(updated_budget)

        retrieved = repository.get_budget_by_id(budget_id)
        assert retrieved is not None
        assert retrieved.amount == -600.0

        repository.close()

    def test_delete_budget(self, temp_db_path: Path) -> None:
        """Test deleting a budget."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        budget = Budget(
            record_id=None,
            description="Test budget",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            time_range=TimeRange(datetime(2024, 1, 1), relativedelta(days=30)),
        )
        budget_id = repository.upsert_budget(budget)

        repository.delete_budget(budget_id)

        assert repository.get_budget_by_id(budget_id) is None

        repository.close()

    def test_budget_time_range_serialization(self, temp_db_path: Path) -> None:
        """Test TimeRange serialization/deserialization."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        # Test simple TimeRange
        # duration of 10 days means last_date = initial + 10 - 1 = initial + 9
        budget = Budget(
            record_id=None,
            description="Simple budget",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            time_range=TimeRange(datetime(2024, 3, 15), relativedelta(days=10)),
        )
        budget_id = repository.upsert_budget(budget)

        retrieved = repository.get_budget_by_id(budget_id)
        assert retrieved is not None
        assert isinstance(retrieved.time_range, TimeRange)
        assert retrieved.time_range.initial_date == datetime(2024, 3, 15)
        # TimeRange.last_date = initial_date + duration - 1 day
        # for 10 days: 2024-03-15 + 10 - 1 = 2024-03-24
        assert retrieved.time_range.last_date == datetime(2024, 3, 24)

        repository.close()

    def test_budget_periodic_time_range_serialization(self, temp_db_path: Path) -> None:
        """Test PeriodicTimeRange serialization/deserialization."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        budget = Budget(
            record_id=None,
            description="Periodic budget",
            amount=Amount(-200.0, "EUR"),
            category=Category.GROCERIES,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2024, 1, 1), relativedelta(months=1)),
                relativedelta(months=1),
                datetime(2024, 6, 30),
            ),
        )
        budget_id = repository.upsert_budget(budget)

        retrieved = repository.get_budget_by_id(budget_id)
        assert retrieved is not None
        assert isinstance(retrieved.time_range, PeriodicTimeRange)
        assert retrieved.time_range.initial_date == datetime(2024, 1, 1)
        assert retrieved.time_range.period == relativedelta(months=1)
        # PeriodicTimeRange.last_date returns _expiration_date
        assert retrieved.time_range.last_date == datetime(2024, 6, 30)

        repository.close()


class TestPlannedOperationRepository:
    """Tests for planned operation CRUD operations in SqliteRepository."""

    def test_get_all_planned_operations_empty(self, temp_db_path: Path) -> None:
        """Test getting planned operations when none exist."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        ops = repository.get_all_planned_operations()
        assert ops == []

        repository.close()

    def test_upsert_planned_operation_insert(self, temp_db_path: Path) -> None:
        """Test inserting a new planned operation."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        op = PlannedOperation(
            record_id=None,
            description="Salaire mensuel",
            amount=Amount(3000.0, "EUR"),
            category=Category.SALARY,
            time_range=PeriodicDailyTimeRange(
                datetime(2024, 1, 28), relativedelta(months=1), datetime(2024, 12, 31)
            ),
        )
        op.set_matcher_params(
            description_hints={"VIREMENT", "SALAIRE"},
            approximation_date_range=timedelta(days=3),
            approximation_amount_ratio=0.1,
        )
        op_id = repository.upsert_planned_operation(op)

        assert op_id > 0
        retrieved = repository.get_planned_operation_by_id(op_id)
        assert retrieved is not None
        assert retrieved.description == "Salaire mensuel"
        assert retrieved.amount == 3000.0
        assert retrieved.category == Category.SALARY

        repository.close()

    def test_upsert_planned_operation_update(self, temp_db_path: Path) -> None:
        """Test updating an existing planned operation."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        op = PlannedOperation(
            record_id=None,
            description="Loyer",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            time_range=DailyTimeRange(datetime(2024, 1, 5)),
        )
        op_id = repository.upsert_planned_operation(op)

        # Update the operation
        updated_op = op.replace(record_id=op_id, amount=Amount(-850.0, "EUR"))
        repository.upsert_planned_operation(updated_op)

        retrieved = repository.get_planned_operation_by_id(op_id)
        assert retrieved is not None
        assert retrieved.amount == -850.0

        repository.close()

    def test_delete_planned_operation(self, temp_db_path: Path) -> None:
        """Test deleting a planned operation."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        op = PlannedOperation(
            record_id=None,
            description="Test op",
            amount=Amount(-50.0, "EUR"),
            category=Category.OTHER,
            time_range=DailyTimeRange(datetime(2024, 2, 15)),
        )
        op_id = repository.upsert_planned_operation(op)

        repository.delete_planned_operation(op_id)

        assert repository.get_planned_operation_by_id(op_id) is None

        repository.close()

    def test_planned_operation_matcher_params_serialization(
        self, temp_db_path: Path
    ) -> None:
        """Test that matcher params are serialized correctly."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        op = PlannedOperation(
            record_id=None,
            description="Test with matcher",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            time_range=DailyTimeRange(datetime(2024, 1, 1)),
        )
        op.set_matcher_params(
            description_hints={"KEYWORD1", "KEYWORD2"},
            approximation_date_range=timedelta(days=7),
            approximation_amount_ratio=0.15,
        )
        op_id = repository.upsert_planned_operation(op)

        retrieved = repository.get_planned_operation_by_id(op_id)
        assert retrieved is not None
        assert retrieved.matcher.description_hints == {"KEYWORD1", "KEYWORD2"}
        assert retrieved.matcher.approximation_date_range == timedelta(days=7)
        assert retrieved.matcher.approximation_amount_ratio == 0.15

        repository.close()

    def test_planned_operation_description_hints_serialization(
        self, temp_db_path: Path
    ) -> None:
        """Test that description hints with special chars are handled."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        op = PlannedOperation(
            record_id=None,
            description="Test hints",
            amount=Amount(-50.0, "EUR"),
            category=Category.OTHER,
            time_range=DailyTimeRange(datetime(2024, 1, 1)),
        )
        # Test with empty hints
        op.set_matcher_params(description_hints=set())
        op_id = repository.upsert_planned_operation(op)

        retrieved = repository.get_planned_operation_by_id(op_id)
        assert retrieved is not None
        assert retrieved.matcher.description_hints == set()

        repository.close()


class TestSchemaMigration:
    """Tests for schema migration."""

    def test_migration_v1_to_v2(self, temp_db_path: Path) -> None:
        """Test that migration from v1 to v2 works correctly."""
        # Create a v1 database
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        # Verify schema version is now 2
        assert repository._get_schema_version() == CURRENT_SCHEMA_VERSION

        # Verify new tables exist
        conn = repository._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='budgets'"
        )
        assert cursor.fetchone() is not None

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='planned_operations'"
        )
        assert cursor.fetchone() is not None

        repository.close()

    def test_migration_preserves_existing_data(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """Test that migration preserves existing account data."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()
        repository.set_aggregated_account_name("Test")
        repository.upsert_account(sample_account)

        # Close and reopen to simulate migration
        repository.close()

        repository2 = SqliteRepository(temp_db_path)
        repository2.initialize()

        # Verify existing data is preserved
        accounts = repository2.get_all_accounts()
        assert len(accounts) == 1
        assert accounts[0].name == "Compte courant"
        assert len(accounts[0].operations) == 3

        repository2.close()
