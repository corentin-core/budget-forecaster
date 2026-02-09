"""Module to test the AccountAnalyzer class."""
# pylint: disable=too-few-public-methods
from datetime import date

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
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.account.account_analyzer import AccountAnalyzer


@pytest.fixture
def account() -> Account:
    """Return an account with two historic operations."""
    operations = (
        HistoricOperation(
            unique_id=1,
            description="Operation 1",
            amount=Amount(-50.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 1, 15),
        ),
        HistoricOperation(
            unique_id=2,
            description="Operation 2",
            amount=Amount(-30.0),
            category=Category.GROCERIES,
            operation_date=date(2023, 2, 15),
        ),
    )
    return Account(
        name="Test Account",
        balance=1000.0,
        currency="EUR",
        balance_date=date(2023, 3, 1),
        operations=operations,
    )


@pytest.fixture
def planned_operations() -> tuple[PlannedOperation, ...]:
    """Return a tuple of planned operations."""
    return (
        PlannedOperation(
            record_id=1,
            description="Isolated Planned Operation",
            amount=Amount(-50.0),
            category=Category.OTHER,
            date_range=SingleDay(date(2023, 3, 15)),
        ),
        PlannedOperation(
            record_id=2,
            description="Recurring Planned Operation",
            amount=Amount(-20.0),
            category=Category.GROCERIES,
            date_range=RecurringDay(
                date(2023, 3, 1),
                expiration_date=date(2023, 6, 1),
                period=relativedelta(months=1),
            ),
        ),
    )


@pytest.fixture
def budgets() -> tuple[Budget, ...]:
    """Return a tuple of budgets."""
    return (
        Budget(
            record_id=1,
            description="Obsolete budget",
            amount=Amount(-230),
            category=Category.CAR_FUEL,
            date_range=DateRange(date(2023, 1, 1), relativedelta(months=1)),
        ),
        Budget(
            record_id=2,
            description="Recurring budget 1",
            amount=Amount(-300),
            category=Category.GROCERIES,
            date_range=RecurringDateRange(
                DateRange(date(2023, 3, 1), relativedelta(months=1)),
                period=relativedelta(months=1),
            ),
        ),
        Budget(
            record_id=3,
            description="Recurring budget 2",
            amount=Amount(-100),
            category=Category.OTHER,
            date_range=RecurringDateRange(
                DateRange(date(2023, 4, 1), relativedelta(months=1)),
                period=relativedelta(months=1),
                expiration_date=date(2023, 5, 31),
            ),
        ),
        Budget(
            record_id=4,
            description="Isolated budget",
            amount=Amount(-150),
            category=Category.OTHER,
            date_range=DateRange(date(2023, 4, 15), relativedelta(days=16)),
        ),
    )


