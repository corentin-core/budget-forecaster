"""Module with tests for the PersistentAccount and SqliteRepository classes."""

import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
    SingleDay,
)
from budget_forecaster.core.types import Category
from budget_forecaster.domain.account.account import Account, AccountParameters
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.exceptions import (
    AccountNotFoundError,
    AccountNotLoadedError,
    BudgetNotFoundError,
    PlannedOperationNotFoundError,
)
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SCHEMA_V1,
    SCHEMA_V2,
    SCHEMA_V3,
    SqliteRepository,
)


@pytest.fixture(name="temp_db_path")
def temp_db_path_fixture() -> Path:
    """Fixture that provides a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return Path(f.name)


@pytest.fixture(name="sample_operations")
def sample_operations_fixture() -> tuple[HistoricOperation, ...]:
    """Fixture with sample operations."""
    return (
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
    )


@pytest.fixture(name="sample_account")
def sample_account_fixture(sample_operations: tuple[HistoricOperation, ...]) -> Account:
    """Fixture with a sample account."""
    return Account(
        name="Compte courant",
        balance=1550.0,
        currency="EUR",
        balance_date=date(2024, 1, 31),
        operations=sample_operations,
    )


class TestSqliteRepository:
    """Tests for the SqliteRepository class."""

    def test_initialize_creates_schema(self, temp_db_path: Path) -> None:
        """Test that initialize creates a fully functional database."""
        with SqliteRepository(temp_db_path) as repository:
            # All tables are operational on a fresh database
            assert not repository.get_all_accounts()
            assert not repository.get_all_budgets()
            assert not repository.get_all_planned_operations()
            assert not repository.get_all_links()

    def test_set_and_get_aggregated_account_name(self, temp_db_path: Path) -> None:
        """Test setting and getting aggregated account name."""
        with SqliteRepository(temp_db_path) as repository:
            assert repository.get_aggregated_account_name() is None

            repository.set_aggregated_account_name("Mes comptes")
            assert repository.get_aggregated_account_name() == "Mes comptes"

            # Update name
            repository.set_aggregated_account_name("Tous mes comptes")
            assert repository.get_aggregated_account_name() == "Tous mes comptes"

    def test_upsert_and_get_account(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """Test inserting and retrieving an account."""
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Test")

            repository.upsert_account(sample_account)

            retrieved = repository.get_account_by_name("Compte courant")
            assert retrieved.name == sample_account.name
            assert retrieved.balance == sample_account.balance
            assert retrieved.currency == sample_account.currency
            assert retrieved.balance_date == sample_account.balance_date
            assert len(retrieved.operations) == len(sample_account.operations)

    def test_upsert_account_updates_existing(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """Test that upsert updates an existing account."""
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Test")

            repository.upsert_account(sample_account)

            # Update with new balance
            updated_account = sample_account._replace(balance=2000.0)
            repository.upsert_account(updated_account)

            retrieved = repository.get_account_by_name("Compte courant")
            assert retrieved.balance == 2000.0

    def test_get_all_accounts(
        self, temp_db_path: Path, sample_operations: tuple[HistoricOperation, ...]
    ) -> None:
        """Test getting all accounts."""
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Test")

            account1 = Account(
                name="Compte 1",
                balance=1000.0,
                currency="EUR",
                balance_date=date(2024, 1, 31),
                operations=sample_operations[:2],
            )
            account2 = Account(
                name="Compte 2",
                balance=500.0,
                currency="EUR",
                balance_date=date(2024, 1, 31),
                operations=(sample_operations[2],),
            )

            repository.upsert_account(account1)
            repository.upsert_account(account2)

            accounts = repository.get_all_accounts()
            assert len(accounts) == 2
            names = {acc.name for acc in accounts}
            assert names == {"Compte 1", "Compte 2"}

    def test_update_operation(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """Test updating a single operation."""
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Test")
            repository.upsert_account(sample_account)

            # Update operation category
            updated_op = sample_account.operations[1].replace(category=Category.OTHER)
            repository.update_operation(updated_op)

            retrieved = repository.get_account_by_name("Compte courant")
            op = next(o for o in retrieved.operations if o.unique_id == 2)
            assert op.category == Category.OTHER

    def test_operation_exists(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """Test checking if an operation exists."""
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Test")
            repository.upsert_account(sample_account)

            assert repository.operation_exists(1) is True
            assert repository.operation_exists(999) is False


class TestPersistentAccount:
    """Tests for the PersistentAccount class."""

    def test_constructor_raises_when_no_account(self, temp_db_path: Path) -> None:
        """Test that constructor raises AccountNotLoadedError when no account exists."""
        with SqliteRepository(temp_db_path) as repository:
            with pytest.raises(AccountNotLoadedError):
                PersistentAccount(repository)

    def test_save_and_load(self, temp_db_path: Path, sample_account: Account) -> None:
        """Test saving and loading an aggregated account."""
        # Set up data through repository public API
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Mes comptes")
            repository.upsert_account(sample_account)

        # Load through PersistentAccount
        with SqliteRepository(temp_db_path) as repository2:
            persistent = PersistentAccount(repository2)

            assert persistent.account.name == "Mes comptes"
            assert len(persistent.accounts) == 1
            assert persistent.accounts[0].name == "Compte courant"
            assert len(persistent.accounts[0].operations) == 3

    def test_upsert_account(self, temp_db_path: Path, sample_account: Account) -> None:
        """Test upserting account through the interface."""
        # Set up initial data through repository
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Mes comptes")
            repository.upsert_account(sample_account)

        # Load, modify via upsert, save
        with SqliteRepository(temp_db_path) as repository:
            persistent = PersistentAccount(repository)

            new_operation = HistoricOperation(
                unique_id=4,
                description="Nouvelle opération",
                amount=Amount(-50.0, "EUR"),
                category=Category.OTHER,
                operation_date=date(2024, 2, 1),
            )
            new_account_params = AccountParameters(
                name="Compte courant",
                balance=1500.0,
                currency="EUR",
                balance_date=date(2024, 2, 1),
                operations=(new_operation,),
            )
            persistent.upsert_account(new_account_params)
            persistent.save()

        # Reload and verify
        with SqliteRepository(temp_db_path) as repository2:
            persistent2 = PersistentAccount(repository2)

            account = persistent2.accounts[0]
            assert len(account.operations) == 4


class TestBudgetRepository:
    """Tests for budget CRUD operations in SqliteRepository."""

    def test_get_all_budgets_empty(self, temp_db_path: Path) -> None:
        """Test getting budgets when none exist."""
        with SqliteRepository(temp_db_path) as repository:
            budgets = repository.get_all_budgets()
            assert not budgets

    def test_upsert_budget_insert(self, temp_db_path: Path) -> None:
        """Test inserting a new budget."""
        with SqliteRepository(temp_db_path) as repository:
            budget = Budget(
                record_id=None,
                description="Courses mensuelles",
                amount=Amount(-500.0, "EUR"),
                category=Category.GROCERIES,
                date_range=RecurringDateRange(
                    DateRange(date(2024, 1, 1), relativedelta(months=1)),
                    relativedelta(months=1),
                    date(2024, 12, 31),
                ),
            )
            budget_id = repository.upsert_budget(budget)

            assert budget_id > 0
            retrieved = repository.get_budget_by_id(budget_id)
            assert retrieved.description == "Courses mensuelles"
            assert retrieved.amount == -500.0
            assert retrieved.category == Category.GROCERIES

    def test_upsert_budget_update(self, temp_db_path: Path) -> None:
        """Test updating an existing budget."""
        with SqliteRepository(temp_db_path) as repository:
            budget = Budget(
                record_id=None,
                description="Courses mensuelles",
                amount=Amount(-500.0, "EUR"),
                category=Category.GROCERIES,
                date_range=DateRange(date(2024, 1, 1), relativedelta(months=1)),
            )
            budget_id = repository.upsert_budget(budget)

            # Update the budget
            updated_budget = budget.replace(
                record_id=budget_id, amount=Amount(-600.0, "EUR")
            )
            repository.upsert_budget(updated_budget)

            retrieved = repository.get_budget_by_id(budget_id)
            assert retrieved.amount == -600.0

    def test_delete_budget(self, temp_db_path: Path) -> None:
        """Test deleting a budget."""
        with SqliteRepository(temp_db_path) as repository:
            budget = Budget(
                record_id=None,
                description="Test budget",
                amount=Amount(-100.0, "EUR"),
                category=Category.OTHER,
                date_range=DateRange(date(2024, 1, 1), relativedelta(days=30)),
            )
            budget_id = repository.upsert_budget(budget)

            repository.delete_budget(budget_id)

            with pytest.raises(BudgetNotFoundError):
                repository.get_budget_by_id(budget_id)

    def test_budget_time_range_serialization(self, temp_db_path: Path) -> None:
        """Test TimeRange serialization/deserialization."""
        with SqliteRepository(temp_db_path) as repository:
            # Test simple TimeRange
            # duration of 10 days means last_date = initial + 10 - 1 = initial + 9
            budget = Budget(
                record_id=None,
                description="Simple budget",
                amount=Amount(-100.0, "EUR"),
                category=Category.OTHER,
                date_range=DateRange(date(2024, 3, 15), relativedelta(days=10)),
            )
            budget_id = repository.upsert_budget(budget)

            retrieved = repository.get_budget_by_id(budget_id)
            assert isinstance(retrieved.date_range, DateRange)
            assert retrieved.date_range.start_date == date(2024, 3, 15)
            # TimeRange.last_date = initial_date + duration - 1 day
            # for 10 days: 2024-03-15 + 10 - 1 = 2024-03-24
            assert retrieved.date_range.last_date == date(2024, 3, 24)

    def test_budget_periodic_time_range_serialization(self, temp_db_path: Path) -> None:
        """Test PeriodicTimeRange serialization/deserialization."""
        with SqliteRepository(temp_db_path) as repository:
            budget = Budget(
                record_id=None,
                description="Periodic budget",
                amount=Amount(-200.0, "EUR"),
                category=Category.GROCERIES,
                date_range=RecurringDateRange(
                    DateRange(date(2024, 1, 1), relativedelta(months=1)),
                    relativedelta(months=1),
                    date(2024, 6, 30),
                ),
            )
            budget_id = repository.upsert_budget(budget)

            retrieved = repository.get_budget_by_id(budget_id)
            assert isinstance(retrieved.date_range, RecurringDateRange)
            assert retrieved.date_range.start_date == date(2024, 1, 1)
            assert retrieved.date_range.period == relativedelta(months=1)
            # PeriodicTimeRange.last_date returns _expiration_date
            assert retrieved.date_range.last_date == date(2024, 6, 30)


class TestPlannedOperationRepository:
    """Tests for planned operation CRUD operations in SqliteRepository."""

    def test_get_all_planned_operations_empty(self, temp_db_path: Path) -> None:
        """Test getting planned operations when none exist."""
        with SqliteRepository(temp_db_path) as repository:
            ops = repository.get_all_planned_operations()
            assert not ops

    def test_upsert_planned_operation_insert(self, temp_db_path: Path) -> None:
        """Test inserting a new planned operation."""
        with SqliteRepository(temp_db_path) as repository:
            op = PlannedOperation(
                record_id=None,
                description="Salaire mensuel",
                amount=Amount(3000.0, "EUR"),
                category=Category.SALARY,
                date_range=RecurringDay(
                    date(2024, 1, 28),
                    relativedelta(months=1),
                    date(2024, 12, 31),
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
            assert retrieved.description == "Salaire mensuel"
            assert retrieved.amount == 3000.0
            assert retrieved.category == Category.SALARY

    def test_upsert_planned_operation_update(self, temp_db_path: Path) -> None:
        """Test updating an existing planned operation."""
        with SqliteRepository(temp_db_path) as repository:
            op = PlannedOperation(
                record_id=None,
                description="Loyer",
                amount=Amount(-800.0, "EUR"),
                category=Category.RENT,
                date_range=SingleDay(date(2024, 1, 5)),
            )
            op_id = repository.upsert_planned_operation(op)

            # Update the operation
            updated_op = op.replace(record_id=op_id, amount=Amount(-850.0, "EUR"))
            repository.upsert_planned_operation(updated_op)

            retrieved = repository.get_planned_operation_by_id(op_id)
            assert retrieved.amount == -850.0

    def test_delete_planned_operation(self, temp_db_path: Path) -> None:
        """Test deleting a planned operation."""
        with SqliteRepository(temp_db_path) as repository:
            op = PlannedOperation(
                record_id=None,
                description="Test op",
                amount=Amount(-50.0, "EUR"),
                category=Category.OTHER,
                date_range=SingleDay(date(2024, 2, 15)),
            )
            op_id = repository.upsert_planned_operation(op)

            repository.delete_planned_operation(op_id)

            with pytest.raises(PlannedOperationNotFoundError):
                repository.get_planned_operation_by_id(op_id)

    def test_planned_operation_matcher_params_serialization(
        self, temp_db_path: Path
    ) -> None:
        """Test that matcher params are serialized correctly."""
        with SqliteRepository(temp_db_path) as repository:
            op = PlannedOperation(
                record_id=None,
                description="Test with matcher",
                amount=Amount(-100.0, "EUR"),
                category=Category.OTHER,
                date_range=SingleDay(date(2024, 1, 1)),
            )
            op.set_matcher_params(
                description_hints={"KEYWORD1", "KEYWORD2"},
                approximation_date_range=timedelta(days=7),
                approximation_amount_ratio=0.15,
            )
            op_id = repository.upsert_planned_operation(op)

            retrieved = repository.get_planned_operation_by_id(op_id)
            assert retrieved.matcher.description_hints == {"KEYWORD1", "KEYWORD2"}
            assert retrieved.matcher.approximation_date_range == timedelta(days=7)
            assert retrieved.matcher.approximation_amount_ratio == 0.15

    def test_planned_operation_description_hints_serialization(
        self, temp_db_path: Path
    ) -> None:
        """Test that description hints with special chars are handled."""
        with SqliteRepository(temp_db_path) as repository:
            op = PlannedOperation(
                record_id=None,
                description="Test hints",
                amount=Amount(-50.0, "EUR"),
                category=Category.OTHER,
                date_range=SingleDay(date(2024, 1, 1)),
            )
            # Test with empty hints
            op.set_matcher_params(description_hints=set())
            op_id = repository.upsert_planned_operation(op)

            retrieved = repository.get_planned_operation_by_id(op_id)
            assert retrieved.matcher.description_hints == set()


class TestPersistentAccountOperations:
    """Tests for PersistentAccount reload, replace, and close operations."""

    def test_reload_refreshes_data(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """reload() refreshes the account data from the repository."""
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Mes comptes")
            repository.upsert_account(sample_account)
            persistent = PersistentAccount(repository)

            # Modify data directly through repository
            updated_op = sample_account.operations[0].replace(
                category=Category.OTHER,
            )
            repository.update_operation(updated_op)

            # Before reload, persistent still has old data
            ops_before = persistent.accounts[0].operations
            before = [o for o in ops_before if o.unique_id == 1]
            assert before[0].category == Category.SALARY

            persistent.reload()

            # After reload, data is refreshed
            ops = persistent.accounts[0].operations
            matching = [o for o in ops if o.unique_id == 1]
            assert matching[0].category == Category.OTHER

    def test_replace_account_updates_in_memory(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """replace_account updates the account in the aggregated account."""
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Mes comptes")
            repository.upsert_account(sample_account)
            persistent = PersistentAccount(repository)

            updated_account = sample_account._replace(balance=9999.0)
            persistent.replace_account(updated_account)

            assert persistent.accounts[0].balance == 9999.0

    def test_replace_operation_updates_in_memory(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """replace_operation updates the operation in the aggregated account."""
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Mes comptes")
            repository.upsert_account(sample_account)
            persistent = PersistentAccount(repository)

            new_op = sample_account.operations[1].replace(
                category=Category.ENTERTAINMENT,
            )
            persistent.replace_operation(new_op)

            ops = persistent.accounts[0].operations
            matching = [o for o in ops if o.unique_id == 2]
            assert matching[0].category == Category.ENTERTAINMENT


class TestSqliteRepositoryGaps:
    """Tests for SqliteRepository uncovered paths."""

    def test_get_account_by_name_raises_for_unknown(self, temp_db_path: Path) -> None:
        """get_account_by_name raises AccountNotFoundError when account doesn't exist."""
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Test")
            with pytest.raises(AccountNotFoundError):
                repository.get_account_by_name("NonExistent")

    def test_yearly_budget_serialization(self, temp_db_path: Path) -> None:
        """Budgets with yearly duration are serialized and deserialized correctly."""
        with SqliteRepository(temp_db_path) as repository:
            budget = Budget(
                record_id=None,
                description="Annual budget",
                amount=Amount(-5000.0, "EUR"),
                category=Category.OTHER,
                date_range=RecurringDateRange(
                    DateRange(date(2024, 1, 1), relativedelta(years=1)),
                    relativedelta(years=1),
                    date(2026, 12, 31),
                ),
            )
            budget_id = repository.upsert_budget(budget)

            retrieved = repository.get_budget_by_id(budget_id)
            assert retrieved == budget.replace(record_id=budget_id)

    def test_daily_planned_operation_serialization(self, temp_db_path: Path) -> None:
        """Planned operations with day-based duration round-trip correctly."""
        with SqliteRepository(temp_db_path) as repository:
            op = PlannedOperation(
                record_id=None,
                description="Daily op",
                amount=Amount(-10.0, "EUR"),
                category=Category.OTHER,
                date_range=RecurringDay(
                    date(2024, 1, 1),
                    relativedelta(days=7),
                    date(2024, 12, 31),
                ),
            )
            op_id = repository.upsert_planned_operation(op)

            retrieved = repository.get_planned_operation_by_id(op_id)
            assert retrieved == op.replace(record_id=op_id)


