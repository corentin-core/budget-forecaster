"""Module with tests for the ForecastActualizer class."""
from datetime import datetime

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account
from budget_forecaster.amount import Amount
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.forecast.forecast_actualizer import ForecastActualizer
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
    """Fixture with an account with one executed operation."""
    return Account(
        name="Test Account",
        balance=1000.0,
        currency="EUR",
        balance_date=datetime(2023, 1, 1),
        operations=(
            HistoricOperation(
                unique_id=1,
                description="Executed Operation",
                amount=Amount(50.0, "EUR"),
                category=Category.GROCERIES,
                date=datetime(2023, 1, 1),
            ),
        ),
    )


class TestForecastActualizer:
    """Tests for the ForecastActualizer class."""

    def test_no_operations(self, account: Account) -> None:
        """
        In this test, we have no planned operations.
        """
        forecast = Forecast(operations=(), budgets=())
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert not actualized_forecast.operations
        assert not actualized_forecast.budgets

    def test_late_operations(self, account: Account) -> None:
        """
        In this test, the last occurrences of the planned operation are late.
        The operations are postponed to the next period and
        the next period is updated to start after the postponed operations.
        """
        # We add one executed operation to the account to check that it is not considered as late
        account = account._replace(
            operations=(
                account.operations
                + (
                    HistoricOperation(
                        unique_id=2,
                        description="Not late operation",
                        amount=Amount(100.0, "EUR"),
                        category=Category.OTHER,
                        date=datetime(2023, 1, 1),
                    ),
                )
            )
        )
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    description="Late Operation",
                    amount=Amount(100.0, "EUR"),
                    category=Category.OTHER,
                    time_range=PeriodicDailyTimeRange(
                        datetime(2022, 12, 1), relativedelta(days=1)
                    ),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        # We have 5 late operations and the next period of the planned operation
        assert len(actualized_forecast.operations) == 6
        for _ in range(5):
            planned_operation = actualized_forecast.operations[0]
            assert isinstance(planned_operation.time_range, DailyTimeRange)
            assert planned_operation.description == "Late Operation"
            assert planned_operation.amount == 100.0
            assert planned_operation.time_range.initial_date == datetime(2023, 1, 2)
        planned_operation = actualized_forecast.operations[5]
        assert isinstance(planned_operation.time_range, PeriodicDailyTimeRange)
        assert planned_operation.description == "Late Operation"
        assert planned_operation.time_range.initial_date == datetime(2023, 1, 3)
        assert planned_operation.time_range.last_date == datetime.max

    def test_executed_operations(self, account: Account) -> None:
        """
        In this test, the planned operation is executed.
        """
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    description="Executed Operation",
                    amount=Amount(50.0, "EUR"),
                    category=Category.GROCERIES,
                    time_range=DailyTimeRange(datetime(2023, 1, 1)),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert not actualized_forecast.operations

    def test_anticipated_operations(self, account: Account) -> None:
        """
        In this test, several operations matches future time ranges of the planned operation.
        We consider as executed all operations that match the planned operation and
        close to the balance date.
        The next period of the planned operation is updated to start after the
        last executed operation.
        """
        account = account._replace(
            operations=tuple(
                HistoricOperation(
                    unique_id=id,
                    description="Executed Operation",
                    amount=Amount(50.0, "EUR"),
                    category=Category.GROCERIES,
                    date=datetime(2023, 1, 1),
                )
                for id in range(10)
            )
        )
        forecast = Forecast(
            operations=(
                PlannedOperation(
                    description="Anticipated Operation",
                    amount=Amount(50.0, "EUR"),
                    category=Category.GROCERIES,
                    time_range=PeriodicDailyTimeRange(
                        datetime(2023, 1, 2), relativedelta(days=1)
                    ),
                ),
            ),
            budgets=(),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert len(actualized_forecast.operations) == 1
        planned_operation = actualized_forecast.operations[0]
        assert planned_operation.description == "Anticipated Operation"
        assert isinstance(planned_operation.time_range, PeriodicDailyTimeRange)
        # Only the operations within the approximation date range are considered
        # The next period of the planned operation is updated to start after
        # the last executed operation
        assert planned_operation.time_range.initial_date == datetime(2023, 1, 7)
        assert planned_operation.time_range.last_date == datetime.max

    def test_budgets(self, account: Account) -> None:
        """
        In this test we have 3 budgets and one executed operation of 50.0 EUR.
        The first budget is a one-time operation that is completely
        consumed by the executed operation.
        The second budget is a periodic operation that is partially
        consumed by the executed operation.
        The remaining of the second budget is assigned to the next period.
        The third budget is a one-time operation that is not
        consumed by the executed operation.
        """
        forecast = Forecast(
            operations=(),
            budgets=(
                Budget(
                    description="Budget Operation 1",
                    amount=Amount(10.0, "EUR"),
                    category=Category.GROCERIES,
                    time_range=TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
                ),
                Budget(
                    description="Budget Operation 2",
                    amount=Amount(100.0, "EUR"),
                    category=Category.GROCERIES,
                    time_range=PeriodicTimeRange(
                        TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
                        relativedelta(months=1),
                    ),
                ),
                Budget(
                    description="Budget Operation 3",
                    amount=Amount(100.0, "EUR"),
                    category=Category.GROCERIES,
                    time_range=TimeRange(datetime(2023, 2, 1), relativedelta(months=1)),
                ),
            ),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert len(actualized_forecast.budgets) == 3
        budget_1 = actualized_forecast.budgets[0]
        assert budget_1.description == "Budget Operation 2"
        assert budget_1.time_range.initial_date == datetime(2023, 1, 2)
        assert budget_1.time_range.last_date == datetime(2023, 1, 31)
        # budget of Operation 1 is completely consumed
        # the remaining of the operation is assigned to Operation 2
        assert budget_1.amount == 60.0
        budget_2 = actualized_forecast.budgets[1]
        assert budget_2.description == "Budget Operation 2"
        assert budget_2.time_range.initial_date == datetime(2023, 2, 1)
        assert budget_2.time_range.last_date == datetime.max
        assert budget_2.amount == 100.0
        budget_3 = actualized_forecast.budgets[2]
        assert budget_3.description == "Budget Operation 3"
        assert budget_3.time_range.initial_date == datetime(2023, 2, 1)
        assert budget_3.time_range.last_date == datetime(2023, 2, 28)
        assert budget_3.amount == 100.0

    def test_expired_budget(self, account: Account) -> None:
        """
        In this test we have 2 budgets, one of them is expired.
        The expired budget is discarded and the other budget is partially
        consumed by the executed operation.
        The remaining of the budget is assigned to the next period.
        """
        forecast = Forecast(
            operations=(),
            budgets=(
                Budget(
                    description="Expired Budget",
                    amount=Amount(100.0, "EUR"),
                    category=Category.GROCERIES,
                    time_range=TimeRange(datetime(2022, 12, 31), relativedelta(days=1)),
                ),
                Budget(
                    description="Budget Operation",
                    amount=Amount(100.0, "EUR"),
                    category=Category.GROCERIES,
                    time_range=TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
                ),
            ),
        )
        actualizer = ForecastActualizer(account)
        actualized_forecast = actualizer(forecast)
        assert len(actualized_forecast.budgets) == 1
        assert actualized_forecast.budgets[0].description == "Budget Operation"
        assert actualized_forecast.budgets[0].time_range.initial_date == datetime(
            2023, 1, 2
        )
        assert actualized_forecast.budgets[0].time_range.last_date == datetime(
            2023, 1, 31
        )
        assert actualized_forecast.budgets[0].amount == 50.0

    def test_budget_last_day(self, account: Account) -> None:
        """
        Budget in their last day can be assigned to operations but are not
        reported on future periods.
        """
        budget_1 = Budget(
            description="Expired Budget",
            amount=Amount(10.0, "EUR"),
            category=Category.GROCERIES,
            time_range=TimeRange(datetime(2023, 1, 1), relativedelta(days=1)),
        )
        budget_2 = Budget(
            description="Budget Operation",
            amount=Amount(50.0, "EUR"),
            category=Category.GROCERIES,
            time_range=TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

        for budgets in (
            (budget_1, budget_2),
            (budget_2, budget_1),
        ):
            forecast = Forecast(operations=(), budgets=budgets)
            actualizer = ForecastActualizer(account)
            actualized_forecast = actualizer(forecast)
            assert len(actualized_forecast.budgets) == 1
            assert actualized_forecast.budgets[0].description == "Budget Operation"
            assert actualized_forecast.budgets[0].time_range.initial_date == datetime(
                2023, 1, 2
            )
            assert actualized_forecast.budgets[0].time_range.last_date == datetime(
                2023, 1, 31
            )
            assert actualized_forecast.budgets[0].amount == 10.0
