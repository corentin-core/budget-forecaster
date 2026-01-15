"""Module to test the AccountForecaster class."""
from datetime import datetime

import pandas as pd
import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account
from budget_forecaster.account.account_forecaster import AccountForecaster
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
    """Create a test account with two historic operations."""
    category = Category.GROCERIES
    operations = (
        HistoricOperation(
            unique_id=1,
            description="Operation 1",
            amount=Amount(-50.0),
            category=category,
            date=datetime(2023, 1, 15),
        ),
        HistoricOperation(
            unique_id=2,
            description="Operation 2",
            amount=Amount(-30.0),
            category=category,
            date=datetime(2023, 2, 15),
        ),
    )
    return Account(
        name="Test Account",
        balance=1000.0,
        currency="EUR",
        balance_date=datetime(2023, 2, 28),
        operations=operations,
    )


class TestAccountForecaster:
    """Test the AccountForecaster class."""

    def test_present_state(self, account: Account) -> None:
        """Test the present state of the account."""
        account_forecaster = AccountForecaster(account, Forecast((), ()))
        present_state = account_forecaster(account.balance_date)
        assert present_state.balance == 1000.0
        assert present_state.operations == account.operations

    def test_get_past_state(self, account: Account) -> None:
        """Test the past state of the account."""
        account_forecaster = AccountForecaster(account, Forecast((), ()))
        past_state = account_forecaster(datetime(2023, 1, 31))
        assert past_state.balance == 1030.0
        assert set(past_state.operations) == {account.operations[0]}

        past_state = account_forecaster(datetime(2023, 1, 1))
        assert past_state.balance == 1080.0
        assert not past_state.operations

    def test_get_future_state(self, account: Account) -> None:
        """Test the future state of the account."""
        account_forecaster = AccountForecaster(account, Forecast((), ()))
        future_state = account_forecaster(datetime(2023, 4, 1))
        assert future_state.balance == 1000.0
        assert set(future_state.operations) == {
            account.operations[0],
            account.operations[1],
        }


@pytest.fixture
def planned_operations() -> tuple[PlannedOperation, ...]:
    """Create a tuple of planned operations."""
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


class TestPlannedOperations:
    """Test the Account class with planned operations"""

    def test_initial_state(
        self, account: Account, planned_operations: tuple[PlannedOperation, ...]
    ) -> None:
        """Test the initial state of the account."""
        forecast = Forecast(operations=planned_operations, budgets=())
        account_forecaster = AccountForecaster(account, forecast)
        present_state = account_forecaster(account.balance_date)
        assert present_state.balance == 1000.0
        assert present_state.operations == account.operations

    def test_get_past_state(
        self, account: Account, planned_operations: tuple[PlannedOperation, ...]
    ) -> None:
        """Test the past state of the account."""
        forecast = Forecast(operations=planned_operations, budgets=())
        account_forecaster = AccountForecaster(account, forecast)
        past_state = account_forecaster(datetime(2023, 1, 31))
        assert past_state.balance == 1030.0
        assert set(past_state.operations) == {account.operations[0]}

        past_state = account_forecaster(datetime(2023, 1, 1))
        assert past_state.balance == 1080.0
        assert not past_state.operations

    def test_get_future_state(
        self, account: Account, planned_operations: tuple[PlannedOperation, ...]
    ) -> None:
        """Test the future state of the account."""
        forecast = Forecast(operations=planned_operations, budgets=())
        account_forecaster = AccountForecaster(account, forecast)
        future_state = account_forecaster(datetime(2023, 4, 1))
        assert future_state.balance == 910.0
        assert set(future_state.operations) == {
            *account.operations,
            HistoricOperation(
                unique_id=3,
                description="Isolated Planned Operation",
                amount=Amount(-50.0),
                category=Category.OTHER,
                date=datetime(2023, 3, 15),
            ),
            HistoricOperation(
                unique_id=4,
                description="Recurring Planned Operation",
                amount=Amount(-20.0),
                category=Category.GROCERIES,
                date=datetime(2023, 3, 1),
            ),
            HistoricOperation(
                unique_id=5,
                description="Recurring Planned Operation",
                amount=Amount(-20.0),
                category=Category.GROCERIES,
                date=datetime(2023, 4, 1),
            ),
        }


@pytest.fixture
def budgets() -> tuple[Budget, ...]:
    """Create a tuple of budgets."""
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


class TestBudget:
    """Test the Account class with budgets"""

    def test_initial_state(self, account: Account, budgets: tuple[Budget, ...]) -> None:
        """Test the initial state of the account."""
        forecast = Forecast(operations=(), budgets=budgets)
        account_forecaster = AccountForecaster(account, forecast)
        present_state = account_forecaster(account.balance_date)
        assert present_state.balance == 1000.0
        assert present_state.operations == account.operations

    def test_get_past_state(
        self, account: Account, budgets: tuple[Budget, ...]
    ) -> None:
        """Test the past state of the account."""
        forecast = Forecast(operations=(), budgets=budgets)
        account_forecaster = AccountForecaster(account, forecast)
        past_state = account_forecaster(datetime(2023, 1, 31))
        assert past_state.balance == 1030.0
        assert set(past_state.operations) == {account.operations[0]}

        past_state = account_forecaster(datetime(2023, 1, 1))
        assert past_state.balance == 1080.0
        assert not past_state.operations

    def test_get_future_state(
        self, account: Account, budgets: tuple[Budget, ...]
    ) -> None:
        """Test the future state of the account."""
        forecast = Forecast(operations=(), budgets=budgets)
        account_forecaster = AccountForecaster(account, forecast)
        future_state = account_forecaster(datetime(2023, 3, 31))
        # recurring budget 1 is applied : -300
        assert future_state.balance == pytest.approx(700.0)
        future_state = account_forecaster(datetime(2023, 4, 30))
        # recurring budget 1 + recurring budget 2 + isolated budget are applied : -300 - 100 - 150
        assert future_state.balance == pytest.approx(150.0)
        future_state = account_forecaster(datetime(2023, 5, 31))
        # recurring budget 1 + recurring budget 2 are applied : -300 - 100
        assert future_state.balance == pytest.approx(-250.0)

    def test_account_consistency(
        self,
        account: Account,
        planned_operations: tuple[PlannedOperation, ...],
        budgets: tuple[Budget, ...],
    ) -> None:
        """
        Test that the account state is consistent when computing from a future account state
        """
        forecast = Forecast(operations=planned_operations, budgets=budgets)
        account_forecaster = AccountForecaster(account, forecast)
        from_previous_account_state_forecaster = AccountForecaster(account, forecast)
        start_date = datetime(2023, 3, 1)
        end_date = datetime(2023, 7, 1)
        dates = pd.date_range(start_date, end_date, freq="D")

        for current_date in dates:
            from_previous_account_state = from_previous_account_state_forecaster(
                current_date
            )
            from_original_account_state = account_forecaster(current_date)
            assert from_previous_account_state.balance == pytest.approx(
                from_original_account_state.balance
            ), current_date

            from_previous_account_state_forecaster = AccountForecaster(
                from_previous_account_state, forecast
            )