class TestComputeBalanceEvolution:
    """Tests for compute_balance_evolution_per_day."""

    def test_start_date_after_end_date_raises(self, account: Account) -> None:
        """start_date > end_date raises ValueError."""
        analyzer = AccountAnalyzer(account, Forecast((), ()))
        with pytest.raises(ValueError, match="start_date must be <= end_date"):
            analyzer.compute_balance_evolution_per_day(
                date(2023, 3, 1), date(2023, 1, 1)
            )

    def test_no_forecast(self, account: Account) -> None:
        """Balance evolves based on historic operations only."""
        analyzer = AccountAnalyzer(account, Forecast((), ()))
        df = analyzer.compute_balance_evolution_per_day(
            date(2023, 1, 1), date(2023, 3, 1)
        )
        assert df.index[0].date() == date(2023, 1, 1)
        assert df.index[-1].date() == date(2023, 3, 1)
        assert df.loc["2023-01-01"]["Solde"] == 1080.0
        assert df.loc["2023-01-15"]["Solde"] == 1030.0
        assert df.loc["2023-02-15"]["Solde"] == 1000.0

    def test_with_planned_operations(
        self, account: Account, planned_operations: tuple[PlannedOperation, ...]
    ) -> None:
        """Balance reflects planned operations after actualization.

        Without operation links, past/current planned operations are advanced
        to the next period (not automatically executed via matcher).
        - Recurring op (2023-03-01, -20€/month until 2023-06-01): advanced to 2023-04-01
        - Isolated op (2023-03-15, -50€): kept as-is (future)
        """
        analyzer = AccountAnalyzer(account, Forecast(planned_operations, ()))
        df = analyzer.compute_balance_evolution_per_day(
            date(2023, 2, 1), date(2023, 8, 1)
        )
        assert df.index[0].date() == date(2023, 2, 1)
        assert df.index[-1].date() == date(2023, 8, 1)
        for date_str, expected_balance in {
            "2023-02-01": 1030.0,
            "2023-03-01": 1000.0,
            # Recurring op advanced to April, not executed in March
            "2023-03-02": 1000.0,
            # Isolated op executed
            "2023-03-15": 950.0,
            # Recurring op (advanced from March) + normal April occurrence
            "2023-04-01": 930.0,
            # Recurring op
            "2023-05-01": 910.0,
            # Recurring op executes on expiration date (inclusive)
            "2023-06-01": 890.0,
            "2023-07-01": 890.0,
            "2023-08-01": 890.0,
        }.items():
            assert df.loc[date_str]["Solde"] == pytest.approx(
                expected_balance
            ), f"Date: {date_str}"

    def test_with_budgets(self, account: Account, budgets: tuple[Budget, ...]) -> None:
        """Balance reflects budget consumption spread across days."""
        analyzer = AccountAnalyzer(account, Forecast((), budgets))
        df = analyzer.compute_balance_evolution_per_day(
            date(2023, 3, 1), date(2023, 7, 31)
        )
        assert df.index[0].date() == date(2023, 3, 1)
        assert df.index[-1].date() == date(2023, 7, 31)
        for date_str, expected_balance in {
            "2023-03-01": 1000.0,
            # Recurring budget 1: -300€ for 30 days left, -140€ for 14 days
            "2023-03-15": 860.0,
            # Recurring budget 1 consumed for March
            "2023-03-31": 700.0,
            # Recurring budget 1: -300€, Recurring budget 2: -100€, Isolated budget: -150€
            "2023-04-30": 150.0,
            # Recurring budget 1: -300€, Recurring budget 2: -100€
            "2023-05-31": -250.0,
            # Recurring budget 1: -300€
            "2023-06-30": -550.0,
            # Recurring budget 1: -300€
            "2023-07-31": -850.0,
        }.items():
            assert df.loc[date_str]["Solde"] == pytest.approx(
                expected_balance
            ), f"Date: {date_str}"


class TestComputeOperations:
    """Tests for compute_operations."""

    def test_filters_by_date_range(self, account: Account) -> None:
        """Only operations within the date range are returned."""
        analyzer = AccountAnalyzer(account, Forecast((), ()))
        df = analyzer.compute_operations(date(2023, 1, 1), date(2023, 1, 31))
        assert len(df) == 1
        assert df.iloc[0]["Description"] == "Operation 1"
        assert float(df.iloc[0]["Montant"]) == -50.0

    def test_includes_boundary_dates(self, account: Account) -> None:
        """Operations on start_date and end_date are included."""
        analyzer = AccountAnalyzer(account, Forecast((), ()))
        df = analyzer.compute_operations(date(2023, 1, 15), date(2023, 2, 15))
        assert len(df) == 2

    def test_no_operations_in_range(self, account: Account) -> None:
        """Date range with no operations returns empty DataFrame."""
        analyzer = AccountAnalyzer(account, Forecast((), ()))
        df = analyzer.compute_operations(date(2023, 6, 1), date(2023, 7, 1))
        assert len(df) == 0
        assert list(df.columns) == ["Catégorie", "Description", "Montant"]

    def test_empty_account(self) -> None:
        """Account with no operations returns empty DataFrame."""
        empty_account = Account(
            name="Empty",
            balance=500.0,
            currency="EUR",
            balance_date=date(2023, 1, 1),
            operations=(),
        )
        analyzer = AccountAnalyzer(empty_account, Forecast((), ()))
        df = analyzer.compute_operations(date(2023, 1, 1), date(2023, 12, 31))
        assert len(df) == 0


