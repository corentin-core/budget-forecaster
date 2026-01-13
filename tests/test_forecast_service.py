"""Tests for the ForecastService."""

# pylint: disable=redefined-outer-name,import-outside-toplevel

from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from budget_forecaster.account.account import Account
from budget_forecaster.services.forecast_service import (
    CategoryBudget,
    ForecastService,
    MonthlySummary,
)


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
def temp_forecast_files(tmp_path: Path) -> tuple[Path, Path]:
    """Create temporary forecast files."""
    planned_ops = tmp_path / "planned_operations.csv"
    budgets = tmp_path / "budgets.csv"

    # Create minimal valid CSV files
    planned_ops.write_text(
        "description,amount,category,start_date,end_date,periodicity\n"
        "Test Op,100,Courses,2025-01-01,,monthly\n"
    )
    budgets.write_text(
        "category,amount,start_date,end_date,periodicity\n"
        "Courses,-500,2025-01-01,,monthly\n"
    )

    return planned_ops, budgets


@pytest.fixture
def service(
    mock_account: Account, temp_forecast_files: tuple[Path, Path]
) -> ForecastService:
    """Create a ForecastService with mock data."""
    planned_ops, budgets = temp_forecast_files
    return ForecastService(
        account=mock_account,
        planned_operations_path=planned_ops,
        budgets_path=budgets,
    )


class TestForecastServiceInit:
    """Tests for ForecastService initialization."""

    def test_planned_operations_path_property(
        self, service: ForecastService, temp_forecast_files: tuple[Path, Path]
    ) -> None:
        """planned_operations_path returns the correct path."""
        planned_ops, _ = temp_forecast_files
        assert service.planned_operations_path == planned_ops

    def test_budgets_path_property(
        self, service: ForecastService, temp_forecast_files: tuple[Path, Path]
    ) -> None:
        """budgets_path returns the correct path."""
        _, budgets = temp_forecast_files
        assert service.budgets_path == budgets

    def test_report_initially_none(self, service: ForecastService) -> None:
        """report is None before computation."""
        assert service.report is None


class TestHasForecastFiles:
    """Tests for has_forecast_files property."""

    def test_returns_true_when_both_exist(self, service: ForecastService) -> None:
        """has_forecast_files returns True when both files exist."""
        assert service.has_forecast_files is True

    def test_returns_false_when_planned_ops_missing(
        self, mock_account: Account, tmp_path: Path
    ) -> None:
        """has_forecast_files returns False when planned_operations missing."""
        budgets = tmp_path / "budgets.csv"
        budgets.write_text("header\ndata\n")

        service = ForecastService(
            account=mock_account,
            planned_operations_path=tmp_path / "nonexistent.csv",
            budgets_path=budgets,
        )
        assert service.has_forecast_files is False

    def test_returns_false_when_budgets_missing(
        self, mock_account: Account, tmp_path: Path
    ) -> None:
        """has_forecast_files returns False when budgets missing."""
        planned_ops = tmp_path / "planned_operations.csv"
        planned_ops.write_text("header\ndata\n")

        service = ForecastService(
            account=mock_account,
            planned_operations_path=planned_ops,
            budgets_path=tmp_path / "nonexistent.csv",
        )
        assert service.has_forecast_files is False

    def test_returns_false_when_both_missing(
        self, mock_account: Account, tmp_path: Path
    ) -> None:
        """has_forecast_files returns False when both files missing."""
        service = ForecastService(
            account=mock_account,
            planned_operations_path=tmp_path / "nonexistent1.csv",
            budgets_path=tmp_path / "nonexistent2.csv",
        )
        assert service.has_forecast_files is False


class TestLoadForecast:
    """Tests for load_forecast method."""

    def test_raises_when_files_missing(
        self, mock_account: Account, tmp_path: Path
    ) -> None:
        """load_forecast raises FileNotFoundError when files are missing."""
        service = ForecastService(
            account=mock_account,
            planned_operations_path=tmp_path / "missing1.csv",
            budgets_path=tmp_path / "missing2.csv",
        )

        with pytest.raises(FileNotFoundError) as exc_info:
            service.load_forecast()

        assert "Forecast files not found" in str(exc_info.value)

    def test_raises_with_specific_missing_file(
        self, mock_account: Account, tmp_path: Path
    ) -> None:
        """load_forecast error message includes missing file paths."""
        missing_planned = tmp_path / "missing_planned.csv"
        budgets = tmp_path / "budgets.csv"
        budgets.write_text("header\n")

        service = ForecastService(
            account=mock_account,
            planned_operations_path=missing_planned,
            budgets_path=budgets,
        )

        with pytest.raises(FileNotFoundError) as exc_info:
            service.load_forecast()

        assert "missing_planned.csv" in str(exc_info.value)