class TestSchemaMigration:
    """Tests for schema migration."""

    def test_fresh_database_supports_all_tables(self, temp_db_path: Path) -> None:
        """Test that a fresh database has all required tables operational."""
        with SqliteRepository(temp_db_path) as repository:
            # Budget and planned operation tables work (added in v2)
            assert not repository.get_all_budgets()
            assert not repository.get_all_planned_operations()

    def test_migration_preserves_existing_data(
        self, temp_db_path: Path, sample_account: Account
    ) -> None:
        """Test that migration preserves existing account data."""
        with SqliteRepository(temp_db_path) as repository:
            repository.set_aggregated_account_name("Test")
            repository.upsert_account(sample_account)

        # Reopen to simulate migration
        with SqliteRepository(temp_db_path) as repository2:
            # Verify existing data is preserved
            accounts = repository2.get_all_accounts()
            assert len(accounts) == 1
            assert accounts[0].name == "Compte courant"
            assert len(accounts[0].operations) == 3

    def test_migration_v3_to_v4_converts_datetime_to_date(
        self, temp_db_path: Path
    ) -> None:
        """Test that migration v4 converts datetime strings to date strings."""
        # Create a v3 database with datetime strings (old format)
        conn = sqlite3.connect(temp_db_path)
        conn.executescript(SCHEMA_V1)
        conn.executescript(SCHEMA_V2)
        conn.executescript(SCHEMA_V3)
        conn.execute("INSERT INTO schema_version (version) VALUES (3)")
        conn.execute("INSERT INTO aggregated_accounts (name) VALUES ('Test')")
        conn.execute(
            "INSERT INTO accounts (aggregated_account_id, name, balance, currency, "
            "balance_date) VALUES (1, 'Compte', 1000.0, 'EUR', '2026-01-15T00:00:00')"
        )
        conn.execute(
            "INSERT INTO operations (unique_id, account_id, description, category, "
            "date, amount, currency) "
            "VALUES (1, 1, 'Test op', 'Courses', '2026-01-28T00:00:00', -50.0, 'EUR')"
        )
        conn.execute(
            "INSERT INTO planned_operations (description, amount, currency, category, "
            "start_date, end_date) "
            "VALUES ('Loyer', -800.0, 'EUR', 'Logement', '2025-01-01T00:00:00', "
            "'2026-12-31T00:00:00')"
        )
        conn.execute(
            "INSERT INTO budgets (description, amount, currency, category, start_date, "
            "end_date) "
            "VALUES ('Courses', -400.0, 'EUR', 'Courses', '2025-01-01T00:00:00', "
            "'2026-12-31T00:00:00')"
        )
        conn.execute(
            "INSERT INTO operation_links (operation_unique_id, target_type, target_id, "
            "iteration_date, is_manual) "
            "VALUES (1, 'planned_operation', 1, '2026-01-01T00:00:00', 0)"
        )
        conn.commit()
        conn.close()

        # Open with SqliteRepository to trigger migration, then close
        with SqliteRepository(temp_db_path) as repository:
            # Verify data loads correctly through the public interface
            accounts = repository.get_all_accounts()
            assert len(accounts) == 1
            assert accounts[0].operations[0].operation_date == date(2026, 1, 28)

            links = repository.get_all_links()
            assert len(links) == 1
            assert links[0].iteration_date == date(2026, 1, 1)
