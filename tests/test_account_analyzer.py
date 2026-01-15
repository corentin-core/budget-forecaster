"""Module to test the AccountAnalyzer class."""
from datetime import datetime

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account
from budget_forecaster.account.account_analyzer import AccountAnalyzer
from budget_forecaster.amount import Amount
from budget_forecaster.forecast.forecast import Forecast
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
def account() -> Account:
    """Return an account with two historic operations."""
    operations = (
        HistoricOperation(
            unique_id=1,
            description="Operation 1",
            amount=Amount(-50.0),
            category=Category.GROCERIES,
            date=datetime(2023, 1, 15),
        ),
        HistoricOperation(
            unique_id=2,
            description="Operation 2",
            amount=Amount(-30.0),
            category=Category.GROCERIES,
            date=datetime(2023, 2, 15),
        ),
    )
    return Account(
        name="Test Account",
        balance=1000.0,
        currency="EUR",
        balance_date=datetime(2023, 3, 1),
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
            time_range=DailyTimeRange(datetime(2023, 3, 15)),
        ),
        PlannedOperation(
            record_id=2,
            description="Recurring Planned Operation",
            amount=Amount(-20.0),
            category=Category.GROCERIES,
            time_range=PeriodicDailyTimeRange(
                datetime(2023, 3, 1),
                expiration_date=datetime(2023, 6, 1),
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
            time_range=TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        ),
        Budget(
            record_id=2,
            description="Recurring budget 1",
            amount=Amount(-300),
            category=Category.GROCERIES,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2023, 3, 1), relativedelta(months=1)),
                period=relativedelta(months=1),
            ),
        ),
        Budget(
            record_id=3,
            description="Recurring budget 2",
            amount=Amount(-100),
            category=Category.OTHER,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2023, 4, 1), relativedelta(months=1)),
                period=relativedelta(months=1),
                expiration_date=datetime(2023, 5, 31),
            ),
        ),
        Budget(
            record_id=4,
            description="Isolated budget",
            amount=Amount(-150),
            category=Category.OTHER,
            time_range=TimeRange(datetime(2023, 4, 15), relativedelta(days=16)),
        ),
    )


class TestAccountAnalyzer:
    """Test the AccountAnalyzer class."""

    def test_balance_evolution_no_forecast(self, account: Account) -> None:
        """Test the balance evolution without forecast."""
        account_analyzer = AccountAnalyzer(account, Forecast((), ()))
        balance_evolution = account_analyzer.compute_balance_evolution_per_day(
            datetime(2023, 1, 1), datetime(2023, 3, 1)
        )
        assert balance_evolution.index[0] == datetime(2023, 1, 1)
        assert balance_evolution.index[-1] == datetime(2023, 3, 1)
        assert balance_evolution.loc["2023-01-01"]["Solde"] == 1080.0
        assert balance_evolution.loc["2023-01-15"]["Solde"] == 1030.0
        assert balance_evolution.loc["2023-02-15"]["Solde"] == 1000.0

    def test_balance_evolution_planned_operations(
        self, account: Account, planned_operations: tuple[PlannedOperation, ...]
    ) -> None:
        """Test the balance evolution with planned operations."""
        account_analyzer = AccountAnalyzer(account, Forecast(planned_operations, ()))
        balance_evolution = account_analyzer.compute_balance_evolution_per_day(
            datetime(2023, 2, 1), datetime(2023, 8, 1)
        )
        assert balance_evolution.index[0] == datetime(2023, 2, 1)
        assert balance_evolution.index[-1] == datetime(2023, 8, 1)
        for date, expected_balance in {
            "2023-02-01": 1030.0,
            "2023-03-01": 1000.0,
            "2023-03-02": 980.0,
            "2023-03-15": 930.0,
            "2023-04-01": 910.0,
            "2023-05-01": 890.0,
            "2023-06-01": 870.0,
            "2023-07-01": 870.0,
            "2023-08-01": 870.0,
        }.items():
            assert balance_evolution.loc[date]["Solde"] == pytest.approx(
                expected_balance
            ), f"Date: {date}"

    def test_balance_evolution_budgets(
        self, account: Account, budgets: tuple[Budget, ...]
    ) -> None:
        """Test the balance evolution with budgets."""
        account_analyzer = AccountAnalyzer(account, Forecast((), budgets))
        balance_evolution = account_analyzer.compute_balance_evolution_per_day(
            datetime(2023, 3, 1), datetime(2023, 7, 31)
        )
        assert balance_evolution.index[0] == datetime(2023, 3, 1)
        assert balance_evolution.index[-1] == datetime(2023, 7, 31)
        for date, expected_balance in {
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
            assert balance_evolution.loc[date]["Solde"] == pytest.approx(
                expected_balance
            ), f"Date: {date}"

    def test_compute_budget_forecast(
        self,
        account: Account,
        planned_operations: tuple[PlannedOperation, ...],
        budgets: tuple[Budget, ...],
    ) -> None:
        """Test the expenses per category and month."""
        account_analyzer = AccountAnalyzer(
            account, Forecast(planned_operations, budgets)
        )
        expenses_per_category_and_month = account_analyzer.compute_budget_forecast(
            datetime(2023, 1, 1), datetime(2023, 5, 1)
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
        assert (
            expenses_per_category_and_month.loc[str(Category.GROCERIES)]["2023-03-01"][
                "Actualisé"
            ]
            == -320.0
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