class TestComputeReport:
    """Tests for compute_report method."""

    @patch("budget_forecaster.services.forecast_service.AccountAnalyzer")
    @patch("budget_forecaster.services.forecast_service.ForecastReader")
    def test_uses_default_dates(
        self,
        mock_reader_class: MagicMock,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """compute_report uses default date range when not specified."""
        # Setup mocks
        mock_reader = MagicMock()
        mock_reader.read_planned_operations.return_value = []
        mock_reader.read_budgets.return_value = []
        mock_reader_class.return_value = mock_reader

        mock_report = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.compute_report.return_value = mock_report
        mock_analyzer_class.return_value = mock_analyzer

        result = service.compute_report()

        assert result == mock_report
        mock_analyzer.compute_report.assert_called_once()

    @patch("budget_forecaster.services.forecast_service.AccountAnalyzer")
    @patch("budget_forecaster.services.forecast_service.ForecastReader")
    def test_uses_custom_dates(
        self,
        mock_reader_class: MagicMock,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """compute_report uses provided date range."""
        # Setup mocks
        mock_reader = MagicMock()
        mock_reader.read_planned_operations.return_value = []
        mock_reader.read_budgets.return_value = []
        mock_reader_class.return_value = mock_reader

        mock_analyzer = MagicMock()
        mock_analyzer_class.return_value = mock_analyzer

        start = date(2025, 1, 1)
        end = date(2025, 12, 31)
        service.compute_report(start_date=start, end_date=end)

        # Check the analyzer was called with correct dates
        call_args = mock_analyzer.compute_report.call_args
        assert call_args[0][0].date() == start
        assert call_args[0][1].date() == end

    @patch("budget_forecaster.services.forecast_service.AccountAnalyzer")
    @patch("budget_forecaster.services.forecast_service.ForecastReader")
    def test_lazy_loads_forecast(
        self,
        mock_reader_class: MagicMock,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """compute_report loads forecast if not already loaded."""
        mock_reader = MagicMock()
        mock_reader.read_planned_operations.return_value = []
        mock_reader.read_budgets.return_value = []
        mock_reader_class.return_value = mock_reader

        mock_analyzer = MagicMock()
        mock_analyzer_class.return_value = mock_analyzer

        # First call should load forecast
        service.compute_report()
        assert mock_reader.read_planned_operations.called
        assert mock_reader.read_budgets.called


class TestGetBalanceEvolutionSummary:
    """Tests for get_balance_evolution_summary method."""

    def test_returns_empty_when_no_report(self, service: ForecastService) -> None:
        """get_balance_evolution_summary returns empty list when no report."""
        result = service.get_balance_evolution_summary()
        assert result == []

    @patch("budget_forecaster.services.forecast_service.AccountAnalyzer")
    @patch("budget_forecaster.services.forecast_service.ForecastReader")
    def test_returns_date_balance_tuples(
        self,
        mock_reader_class: MagicMock,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """get_balance_evolution_summary returns (date, balance) tuples."""
        import pandas as pd

        # Setup mock report with balance evolution data
        mock_reader = MagicMock()
        mock_reader.read_planned_operations.return_value = []
        mock_reader.read_budgets.return_value = []
        mock_reader_class.return_value = mock_reader

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
    @patch("budget_forecaster.services.forecast_service.ForecastReader")
    def test_returns_typed_monthly_summary(
        self,
        mock_reader_class: MagicMock,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """get_monthly_summary returns correctly typed MonthlySummary list."""
        import pandas as pd

        # Setup mocks
        mock_reader = MagicMock()
        mock_reader.read_planned_operations.return_value = []
        mock_reader.read_budgets.return_value = []
        mock_reader_class.return_value = mock_reader

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
    @patch("budget_forecaster.services.forecast_service.ForecastReader")
    def test_returns_category_stats_tuples(
        self,
        mock_reader_class: MagicMock,
        mock_analyzer_class: MagicMock,
        service: ForecastService,
    ) -> None:
        """get_category_statistics returns (category, total, avg) tuples."""
        import pandas as pd

        # Setup mocks
        mock_reader = MagicMock()
        mock_reader.read_planned_operations.return_value = []
        mock_reader.read_budgets.return_value = []
        mock_reader_class.return_value = mock_reader

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
