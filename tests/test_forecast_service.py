"""Tests for the ForecastService."""

# pylint: disable=redefined-outer-name,too-few-public-methods

from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account
from budget_forecaster.account.sqlite_repository import SqliteRepository
from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.services.forecast_service import (
    CategoryBudget,
    ForecastService,
    MonthlySummary,
)
from budget_forecaster.time_range import DailyTimeRange, TimeRange
from budget_forecaster.types import Category


@pytest.fixture
def mock_account() -> Account:
    """Create a mock account."""
    return Account(
        name="Test Account",
        balance=1000.0,
        currency="EUR",
        balance_date=datetime(2025, 1, 20),
        operations=(),
    )


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def repository(temp_db_path: Path) -> SqliteRepository:
    """Create an initialized repository."""
    repo = SqliteRepository(temp_db_path)
    repo.initialize()
    return repo


@pytest.fixture
def service(mock_account: Account, repository: SqliteRepository) -> ForecastService:
    """Create a ForecastService with mock data."""
    return ForecastService(
        account=mock_account,
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
        self, mock_account: Account, repository: SqliteRepository
    ) -> None:
        """load_forecast loads budgets from database."""
        # Add a budget to the database
        budget = Budget(
            record_id=-1,
            description="Test Budget",
            amount=Amount(-500.0, "EUR"),
            category=Category.GROCERIES,
            time_range=TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
        )
        repository.upsert_budget(budget)

        service = ForecastService(account=mock_account, repository=repository)
        forecast = service.load_forecast()

        assert len(forecast.budgets) == 1
        assert forecast.budgets[0].description == "Test Budget"

    def test_loads_planned_operations_from_db(
        self, mock_account: Account, repository: SqliteRepository
    ) -> None:
        """load_forecast loads planned operations from database."""
        # Add a planned operation to the database
        op = PlannedOperation(
            record_id=-1,
            description="Test Op",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            time_range=DailyTimeRange(datetime(2025, 1, 15)),
        )
        repository.upsert_planned_operation(op)

        service = ForecastService(account=mock_account, repository=repository)
        forecast = service.load_forecast()

        assert len(forecast.operations) == 1
        assert forecast.operations[0].description == "Test Op"


class TestReloadForecast:
    """Tests for reload_forecast method."""

    def test_invalidates_cached_forecast(
        self, mock_account: Account, repository: SqliteRepository
    ) -> None:
        """reload_forecast invalidates cached forecast."""
        service = ForecastService(account=mock_account, repository=repository)

        # Load initial forecast
        service.load_forecast()

        # Add a budget
        budget = Budget(
            record_id=-1,
            description="New Budget",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            time_range=TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
        )
        repository.upsert_budget(budget)

        # Reload should pick up the new budget
        forecast = service.reload_forecast()
        assert len(forecast.budgets) == 1


class TestBudgetCrud:
    """Tests for budget CRUD methods."""

    def test_add_budget(self, service: ForecastService) -> None:
        """add_budget adds a budget and returns its ID."""
        budget = Budget(
            record_id=-1,
            description="Test Budget",
            amount=Amount(-200.0, "EUR"),
            category=Category.GROCERIES,
            time_range=TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
        )

        budget_id = service.add_budget(budget)
        assert budget_id > 0

        # Verify it was added
        retrieved = service.get_budget_by_id(budget_id)
        assert retrieved is not None
        assert retrieved.description == "Test Budget"

    def test_update_budget(self, service: ForecastService) -> None:
        """update_budget updates an existing budget."""
        # Add a budget first
        budget = Budget(
            record_id=-1,
            description="Original",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            time_range=TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
        )
        budget_id = service.add_budget(budget)

        # Update it
        updated_budget = budget.replace(record_id=budget_id, description="Updated")
        service.update_budget(updated_budget)

        # Verify the update
        retrieved = service.get_budget_by_id(budget_id)
        assert retrieved is not None
        assert retrieved.description == "Updated"

    def test_update_budget_requires_valid_id(self, service: ForecastService) -> None:
        """update_budget raises error for invalid ID."""
        budget = Budget(
            record_id=-1,
            description="Test",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            time_range=TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
        )

        with pytest.raises(ValueError, match="valid ID"):
            service.update_budget(budget)

    def test_delete_budget(self, service: ForecastService) -> None:
        """delete_budget removes a budget."""
        budget = Budget(
            record_id=-1,
            description="To Delete",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            time_range=TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
        )
        budget_id = service.add_budget(budget)

        service.delete_budget(budget_id)

        assert service.get_budget_by_id(budget_id) is None

    def test_get_all_budgets(self, service: ForecastService) -> None:
        """get_all_budgets returns all budgets."""
        for i in range(3):
            budget = Budget(
                record_id=-1,
                description=f"Budget {i}",
                amount=Amount(-100.0 * (i + 1), "EUR"),
                category=Category.OTHER,
                time_range=TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
            )
            service.add_budget(budget)

        budgets = service.get_all_budgets()
        assert len(budgets) == 3


