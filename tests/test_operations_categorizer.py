"""Module with tests for the OperationsCategorizer class."""
from datetime import datetime

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.amount import Amount
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operations_categorizer import (
    OperationsCategorizer,
)
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.time_range import DailyTimeRange, PeriodicDailyTimeRange
from budget_forecaster.types import Category


@pytest.fixture
def forecast() -> Forecast:
    """Fixture with a forecast with planned operations."""
    return Forecast(
        operations=(
            PlannedOperation(
                record_id=1,
                description="Planned Operation 1",
                amount=Amount(100.0, "EUR"),
                category=Category.GROCERIES,
                time_range=DailyTimeRange(datetime(2023, 1, 15)),
            ).set_matcher_params(description_hints={"Operation 1"}),
            PlannedOperation(
                record_id=2,
                description="Planned Operation 2",
                amount=Amount(200.0, "EUR"),
                category=Category.OTHER,
                time_range=PeriodicDailyTimeRange(
                    datetime(2023, 2, 15), relativedelta(months=1)
                ),
            ).set_matcher_params(description_hints={"Operation 2"}),
            PlannedOperation(
                record_id=3,
                description="Planned Operation 3",
                amount=Amount(200.0, "EUR"),
                category=Category.SALARY,
                time_range=PeriodicDailyTimeRange(
                    datetime(2023, 2, 15), relativedelta(months=1)
                ),
            ),
        ),
        budgets=(),
    )


@pytest.fixture
def operations() -> list[HistoricOperation]:
    """Fixture with a list of historic operations."""
    return [
        HistoricOperation(
            unique_id=1,
            description="Operation 1",
            amount=Amount(100.0, "EUR"),
            category=Category.OTHER,
            date=datetime(2023, 1, 15),
        ),
        HistoricOperation(
            unique_id=2,
            description="Operation 2",
            amount=Amount(200.0, "EUR"),
            category=Category.GROCERIES,
            date=datetime(2023, 2, 15),
        ),
        HistoricOperation(
            unique_id=3,
            description="Operation 3",
            amount=Amount(100.0, "EUR"),
            category=Category.OTHER,
            date=datetime(2023, 1, 15),
        ),
        HistoricOperation(
            unique_id=4,
            description="Operation 4",
            amount=Amount(200.0, "EUR"),
            category=Category.GROCERIES,
            date=datetime(2023, 2, 15),
        ),
        HistoricOperation(
            unique_id=5,
            description="Operation 5",
            amount=Amount(200.0, "EUR"),
            category=Category.SALARY,
            date=datetime(2023, 2, 15),
        ),
    ]


class TestOperationsCategorizer:
    """Tests for the OperationsCategorizer class."""

    def test_categorizes_operations_correctly(
        self, forecast: Forecast, operations: list[HistoricOperation]
    ) -> None:
        """Test that the OperationsCategorizer categorizes operations correctly."""
        categorizer = OperationsCategorizer(forecast)
        categorized_operations = {
            op.unique_id: op.category for op in categorizer(operations)
        }
        assert categorized_operations == {
            1: Category.GROCERIES,
            2: Category.OTHER,
            3: Category.OTHER,
            4: Category.GROCERIES,
            5: Category.SALARY,
        }

    def test_no_operations_to_categorize(self, forecast: Forecast) -> None:
        """
        Test that the OperationsCategorizer returns an empty list when there are
        no operations to categorize.
        """
        categorizer = OperationsCategorizer(forecast)
        categorized_operations = categorizer([])
        assert len(categorized_operations) == 0
