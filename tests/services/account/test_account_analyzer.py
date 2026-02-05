"""Module to test the AccountAnalyzer class."""
from datetime import date

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.time_range import (
    DailyTimeRange,
    PeriodicDailyTimeRange,
    PeriodicTimeRange,
    TimeRange,
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
            time_range=DailyTimeRange(date(2023, 3, 15)),
        ),
        PlannedOperation(
            record_id=2,
            description="Recurring Planned Operation",
            amount=Amount(-20.0),
            category=Category.GROCERIES,
            time_range=PeriodicDailyTimeRange(
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
            time_range=TimeRange(date(2023, 1, 1), relativedelta(months=1)),
        ),
        Budget(
            record_id=2,
            description="Recurring budget 1",
            amount=Amount(-300),
            category=Category.GROCERIES,
            time_range=PeriodicTimeRange(
                TimeRange(date(2023, 3, 1), relativedelta(months=1)),
                period=relativedelta(months=1),
            ),
        ),
        Budget(
            record_id=3,
            description="Recurring budget 2",
            amount=Amount(-100),
            category=Category.OTHER,
            time_range=PeriodicTimeRange(
                TimeRange(date(2023, 4, 1), relativedelta(months=1)),
                period=relativedelta(months=1),
                expiration_date=date(2023, 5, 31),
            ),
        ),
        Budget(
            record_id=4,
            description="Isolated budget",
            amount=Amount(-150),
            category=Category.OTHER,
            time_range=TimeRange(date(2023, 4, 15), relativedelta(days=16)),
        ),
    )