class TestPlannedOperationCrud:
    """Tests for planned operation CRUD methods."""

    def test_add_planned_operation(self, service: ForecastService) -> None:
        """add_planned_operation adds an operation and returns its ID."""
        op = PlannedOperation(
            record_id=-1,
            description="Test Op",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            time_range=DailyTimeRange(datetime(2025, 1, 15)),
        )

        op_id = service.add_planned_operation(op)
        assert op_id > 0

        retrieved = service.get_planned_operation_by_id(op_id)
        assert retrieved is not None
        assert retrieved.description == "Test Op"

    def test_update_planned_operation(self, service: ForecastService) -> None:
        """update_planned_operation updates an existing operation."""
        op = PlannedOperation(
            record_id=-1,
            description="Original",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            time_range=DailyTimeRange(datetime(2025, 1, 15)),
        )
        op_id = service.add_planned_operation(op)

        updated_op = op.replace(record_id=op_id, description="Updated")
        service.update_planned_operation(updated_op)

        retrieved = service.get_planned_operation_by_id(op_id)
        assert retrieved is not None
        assert retrieved.description == "Updated"

    def test_update_planned_operation_requires_valid_id(
        self, service: ForecastService
    ) -> None:
        """update_planned_operation raises error for invalid ID."""
        op = PlannedOperation(
            record_id=-1,
            description="Test",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            time_range=DailyTimeRange(datetime(2025, 1, 15)),
        )

        with pytest.raises(ValueError, match="valid ID"):
            service.update_planned_operation(op)

    def test_delete_planned_operation(self, service: ForecastService) -> None:
        """delete_planned_operation removes an operation."""
        op = PlannedOperation(
            record_id=-1,
            description="To Delete",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            time_range=DailyTimeRange(datetime(2025, 1, 15)),
        )
        op_id = service.add_planned_operation(op)

        service.delete_planned_operation(op_id)

        assert service.get_planned_operation_by_id(op_id) is None

    def test_get_all_planned_operations(self, service: ForecastService) -> None:
        """get_all_planned_operations returns all operations."""
        for i in range(3):
            op = PlannedOperation(
                record_id=-1,
                description=f"Op {i}",
                amount=Amount(100.0 * (i + 1), "EUR"),
                category=Category.SALARY,
                time_range=DailyTimeRange(datetime(2025, 1, 15 + i)),
            )
            service.add_planned_operation(op)

        ops = service.get_all_planned_operations()
        assert len(ops) == 3


class TestComputeReport:
    """Tests for compute_report method."""

    @patch("budget_forecaster.services.forecast_service.AccountAnalyzer")
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

    @patch("budget_forecaster.services.forecast_service.AccountAnalyzer")
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
        assert call_args[0][0].date() == start
        assert call_args[0][1].date() == end


class TestGetBalanceEvolutionSummary:
    """Tests for get_balance_evolution_summary method."""

    def test_returns_empty_when_no_report(self, service: ForecastService) -> None:
        """get_balance_evolution_summary returns empty list when no report."""
        result = service.get_balance_evolution_summary()
        assert result == []

    @patch("budget_forecaster.services.forecast_service.AccountAnalyzer")
    def test_returns_date_balance_tuples(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """get_balance_evolution_summary returns (date, balance) tuples."""
        import pandas as pd

        # Create a simple DataFrame for balance evolution
        dates = pd.date_range("2025-01-01", periods=10, freq="D")
        df = pd.DataFrame({"Solde": [1000 + i * 10 for i in range(10)]}, index=dates)

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

    @patch("budget_forecaster.services.forecast_service.AccountAnalyzer")
    def test_returns_typed_monthly_summary(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """get_monthly_summary returns correctly typed MonthlySummary list."""
        import pandas as pd

        # Create mock budget forecast DataFrame
        month = pd.Timestamp("2025-01-01")
        columns = pd.MultiIndex.from_tuples(
            [
                (month, "Réel"),
                (month, "Prévu"),
                (month, "Actualisé"),
            ]
        )
        df = pd.DataFrame(
            [[100, 150, 120], [200, 250, 220]],
            index=["Courses", "Loisirs"],
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
        # Check structure matches MonthlySummary
        for summary in result:
            assert "month" in summary
            assert "categories" in summary
            for cat_budget in summary["categories"].values():
                assert "real" in cat_budget
                assert "predicted" in cat_budget
                assert "actualized" in cat_budget


class TestGetCategoryStatistics:
    """Tests for get_category_statistics method."""

    def test_returns_empty_when_no_report(self, service: ForecastService) -> None:
        """get_category_statistics returns empty list when no report."""
        result = service.get_category_statistics()
        assert result == []

    @patch("budget_forecaster.services.forecast_service.AccountAnalyzer")
    def test_returns_category_stats_tuples(
        self,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """get_category_statistics returns (category, total, avg) tuples."""
        import pandas as pd

        # Create mock budget statistics DataFrame
        df = pd.DataFrame(
            {"Total": [1000, 500], "Moyenne mensuelle": [100, 50]},
            index=["Courses", "Loisirs"],
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
        assert result[0] == ("Courses", 1000.0, 100.0)
        assert result[1] == ("Loisirs", 500.0, 50.0)


class TestTypedDicts:
    """Tests for TypedDict definitions."""

    def test_category_budget_structure(self) -> None:
        """CategoryBudget has correct structure."""
        budget = CategoryBudget(real=100.0, predicted=150.0, actualized=120.0)
        assert budget["real"] == 100.0
        assert budget["predicted"] == 150.0
        assert budget["actualized"] == 120.0

    def test_monthly_summary_structure(self) -> None:
        """MonthlySummary has correct structure."""
        import pandas as pd

        month = pd.Timestamp("2025-01-01")
        categories = {
            "Courses": CategoryBudget(real=100.0, predicted=150.0, actualized=120.0)
        }
        summary = MonthlySummary(month=month, categories=categories)
        assert summary["month"] == month
        assert "Courses" in summary["categories"]