class TestComputeForecast:
    """Tests for compute_forecast."""

    def test_filters_expired_and_future(
        self, account: Account, budgets: tuple[Budget, ...]
    ) -> None:
        """Expired and future forecast items are excluded.

        budgets[0] (CAR_FUEL): DateRange 2023-01-01 to 2023-01-31 -> expired at 2023-03-01
        budgets[1] (GROCERIES): RecurringDateRange from 2023-03-01, no expiration -> included
        budgets[2] (OTHER): RecurringDateRange from 2023-04-01, expires 2023-05-31 -> included
        budgets[3] (OTHER): DateRange 2023-04-15 to 2023-04-30 -> included
        """
        analyzer = AccountAnalyzer(account, Forecast((), budgets))
        df = analyzer.compute_forecast(date(2023, 3, 1), date(2023, 6, 30))
        descriptions = set(df["Description"])
        assert "Obsolete budget" not in descriptions
        assert "Recurring budget 1" in descriptions
        assert "Recurring budget 2" in descriptions
        assert "Isolated budget" in descriptions

    def test_includes_planned_operations(
        self,
        account: Account,
        planned_operations: tuple[PlannedOperation, ...],
    ) -> None:
        """Active planned operations appear in forecast."""
        analyzer = AccountAnalyzer(account, Forecast(planned_operations, ()))
        df = analyzer.compute_forecast(date(2023, 3, 1), date(2023, 6, 30))
        descriptions = set(df["Description"])
        assert "Isolated Planned Operation" in descriptions
        assert "Recurring Planned Operation" in descriptions

    def test_recurring_shows_period(
        self, account: Account, budgets: tuple[Budget, ...]
    ) -> None:
        """Recurring items display their period, non-recurring show empty string."""
        analyzer = AccountAnalyzer(account, Forecast((), budgets))
        df = analyzer.compute_forecast(date(2023, 3, 1), date(2023, 6, 30))
        recurring_row = df[df["Description"] == "Recurring budget 1"].iloc[0]
        assert recurring_row["Périodicité"] == "1 Mois"

        isolated_row = df[df["Description"] == "Isolated budget"].iloc[0]
        assert isolated_row["Périodicité"] == ""

    def test_empty_forecast(self, account: Account) -> None:
        """No forecast items returns empty DataFrame."""
        analyzer = AccountAnalyzer(account, Forecast((), ()))
        df = analyzer.compute_forecast(date(2023, 1, 1), date(2023, 12, 31))
        assert len(df) == 0


class TestComputeBudgetForecast:
    """Tests for compute_budget_forecast."""

    def test_actual_and_forecast_columns(
        self,
        account: Account,
        planned_operations: tuple[PlannedOperation, ...],
        budgets: tuple[Budget, ...],
    ) -> None:
        """Expenses per category and month have Réel, Prévu, and Actualisé columns."""
        analyzer = AccountAnalyzer(account, Forecast(planned_operations, budgets))
        df = analyzer.compute_budget_forecast(date(2023, 1, 1), date(2023, 5, 1))
        assert df.loc[str(Category.GROCERIES)]["2023-01-01"]["Réel"] == -50.0
        assert df.loc[str(Category.GROCERIES)]["2023-02-01"]["Réel"] == -30.0
        # "Prévu" = raw forecast: budget (-300) + planned op (-20) = -320
        assert df.loc[str(Category.GROCERIES)]["2023-03-01"]["Prévu"] == -320.0
        assert df.loc[str(Category.CAR_FUEL)]["2023-03-01"]["Prévu"] == 0.0
        assert df.loc[str(Category.OTHER)]["2023-03-01"]["Prévu"] == -50.0
        # "Actualisé" = after actualization: planned op advanced to April
        assert df.loc[str(Category.GROCERIES)]["2023-03-01"]["Actualisé"] == -300.0
        assert df.loc[str(Category.CAR_FUEL)]["2023-03-01"]["Actualisé"] == 0.0
        assert df.loc[str(Category.OTHER)]["2023-03-01"]["Actualisé"] == -50.0
        assert df.loc[str(Category.GROCERIES)]["2023-04-01"]["Prévu"] == -320.0
        assert df.loc[str(Category.CAR_FUEL)]["2023-04-01"]["Prévu"] == 0.0
        assert df.loc[str(Category.OTHER)]["2023-04-01"]["Prévu"] == -250.0


