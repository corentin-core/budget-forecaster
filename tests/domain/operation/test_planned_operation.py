"""Module with tests for the PlannedOperation class."""
from datetime import date, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.time_range import (
    DailyTimeRange,
    PeriodicDailyTimeRange,
    TimeRange,
)
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation


@pytest.fixture
def recurring_planned_operation() -> PlannedOperation:
    """Return a recurring planned operation."""
    return PlannedOperation(
        record_id=1,
        description="Test Operation",
        amount=Amount(100.0),
        category=Category.GROCERIES,
        time_range=PeriodicDailyTimeRange(
            date(2023, 1, 1), relativedelta(months=1), date(2023, 12, 31)
        ),
    )


class TestRecurringPlannedOperation:
    """Test the behavior of a recurring planned operation."""

    def test_match_operation_within_date_range(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation within the date range matches."""
        operation_date = date(2023, 6, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=operation_date,
        )
        assert recurring_planned_operation.matcher.match(historic_operation)

    def test_match_operation_outside_date_range(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation outside the date range does not match."""
        operation_date = date(2024, 1, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=operation_date,
        )
        assert not recurring_planned_operation.matcher.match(historic_operation)

    def test_match_operation_different_amount(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation with a different amount does not match."""
        operation_date = date(2023, 6, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(200.0),
            category=Category.GROCERIES,
            operation_date=operation_date,
        )
        assert not recurring_planned_operation.matcher.match(historic_operation)

    def test_match_operation_different_category(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation with a different category does not match."""
        operation_date = date(2023, 6, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.OTHER,
            operation_date=operation_date,
        )
        assert not recurring_planned_operation.matcher.match(historic_operation)

    def test_match_operation_different_date(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation with a different date does not match."""
        operation_date = date(2023, 6, 1) + timedelta(days=6)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.OTHER,
            operation_date=operation_date,
        )
        assert not recurring_planned_operation.matcher.match(historic_operation)

    def test_amount_on_period(
        self, recurring_planned_operation: PlannedOperation
    ) -> None:
        """Test the amount on period for a recurring planned operation."""
        for date_start, date_end, expected_amount in (
            (date(2023, 1, 1), date(2023, 1, 31), 100.0),
            (date(2022, 12, 1), date(2023, 1, 31), 100.0),
            (date(2024, 2, 1), date(2024, 2, 15), 0.0),
            (date(2023, 6, 1), date(2023, 6, 1), 100.0),
            (date(2023, 6, 1), date(2023, 6, 2), 100.0),
            (date(2023, 1, 1), date(2023, 3, 15), 300.0),
        ):
            assert (
                recurring_planned_operation.amount_on_period(date_start, date_end)
                == expected_amount
            ), f"Expected {expected_amount} for {date_start} - {date_end}"


@pytest.fixture
def isolated_planned_operation() -> PlannedOperation:
    """Return an isolated planned operation."""
    return PlannedOperation(
        record_id=2,
        description="Test Operation",
        amount=Amount(100.0),
        category=Category.GROCERIES,
        time_range=DailyTimeRange(date(2023, 1, 1)),
    )


class TestIsolatedPlannedOperation:
    """Test the behavior of an isolated planned operation."""

    def test_match(self, isolated_planned_operation: PlannedOperation) -> None:
        """Test that a historic operation matches the isolated planned operation."""
        operation_date = date(2023, 1, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=operation_date,
        )
        assert isolated_planned_operation.matcher.match(historic_operation)

    def test_no_match_amount(
        self, isolated_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation with a different amount does not match."""
        operation_date = date(2023, 1, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(200.0),
            category=Category.GROCERIES,
            operation_date=operation_date,
        )
        assert not isolated_planned_operation.matcher.match(historic_operation)

    def test_no_match_category(
        self, isolated_planned_operation: PlannedOperation
    ) -> None:
        """Test that a historic operation with a different category does not match."""
        operation_date = date(2023, 1, 1)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.OTHER,
            operation_date=operation_date,
        )
        assert not isolated_planned_operation.matcher.match(historic_operation)

    def test_no_match_date(self, isolated_planned_operation: PlannedOperation) -> None:
        """Test that a historic operation with a different date does not match."""
        operation_date = date(2023, 1, 10)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            operation_date=operation_date,
        )
        assert not isolated_planned_operation.matcher.match(historic_operation)

    def test_amount_on_period(
        self, isolated_planned_operation: PlannedOperation
    ) -> None:
        """Test the amount on period for an isolated planned operation."""
        for date_start, date_end, expected_amount in (
            (date(2023, 1, 1), date(2023, 1, 1), 100.0),
            (date(2023, 1, 1), date(2023, 1, 2), 100.0),
            (date(2022, 1, 1), date(2022, 12, 31), 0.0),
            (date(2022, 12, 1), date(2023, 1, 1), 100.0),
            (date(2024, 1, 1), date(2024, 1, 2), 0.0),
        ):
            assert (
                isolated_planned_operation.amount_on_period(date_start, date_end)
                == expected_amount
            )


class TestPlannedOperationTypeErrors:
    """Tests for TypeError when passing invalid types to PlannedOperation."""

    def test_init_invalid_time_range_type(self) -> None:
        """Test PlannedOperation raises TypeError for invalid time_range type."""
        with pytest.raises(
            TypeError,
            match="time_range must be DailyTimeRange or PeriodicDailyTimeRange",
        ):
            PlannedOperation(
                record_id=1,
                description="Test",
                amount=Amount(100.0),
                category=Category.GROCERIES,
                time_range=TimeRange(date(2023, 1, 1), relativedelta(months=1)),
            )

    @pytest.fixture
    def planned_operation(self) -> PlannedOperation:
        """Create a planned operation for testing."""
        return PlannedOperation(
            record_id=1,
            description="Test",
            amount=Amount(100.0),
            category=Category.GROCERIES,
            time_range=DailyTimeRange(date(2023, 1, 1)),
        )

    def test_replace_invalid_record_id(
        self, planned_operation: PlannedOperation
    ) -> None:
        """Test PlannedOperation.replace() raises TypeError for invalid record_id."""
        with pytest.raises(TypeError, match="record_id must be int or None"):
            planned_operation.replace(record_id="1")

    def test_replace_invalid_description(
        self, planned_operation: PlannedOperation
    ) -> None:
        """Test PlannedOperation.replace() raises TypeError for invalid description."""
        with pytest.raises(TypeError, match="description must be str"):
            planned_operation.replace(description=123)

    def test_replace_invalid_amount(self, planned_operation: PlannedOperation) -> None:
        """Test PlannedOperation.replace() raises TypeError for invalid amount."""
        with pytest.raises(TypeError, match="amount must be Amount"):
            planned_operation.replace(amount=100.0)

    def test_replace_invalid_category(
        self, planned_operation: PlannedOperation
    ) -> None:
        """Test PlannedOperation.replace() raises TypeError for invalid category."""
        with pytest.raises(TypeError, match="category must be Category"):
            planned_operation.replace(category="GROCERIES")

    def test_replace_invalid_time_range(
        self, planned_operation: PlannedOperation
    ) -> None:
        """Test PlannedOperation.replace() raises TypeError for invalid time_range."""
        with pytest.raises(
            TypeError,
            match="time_range must be DailyTimeRange or PeriodicDailyTimeRange",
        ):
            planned_operation.replace(
                time_range=TimeRange(date(2023, 1, 1), relativedelta(months=1))
            )


class TestPlannedOperationSplitAt:
    """Tests for PlannedOperation.split_at() method."""

    def test_split_at_returns_terminated_and_continuation(self) -> None:
        """Test split_at returns two PlannedOperations."""
        op = PlannedOperation(
            record_id=1,
            description="Salary",
            amount=Amount(2500.0),
            category=Category.SALARY,
            time_range=PeriodicDailyTimeRange(
                date(2025, 1, 1), relativedelta(months=1), date(2025, 12, 31)
            ),
        )

        terminated, continuation = op.split_at(date(2025, 6, 1))

        # Terminated ends day before first new iteration (June 1)
        assert terminated.time_range.last_date == date(2025, 5, 31)
        assert terminated.id == 1  # Keeps original ID

        # Continuation starts at first iteration >= split date
        assert continuation.time_range.initial_date == date(2025, 6, 1)
        assert continuation.id is None  # New record
        assert continuation.description == "Salary"
        assert continuation.amount == 2500.0
        assert continuation.category == Category.SALARY

    def test_split_at_with_new_amount(self) -> None:
        """Test split_at with new amount for continuation."""
        op = PlannedOperation(
            record_id=1,
            description="Salary",
            amount=Amount(2500.0),
            category=Category.SALARY,
            time_range=PeriodicDailyTimeRange(
                date(2025, 1, 1), relativedelta(months=1)
            ),
        )

        _, continuation = op.split_at(date(2025, 6, 1), new_amount=Amount(3000.0))

        assert continuation.amount == 3000.0

    def test_split_at_with_new_period(self) -> None:
        """Test split_at with new period for continuation."""
        op = PlannedOperation(
            record_id=1,
            description="Salary",
            amount=Amount(2500.0),
            category=Category.SALARY,
            time_range=PeriodicDailyTimeRange(
                date(2025, 1, 1), relativedelta(months=1)
            ),
        )

        _, continuation = op.split_at(
            date(2025, 6, 1), new_period=relativedelta(months=3)
        )

        assert continuation.time_range.period == relativedelta(months=3)

    def test_split_at_copies_matcher_params(self) -> None:
        """Test split_at copies matcher parameters to continuation."""
        op = PlannedOperation(
            record_id=1,
            description="Salary",
            amount=Amount(2500.0),
            category=Category.SALARY,
            time_range=PeriodicDailyTimeRange(
                date(2025, 1, 1), relativedelta(months=1)
            ),
        ).set_matcher_params(
            description_hints={"SALARY", "EMPLOYER"},
            approximation_date_range=timedelta(days=10),
            approximation_amount_ratio=0.1,
        )

        _, continuation = op.split_at(date(2025, 6, 1))

        assert continuation.matcher.description_hints == {"SALARY", "EMPLOYER"}
        assert continuation.matcher.approximation_date_range == timedelta(days=10)
        assert continuation.matcher.approximation_amount_ratio == 0.1

    def test_split_at_non_periodic_raises_error(self) -> None:
        """Test split_at raises ValueError for non-periodic operation."""
        op = PlannedOperation(
            record_id=1,
            description="One-time",
            amount=Amount(100.0),
            category=Category.OTHER,
            time_range=DailyTimeRange(date(2025, 1, 1)),
        )

        with pytest.raises(ValueError, match="Cannot split a non-periodic"):
            op.split_at(date(2025, 6, 1))
