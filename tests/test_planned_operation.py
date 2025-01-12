"""Module with tests for the PlannedOperation class."""
from datetime import datetime, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.time_range import DailyTimeRange, PeriodicDailyTimeRange
from budget_forecaster.types import Category


@pytest.fixture
def recurring_planned_operation() -> PlannedOperation:
    """Return a recurring planned operation."""
    return PlannedOperation(
        description="Test Operation",
        amount=Amount(100.0),
        category=Category.GROCERIES,
        time_range=PeriodicDailyTimeRange(
            datetime(2023, 1, 1), relativedelta(months=1), datetime(2023, 12, 31)
        ),
    )


class TestRecurringPlannedOperation:
    """Test the behavior of a recurring planned operation."""

    def test_match_operation_within_date_range(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation within the date range matches."""
        operation_date = datetime(2023, 6, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=operation_date,
        )
        assert recurring_planned_operation.matcher.match(historic_operation)

    def test_match_operation_outside_date_range(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation outside the date range does not match."""
        operation_date = datetime(2024, 1, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=operation_date,
        )
        assert not recurring_planned_operation.matcher.match(historic_operation)

    def test_match_operation_different_amount(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation with a different amount does not match."""
        operation_date = datetime(2023, 6, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(200.0),
            category=Category.GROCERIES,
            date=operation_date,
        )
        assert not recurring_planned_operation.matcher.match(historic_operation)

    def test_match_operation_different_category(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation with a different category does not match."""
        operation_date = datetime(2023, 6, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.OTHER,
            date=operation_date,
        )
        assert not recurring_planned_operation.matcher.match(historic_operation)

    def test_match_operation_different_date(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation with a different date does not match."""
        operation_date = datetime(2023, 6, 1) + timedelta(days=6)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.OTHER,
            date=operation_date,
        )
        assert not recurring_planned_operation.matcher.match(historic_operation)

    def test_amount_on_period(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test the amount on period for a recurring planned operation."""
        for date_start, date_end, expected_amount in (
            (datetime(2023, 1, 1), datetime(2023, 1, 31), 100.0),
            (datetime(2022, 12, 1), datetime(2023, 1, 31), 100.0),
            (datetime(2024, 2, 1), datetime(2024, 2, 15), 0.0),
            (datetime(2023, 6, 1), datetime(2023, 6, 1), 100.0),
            (datetime(2023, 6, 1), datetime(2023, 6, 2), 100.0),
            (datetime(2023, 1, 1), datetime(2023, 3, 15), 300.0),
        ):
            assert (
                recurring_planned_operation.amount_on_period(date_start, date_end)
                == expected_amount
            ), f"Expected {expected_amount} for {date_start} - {date_end}"


@pytest.fixture
def isolated_planned_operation() -> PlannedOperation:
    """Return an isolated planned operation."""
    return PlannedOperation(
        description="Test Operation",
        amount=Amount(100.0),
        category=Category.GROCERIES,
        time_range=DailyTimeRange(datetime(2023, 1, 1)),
    )


class TestIsolatedPlannedOperation:
    """Test the behavior of an isolated planned operation."""

    def test_match(self, isolated_planned_operation: PlannedOperation) -> None:
        """Test that a historic operation matches the isolated planned operation."""
        operation_date = datetime(2023, 1, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=operation_date,
        )
        assert isolated_planned_operation.matcher.match(historic_operation)

    def test_no_match_amount(
        self, isolated_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation with a different amount does not match."""
        operation_date = datetime(2023, 1, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(200.0),
            category=Category.GROCERIES,
            date=operation_date,
        )
        assert not isolated_planned_operation.matcher.match(historic_operation)

    def test_no_match_category(
        self, isolated_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation with a different category does not match."""
        operation_date = datetime(2023, 1, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.OTHER,
            date=operation_date,
        )
        assert not isolated_planned_operation.matcher.match(historic_operation)

    def test_no_match_date(self, isolated_planned_operation: PlannedOperation) -> None:
        """Test that a historic operation with a different date does not match."""
        operation_date = datetime(2023, 1, 10)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            date=operation_date,
        )
        assert not isolated_planned_operation.matcher.match(historic_operation)

    def test_amount_on_period(
        self, isolated_planned_operation: PlannedOperation
    ) -> None:
        """Test the amount on period for an isolated planned operation."""
        for date_start, date_end, expected_amount in (
            (datetime(2023, 1, 1), datetime(2023, 1, 1), 100.0),
            (datetime(2023, 1, 1), datetime(2023, 1, 2), 100.0),
            (datetime(2022, 1, 1), datetime(2022, 12, 31), 0.0),
            (datetime(2022, 12, 1), datetime(2023, 1, 1), 100.0),
            (datetime(2024, 1, 1), datetime(2024, 1, 2), 0.0),
        ):
            assert (
                isolated_planned_operation.amount_on_period(date_start, date_end)
                == expected_amount
            )