class TestComputeBudgetStatistics:
    """Tests for compute_budget_statistics."""

    def test_empty_account(self) -> None:
        """Account with no operations returns empty DataFrame."""
        empty_account = Account(
            name="Empty",
            balance=0.0,
            currency="EUR",
            balance_date=date(2023, 1, 1),
            operations=(),
        )
        analyzer = AccountAnalyzer(empty_account, Forecast((), ()))
        df = analyzer.compute_budget_statistics(date(2023, 1, 1), date(2023, 12, 31))
        assert len(df) == 0
        assert "Total" in df.columns
        assert "Moyenne mensuelle" in df.columns

    def test_statistics_across_complete_months(self) -> None:
        """Statistics are computed only for complete months.

        Trimming logic:
        - analysis_start = max(min_op_date, start_date), then rounded UP to
          next month 1st if not already day 1
        - analysis_end = min(max_op_date, end_date), then rounded DOWN to
          previous month last day if not already day 1

        With ops on Jan 1, Feb 10, Mar 15, and range Jan 1 to Apr 1:
        - analysis_start = max(Jan 1, Jan 1) = Jan 1 (day 1 → kept)
        - analysis_end = min(Mar 15, Apr 1) = Mar 15 (not day 1 → Feb 28)
        - Analysis covers Jan 1 to Feb 28 (two complete months)
        """
        operations = (
            HistoricOperation(
                unique_id=1,
                description="Jan grocery",
                amount=Amount(-100.0),
                category=Category.GROCERIES,
                operation_date=date(2023, 1, 1),
            ),
            HistoricOperation(
                unique_id=2,
                description="Feb grocery",
                amount=Amount(-120.0),
                category=Category.GROCERIES,
                operation_date=date(2023, 2, 10),
            ),
            HistoricOperation(
                unique_id=3,
                description="Feb rent",
                amount=Amount(-800.0),
                category=Category.RENT,
                operation_date=date(2023, 2, 1),
            ),
            HistoricOperation(
                unique_id=4,
                description="Mar grocery",
                amount=Amount(-90.0),
                category=Category.GROCERIES,
                operation_date=date(2023, 3, 15),
            ),
        )
        test_account = Account(
            name="Test",
            balance=5000.0,
            currency="EUR",
            balance_date=date(2023, 4, 1),
            operations=operations,
        )
        analyzer = AccountAnalyzer(test_account, Forecast((), ()))
        df = analyzer.compute_budget_statistics(date(2023, 1, 1), date(2023, 4, 1))
        # Analysis covers Jan 1 to Feb 28 → Jan and Feb operations included
        assert str(Category.GROCERIES) in df.index
        assert str(Category.RENT) in df.index
        # Groceries: Jan (-100) + Feb (-120) = -220
        assert df.loc[str(Category.GROCERIES)]["Total"] == -220.0
        # Rent: Feb (-800)
        assert df.loc[str(Category.RENT)]["Total"] == -800.0
        # Monthly average for groceries: -220 / 2 months = -110
        assert df.loc[str(Category.GROCERIES)]["Moyenne mensuelle"] == -110.0

    def test_operations_outside_range_excluded(self) -> None:
        """Operations outside the requested date range are excluded."""
        operations = (
            HistoricOperation(
                unique_id=1,
                description="Old op",
                amount=Amount(-50.0),
                category=Category.GROCERIES,
                operation_date=date(2022, 6, 1),
            ),
            HistoricOperation(
                unique_id=2,
                description="In range",
                amount=Amount(-75.0),
                category=Category.GROCERIES,
                operation_date=date(2023, 2, 1),
            ),
            HistoricOperation(
                unique_id=3,
                description="In range 2",
                amount=Amount(-80.0),
                category=Category.GROCERIES,
                operation_date=date(2023, 3, 1),
            ),
        )
        test_account = Account(
            name="Test",
            balance=3000.0,
            currency="EUR",
            balance_date=date(2023, 4, 1),
            operations=operations,
        )
        analyzer = AccountAnalyzer(test_account, Forecast((), ()))
        df = analyzer.compute_budget_statistics(date(2023, 1, 1), date(2023, 4, 1))
        # Analysis: max(min_op_date=2022-06-01, start=2023-01-01) = 2023-01-01
        #   Jan 1 is day 1 → kept as-is
        # Analysis end: min(max_op_date=2023-03-01, end=2023-04-01) = 2023-03-01
        #   Mar 1 is day 1 → kept as-is
        # Range: 2023-01-01 to 2023-03-01 → covers Jan and Feb
        assert df.loc[str(Category.GROCERIES)]["Total"] == pytest.approx(-155.0)

    def test_single_incomplete_month(self) -> None:
        """All operations in a single incomplete month yields empty statistics.

        When the only operation is mid-month, trimming to complete months
        pushes analysis_start past analysis_end.
        """
        operations = (
            HistoricOperation(
                unique_id=1,
                description="Mid-month op",
                amount=Amount(-50.0),
                category=Category.GROCERIES,
                operation_date=date(2023, 3, 15),
            ),
        )
        test_account = Account(
            name="Test",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2023, 4, 1),
            operations=operations,
        )
        analyzer = AccountAnalyzer(test_account, Forecast((), ()))
        df = analyzer.compute_budget_statistics(date(2023, 3, 1), date(2023, 3, 31))
        # analysis_start = max(2023-03-15, 2023-03-01) = Mar 15 → trimmed to Apr 1
        # analysis_end = min(2023-03-15, 2023-03-31) = Mar 15 → trimmed to Feb 28
        # Apr 1 > Feb 28 → no operations qualify
        assert len(df) == 0