class TestAccountAnalyzer:
    """Test the AccountAnalyzer class."""

    def test_balance_evolution_start_date_after_end_date_raises(
        self, account: Account
    ) -> None:
        """Test that start_date > end_date raises ValueError."""
        account_analyzer = AccountAnalyzer(account, Forecast((), ()))
        with pytest.raises(ValueError, match="start_date must be <= end_date"):
            account_analyzer.compute_balance_evolution_per_day(
                date(2023, 3, 1), date(2023, 1, 1)
            )

    def test_balance_evolution_no_forecast(self, account: Account) -> None:
        """Test the balance evolution without forecast."""
        account_analyzer = AccountAnalyzer(account, Forecast((), ()))
        balance_evolution = account_analyzer.compute_balance_evolution_per_day(
            date(2023, 1, 1), date(2023, 3, 1)
        )
        assert balance_evolution.index[0].date() == date(2023, 1, 1)
        assert balance_evolution.index[-1].date() == date(2023, 3, 1)
        assert balance_evolution.loc["2023-01-01"]["Solde"] == 1080.0
        assert balance_evolution.loc["2023-01-15"]["Solde"] == 1030.0
        assert balance_evolution.loc["2023-02-15"]["Solde"] == 1000.0

    def test_balance_evolution_planned_operations(
        self, account: Account, planned_operations: tuple[PlannedOperation, ...]
    ) -> None:
        """Test the balance evolution with planned operations.

        Without operation links, past/current planned operations are advanced
        to the next period (not automatically executed via matcher).
        - Recurring op (2023-03-01, -20€/month until 2023-06-01): advanced to 2023-04-01
        - Isolated op (2023-03-15, -50€): kept as-is (future)
        """
        account_analyzer = AccountAnalyzer(account, Forecast(planned_operations, ()))
        balance_evolution = account_analyzer.compute_balance_evolution_per_day(
            date(2023, 2, 1), date(2023, 8, 1)
        )
        assert balance_evolution.index[0].date() == date(2023, 2, 1)
        assert balance_evolution.index[-1].date() == date(2023, 8, 1)
        for date_str, expected_balance in {
            "2023-02-01": 1030.0,
            "2023-03-01": 1000.0,
            # No execution on 2023-03-02 - recurring op advanced to April
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
            assert balance_evolution.loc[date_str]["Solde"] == pytest.approx(
                expected_balance
            ), f"Date: {date_str}"

    def test_balance_evolution_budgets(
        self, account: Account, budgets: tuple[Budget, ...]
    ) -> None:
        """Test the balance evolution with budgets."""
        account_analyzer = AccountAnalyzer(account, Forecast((), budgets))
        balance_evolution = account_analyzer.compute_balance_evolution_per_day(
            date(2023, 3, 1), date(2023, 7, 31)
        )
        assert balance_evolution.index[0].date() == date(2023, 3, 1)
        assert balance_evolution.index[-1].date() == date(2023, 7, 31)
        for date_str, expected_balance in {
            "2023-03-01": 1000.0,
            # Recurring budget 1: -300.0 for 30 days left, -140.0 for 14 days
            "2023-03-15": 860.0,
            # Recurring budget 1 consumed for march
            "2023-03-31": 700.0,
            # Recurring budget 1: -300.0, Recurring budget 2: -100.0, Isolated budget: -150.0
            "2023-04-30": 150.0,
            # Recurring budget 1: -300.0, Recurring budget 2: -100.0
            "2023-05-31": -250.0,
            # Recurring budget 1: -300.0
            "2023-06-30": -550.0,
            # Recurring budget 1: -300.0
            "2023-07-31": -850.0,
        }.items():
            assert balance_evolution.loc[date_str]["Solde"] == pytest.approx(
                expected_balance
            ), f"Date: {date_str}"

    def test_compute_budget_forecast(
        self,
        account: Account,
        planned_operations: tuple[PlannedOperation, ...],
        budgets: tuple[Budget, ...],
    ) -> None:
        """Test the expenses per category and month.

        Without operation links:
        - "Prévu" shows the raw forecast (budget + planned ops)
        - "Actualisé" shows the forecast after actualizing past/current ops
          Past/current planned ops are advanced to next period (not executed)
        """
        account_analyzer = AccountAnalyzer(
            account, Forecast(planned_operations, budgets)
        )
        expenses_per_category_and_month = account_analyzer.compute_budget_forecast(
            date(2023, 1, 1), date(2023, 5, 1)
        )
        assert (
            expenses_per_category_and_month.loc[str(Category.GROCERIES)]["2023-01-01"][
                "Réel"
            ]
            == -50.0
        )
        assert (
            expenses_per_category_and_month.loc[str(Category.GROCERIES)]["2023-02-01"][
                "Réel"
            ]
            == -30.0
        )
        # "Prévu" = raw forecast: budget (-300) + planned op (-20) = -320
        assert (
            expenses_per_category_and_month.loc[str(Category.GROCERIES)]["2023-03-01"][
                "Prévu"
            ]
            == -320.0
        )
        assert (
            expenses_per_category_and_month.loc[str(Category.CAR_FUEL)]["2023-03-01"][
                "Prévu"
            ]
            == 0.0
        )
        assert (
            expenses_per_category_and_month.loc[str(Category.OTHER)]["2023-03-01"][
                "Prévu"
            ]
            == -50.0
        )
        # "Actualisé" = after actualization: planned op advanced to April, only budget remains
        assert (
            expenses_per_category_and_month.loc[str(Category.GROCERIES)]["2023-03-01"][
                "Actualisé"
            ]
            == -300.0
        )
        assert (
            expenses_per_category_and_month.loc[str(Category.CAR_FUEL)]["2023-03-01"][
                "Actualisé"
            ]
            == 0.0
        )
        assert (
            expenses_per_category_and_month.loc[str(Category.OTHER)]["2023-03-01"][
                "Actualisé"
            ]
            == -50.0
        )
        assert (
            expenses_per_category_and_month.loc[str(Category.GROCERIES)]["2023-04-01"][
                "Prévu"
            ]
            == -320.0
        )
        assert (
            expenses_per_category_and_month.loc[str(Category.CAR_FUEL)]["2023-04-01"][
                "Prévu"
            ]
            == 0.0
        )
        assert (
            expenses_per_category_and_month.loc[str(Category.OTHER)]["2023-04-01"][
                "Prévu"
            ]
            == -250.0
        )
