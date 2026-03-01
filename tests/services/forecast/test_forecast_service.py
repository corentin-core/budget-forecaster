"""Tests for the ForecastService."""

# pylint: disable=too-few-public-methods

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import DateRange, SingleDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.exceptions import (
    BudgetNotFoundError,
    PlannedOperationNotFoundError,
)
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.forecast.forecast_service import (
    CategoryBudget,
    ForecastService,
    MonthlySummary,
)
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)


class _AccountStub:
    """Mutable AccountInterface stub for unit tests."""

    def __init__(self, account: Account) -> None:
        self._account = account

    @property
    def account(self) -> Account:
        """Return the account."""
        return self._account

    @account.setter
    def account(self, value: Account) -> None:
        self._account = value


@pytest.fixture(name="mock_account")
def mock_account_fixture() -> Account:
    """Create a mock account."""
    return Account(
        name="Test Account",
        balance=1000.0,
        currency="EUR",
        balance_date=date(2025, 1, 20),
        operations=(),
    )


@pytest.fixture(name="account_provider")
def account_provider_fixture(mock_account: Account) -> _AccountStub:
    """Create an AccountInterface stub wrapping the mock account."""
    return _AccountStub(mock_account)


@pytest.fixture(name="temp_db_path")
def temp_db_path_fixture(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture(name="repository")
def repository_fixture(temp_db_path: Path) -> Iterator[RepositoryInterface]:
    """Create an initialized repository."""
    with SqliteRepository(temp_db_path) as repo:
        yield repo


@pytest.fixture(name="operation_link_service")
def operation_link_service_fixture(
    repository: RepositoryInterface,
) -> OperationLinkService:
    """Create an OperationLinkService for testing."""
    return OperationLinkService(repository)


@pytest.fixture(name="service")
def service_fixture(
    account_provider: _AccountStub,
    repository: RepositoryInterface,
) -> ForecastService:
    """Create a ForecastService with mock data."""
    return ForecastService(
        account_provider=account_provider,
        repository=repository,
    )


class TestForecastServiceInit:
    """Tests for ForecastService initialization."""

    def test_report_initially_none(self, service: ForecastService) -> None:
        """report is None before computation."""
        assert service.report is None


class TestLoadForecast:
    """Tests for load_forecast method."""

    def test_loads_empty_forecast(self, service: ForecastService) -> None:
        """load_forecast works with empty database."""
        forecast = service.load_forecast()
        assert len(forecast.operations) == 0
        assert len(forecast.budgets) == 0

    def test_loads_budgets_from_db(
        self,
        mock_account: Account,
        repository: RepositoryInterface,
    ) -> None:
        """load_forecast loads budgets from database."""
        # Add a budget to the database
        budget = Budget(
            record_id=None,
            description="Test Budget",
            amount=Amount(-500.0, "EUR"),
            category=Category.GROCERIES,
            date_range=DateRange(date(2025, 1, 1), relativedelta(months=1)),
        )
        repository.upsert_budget(budget)

        service = ForecastService(
            account_provider=_AccountStub(mock_account),
            repository=repository,
        )
        forecast = service.load_forecast()

        assert len(forecast.budgets) == 1
        assert forecast.budgets[0].description == "Test Budget"

    def test_loads_planned_operations_from_db(
        self,
        mock_account: Account,
        repository: RepositoryInterface,
    ) -> None:
        """load_forecast loads planned operations from database."""
        # Add a planned operation to the database
        op = PlannedOperation(
            record_id=None,
            description="Test Op",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        repository.upsert_planned_operation(op)

        service = ForecastService(
            account_provider=_AccountStub(mock_account),
            repository=repository,
        )
        forecast = service.load_forecast()

        assert len(forecast.operations) == 1
        assert forecast.operations[0].description == "Test Op"


class TestReloadForecast:
    """Tests for reload_forecast method."""

    def test_invalidates_cached_forecast(
        self,
        mock_account: Account,
        repository: RepositoryInterface,
    ) -> None:
        """reload_forecast invalidates cached forecast."""
        service = ForecastService(
            account_provider=_AccountStub(mock_account),
            repository=repository,
        )

        # Load initial forecast
        service.load_forecast()

        # Add a budget
        budget = Budget(
            record_id=None,
            description="New Budget",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            date_range=DateRange(date(2025, 1, 1), relativedelta(months=1)),
        )
        repository.upsert_budget(budget)

        # Reload should pick up the new budget
        forecast = service.reload_forecast()
        assert len(forecast.budgets) == 1


class TestBudgetCrud:
    """Tests for budget CRUD methods."""

    def test_add_budget(self, service: ForecastService) -> None:
        """add_budget adds a budget and returns the created budget."""
        budget = Budget(
            record_id=None,
            description="Test Budget",
            amount=Amount(-200.0, "EUR"),
            category=Category.GROCERIES,
            date_range=DateRange(date(2025, 1, 1), relativedelta(months=1)),
        )

        created_budget = service.add_budget(budget)
        assert created_budget.id is not None
        assert created_budget.id > 0

        # Verify it was added
        retrieved = service.get_budget_by_id(created_budget.id)
        assert retrieved.description == "Test Budget"

    def test_update_budget(self, service: ForecastService) -> None:
        """update_budget updates an existing budget."""
        # Add a budget first
        budget = Budget(
            record_id=None,
            description="Original",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            date_range=DateRange(date(2025, 1, 1), relativedelta(months=1)),
        )
        created_budget = service.add_budget(budget)

        # Update it
        updated_budget = created_budget.replace(description="Updated")
        service.update_budget(updated_budget)

        # Verify the update
        assert created_budget.id is not None
        retrieved = service.get_budget_by_id(created_budget.id)
        assert retrieved.description == "Updated"

    def test_update_budget_requires_valid_id(self, service: ForecastService) -> None:
        """update_budget raises error for invalid ID."""
        budget = Budget(
            record_id=None,
            description="Test",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            date_range=DateRange(date(2025, 1, 1), relativedelta(months=1)),
        )

        with pytest.raises(ValueError, match="valid ID"):
            service.update_budget(budget)

    def test_delete_budget(self, service: ForecastService) -> None:
        """delete_budget removes a budget."""
        budget = Budget(
            record_id=None,
            description="To Delete",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            date_range=DateRange(date(2025, 1, 1), relativedelta(months=1)),
        )
        created_budget = service.add_budget(budget)
        assert created_budget.id is not None

        service.delete_budget(created_budget.id)

        with pytest.raises(BudgetNotFoundError):
            service.get_budget_by_id(created_budget.id)

    def test_get_all_budgets(self, service: ForecastService) -> None:
        """get_all_budgets returns all budgets."""
        for i in range(3):
            budget = Budget(
                record_id=None,
                description=f"Budget {i}",
                amount=Amount(-100.0 * (i + 1), "EUR"),
                category=Category.OTHER,
                date_range=DateRange(date(2025, 1, 1), relativedelta(months=1)),
            )
            service.add_budget(budget)

        budgets = service.get_all_budgets()
        assert len(budgets) == 3


class TestPlannedOperationCrud:
    """Tests for planned operation CRUD methods."""

    def test_add_planned_operation(self, service: ForecastService) -> None:
        """add_planned_operation adds an operation and returns the created operation."""
        op = PlannedOperation(
            record_id=None,
            description="Test Op",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            date_range=SingleDay(date(2025, 1, 15)),
        )

        created_op = service.add_planned_operation(op)
        assert created_op.id is not None
        assert created_op.id > 0

        retrieved = service.get_planned_operation_by_id(created_op.id)
        assert retrieved.description == "Test Op"

    def test_update_planned_operation(self, service: ForecastService) -> None:
        """update_planned_operation updates an existing operation."""
        op = PlannedOperation(
            record_id=None,
            description="Original",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        created_op = service.add_planned_operation(op)

        updated_op = created_op.replace(description="Updated")
        service.update_planned_operation(updated_op)

        assert created_op.id is not None
        retrieved = service.get_planned_operation_by_id(created_op.id)
        assert retrieved.description == "Updated"

    def test_update_planned_operation_requires_valid_id(
        self, service: ForecastService
    ) -> None:
        """update_planned_operation raises error for invalid ID."""
        op = PlannedOperation(
            record_id=None,
            description="Test",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            date_range=SingleDay(date(2025, 1, 15)),
        )

        with pytest.raises(ValueError, match="valid ID"):
            service.update_planned_operation(op)

    def test_delete_planned_operation(self, service: ForecastService) -> None:
        """delete_planned_operation removes an operation."""
        op = PlannedOperation(
            record_id=None,
            description="To Delete",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        created_op = service.add_planned_operation(op)
        assert created_op.id is not None

        service.delete_planned_operation(created_op.id)

        with pytest.raises(PlannedOperationNotFoundError):
            service.get_planned_operation_by_id(created_op.id)

    def test_get_all_planned_operations(self, service: ForecastService) -> None:
        """get_all_planned_operations returns all operations."""
        for i in range(3):
            op = PlannedOperation(
                record_id=None,
                description=f"Op {i}",
                amount=Amount(100.0 * (i + 1), "EUR"),
                category=Category.SALARY,
                date_range=SingleDay(date(2025, 1, 15 + i)),
            )
            service.add_planned_operation(op)

        ops = service.get_all_planned_operations()
        assert len(ops) == 3


class TestComputeReport:
    """Tests for compute_report method."""

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_uses_default_dates(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """compute_report uses default date range when not specified."""
        mock_report = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.compute_report.return_value = mock_report
        mock_analyzer_class.return_value = mock_analyzer

        result = service.compute_report()

        assert result == mock_report
        mock_analyzer.compute_report.assert_called_once()

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_uses_custom_dates(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """compute_report uses provided date range."""
        mock_analyzer = MagicMock()
        mock_analyzer_class.return_value = mock_analyzer

        start = date(2025, 1, 1)
        end = date(2025, 12, 31)
        service.compute_report(start_date=start, end_date=end)

        # Check the analyzer was called with correct dates
        call_args = mock_analyzer.compute_report.call_args
        assert call_args[0][0] == start
        assert call_args[0][1] == end

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_uses_current_account_not_stale_snapshot(
        self,
        mock_analyzer_class: MagicMock,
        account_provider: _AccountStub,
        repository: RepositoryInterface,
    ) -> None:
        """Regression: compute_report reads the current account, not a stale snapshot.

        Previously ForecastService stored an Account snapshot at init time.
        After categorizing operations, the snapshot was stale and the forecast
        showed outdated categories (e.g. uncategorized for already-categorized ops).
        """
        mock_analyzer = MagicMock()
        mock_analyzer_class.return_value = mock_analyzer

        service = ForecastService(
            account_provider=account_provider,
            repository=repository,
        )

        # First compute — account has no operations
        service.compute_report()
        first_account = mock_analyzer_class.call_args[0][0]
        assert first_account.operations == ()

        # Simulate categorization: update the account with a new operation
        operation = HistoricOperation(
            unique_id=1,
            description="Supermarket",
            amount=Amount(-50.0, "EUR"),
            category=Category.GROCERIES,
            operation_date=date(2025, 1, 15),
        )
        account_provider.account = account_provider.account._replace(
            operations=(operation,),
        )

        # Second compute — should see the updated account
        service.compute_report()
        second_account = mock_analyzer_class.call_args[0][0]
        assert second_account.operations == (operation,)


class TestGetBalanceEvolutionSummary:
    """Tests for get_balance_evolution_summary method."""

    def test_returns_empty_when_no_report(self, service: ForecastService) -> None:
        """get_balance_evolution_summary returns empty list when no report."""
        result = service.get_balance_evolution_summary()
        assert result == []

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_returns_date_balance_tuples(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """get_balance_evolution_summary returns (date, balance) tuples."""

        # Create a simple DataFrame for balance evolution
        dates = pd.date_range("2025-01-01", periods=10, freq="D")
        df = pd.DataFrame({"Balance": [1000 + i * 10 for i in range(10)]}, index=dates)

        mock_report = MagicMock()
        mock_report.balance_evolution_per_day = df

        mock_analyzer = MagicMock()
        mock_analyzer.compute_report.return_value = mock_report
        mock_analyzer_class.return_value = mock_analyzer

        service.compute_report()
        result = service.get_balance_evolution_summary()

        assert len(result) > 0
        assert all(isinstance(item, tuple) for item in result)
        assert all(isinstance(item[0], date) for item in result)
        assert all(isinstance(item[1], float) for item in result)


class TestGetMonthlySummary:
    """Tests for get_monthly_summary method."""

    def test_returns_empty_when_no_report(self, service: ForecastService) -> None:
        """get_monthly_summary returns empty list when no report."""
        result = service.get_monthly_summary()
        assert result == []

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_returns_typed_monthly_summary(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """get_monthly_summary returns correctly typed MonthlySummary list."""

        # Create mock budget forecast DataFrame with enriched columns
        month = pd.Timestamp("2025-01-01")
        columns = pd.MultiIndex.from_tuples(
            [
                (month, "TotalPlanned"),
                (month, "Actual"),
                (month, "Projected"),
            ]
        )
        df = pd.DataFrame(
            [[-150, -100, -120], [-250, -200, -220]],
            index=["groceries", "entertainment"],
            columns=columns,
        )

        mock_report = MagicMock()
        mock_report.budget_forecast = df

        mock_analyzer = MagicMock()
        mock_analyzer.compute_report.return_value = mock_report
        mock_analyzer_class.return_value = mock_analyzer

        service.compute_report()
        result = service.get_monthly_summary()

        assert len(result) > 0
        for summary in result:
            assert "month" in summary
            assert "categories" in summary
            for cat_budget in summary["categories"].values():
                assert "planned" in cat_budget
                assert "actual" in cat_budget
                assert "projected" in cat_budget
                assert "is_income" in cat_budget


class TestGetCategoryStatistics:
    """Tests for get_category_statistics method."""

    def test_returns_empty_when_no_report(self, service: ForecastService) -> None:
        """get_category_statistics returns empty list when no report."""
        result = service.get_category_statistics()
        assert result == []

    @patch("budget_forecaster.services.forecast.forecast_service.AccountAnalyzer")
    def test_returns_category_stats_tuples(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """get_category_statistics returns (category, total, avg) tuples."""

        # Create mock budget statistics DataFrame
        df = pd.DataFrame(
            {"Total": [1000, 500], "Monthly average": [100, 50]},
            index=["groceries", "entertainment"],
        )

        mock_report = MagicMock()
        mock_report.budget_statistics = df

        mock_analyzer = MagicMock()
        mock_analyzer.compute_report.return_value = mock_report
        mock_analyzer_class.return_value = mock_analyzer

        service.compute_report()
        result = service.get_category_statistics()

        assert len(result) == 2
        assert all(isinstance(item, tuple) for item in result)
        assert all(len(item) == 3 for item in result)
        # (category_name, total, monthly_avg)
        assert result[0] == ("groceries", 1000.0, 100.0)
        assert result[1] == ("entertainment", 500.0, 50.0)


class TestTypedDicts:
    """Tests for TypedDict definitions."""

    def test_category_budget_structure(self) -> None:
        """CategoryBudget has correct structure."""
        budget = CategoryBudget(
            planned=150.0, actual=100.0, projected=120.0, is_income=False
        )
        assert budget["planned"] == 150.0
        assert budget["actual"] == 100.0
        assert budget["projected"] == 120.0
        assert budget["is_income"] is False

    def test_monthly_summary_structure(self) -> None:
        """MonthlySummary has correct structure."""

        month = pd.Timestamp("2025-01-01")
        categories = {
            "groceries": CategoryBudget(
                planned=150.0, actual=100.0, projected=120.0, is_income=False
            )
        }
        summary = MonthlySummary(month=month, categories=categories)
        assert summary["month"] == month
        assert "groceries" in summary["categories"]
