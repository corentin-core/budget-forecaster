"""Module with tests for the OperationsCategorizer class."""
from datetime import date

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay, SingleDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.operation.operations_categorizer import (
    OperationsCategorizer,
)


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
                date_range=SingleDay(date(2023, 1, 15)),
            ).set_matcher_params(description_hints={"Operation 1"}),
            PlannedOperation(
                record_id=2,
                description="Planned Operation 2",
                amount=Amount(200.0, "EUR"),
                category=Category.OTHER,
                date_range=RecurringDay(date(2023, 2, 15), relativedelta(months=1)),
            ).set_matcher_params(description_hints={"Operation 2"}),
            PlannedOperation(
                record_id=3,
                description="Planned Operation 3",
                amount=Amount(200.0, "EUR"),
                category=Category.SALARY,
                date_range=RecurringDay(date(2023, 2, 15), relativedelta(months=1)),
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
            operation_date=date(2023, 1, 15),
        ),
        HistoricOperation(
            unique_id=2,
            description="Operation 2",
            amount=Amount(200.0, "EUR"),
            category=Category.GROCERIES,
            operation_date=date(2023, 2, 15),
        ),
        HistoricOperation(
            unique_id=3,
            description="Operation 3",
            amount=Amount(100.0, "EUR"),
            category=Category.OTHER,
            operation_date=date(2023, 1, 15),
        ),
        HistoricOperation(
            unique_id=4,
            description="Operation 4",
            amount=Amount(200.0, "EUR"),
            category=Category.GROCERIES,
            operation_date=date(2023, 2, 15),
        ),
        HistoricOperation(
            unique_id=5,
            description="Operation 5",
            amount=Amount(200.0, "EUR"),
            category=Category.SALARY,
            operation_date=date(2023, 2, 15),
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