class TestComputeReport:
    """Tests for compute_report."""

    def test_report_contains_all_sections(
        self,
        account: Account,
        planned_operations: tuple[PlannedOperation, ...],
        budgets: tuple[Budget, ...],
    ) -> None:
        """compute_report assembles all sub-computations into a report."""
        analyzer = AccountAnalyzer(account, Forecast(planned_operations, budgets))
        report = analyzer.compute_report(date(2023, 1, 1), date(2023, 6, 30))

        assert report.balance_date == date(2023, 3, 1)
        assert report.start_date == date(2023, 1, 1)
        assert report.end_date == date(2023, 6, 30)

        # Operations DataFrame has expected columns
        assert list(report.operations.columns) == [
            "Catégorie",
            "Description",
            "Montant",
        ]
        assert len(report.operations) == 2

        # Forecast DataFrame is populated
        assert len(report.forecast) > 0

        # Balance evolution covers the full date range
        assert report.balance_evolution_per_day.index[0].date() == date(2023, 1, 1)
        assert report.balance_evolution_per_day.index[-1].date() == date(2023, 6, 30)

        # Budget forecast has multi-level columns
        assert report.budget_forecast.columns.nlevels == 2

        # Budget statistics has expected columns
        assert "Total" in report.budget_statistics.columns
        assert "Moyenne mensuelle" in report.budget_statistics.columns
