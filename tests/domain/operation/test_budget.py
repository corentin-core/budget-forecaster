"""Module with tests for the budget class."""
from datetime import datetime

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.time_range import PeriodicTimeRange, TimeRange
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation


@pytest.fixture
def recurring_budget() -> Budget:
    """Fixture with a recurring budget."""
    return Budget(
        record_id=1,
        description="Test Budget",
        amount=Amount(-100.0),
        category=Category.GROCERIES,
        time_range=PeriodicTimeRange(
            TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
            relativedelta(months=1),
            datetime(2023, 12, 31),
        ),
    )


class TestRecurringBudget:
    """Test the budget class with a renewable period."""

    def test_matches_operation_within_budget(self, recurring_budget: Budget) -> None:
        """Test that the budget matches operations within the budget."""
        for operation_date in (
            datetime(2023, 1, 1),
            datetime(2023, 12, 31),
            datetime(2023, 6, 15),
        ):
            historic_operation = HistoricOperation(
                unique_id=1,
                description="Test Operation",
                amount=Amount(-100.0),
                category=Category.GROCERIES,
                date=operation_date,
            )
            assert recurring_budget.matcher.match(historic_operation)

    def test_matches_operation_outside_budget(self, recurring_budget: Budget) -> None:
        """Test that the budget does not match operations outside the budget."""
        for operation_date in (datetime(2024, 1, 1), datetime(2022, 12, 31)):
            historic_operation = HistoricOperation(
                unique_id=1,
                description="Test Operation",
                amount=Amount(-100.0),
                category=Category.GROCERIES,
                date=operation_date,
            )
            assert not recurring_budget.matcher.match(historic_operation)

    def test_matches_operation_different_category(
        self, recurring_budget: Budget
    ) -> None:
        """Test that the budget does not match operations with different categories."""
        operation_date = datetime(2023, 6, 15)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(-100.0),
            category=Category.OTHER,
            date=operation_date,
        )
        assert not recurring_budget.matcher.match(historic_operation)

    def test_amount_on_period(self, recurring_budget: Budget) -> None:
        """Test the amount on period for a recurring budget."""
        for date_start, date_end, expected_amount in (
            (datetime(2023, 1, 1), datetime(2023, 1, 31), -100.0),
            (datetime(2022, 12, 1), datetime(2023, 1, 31), -100.0),
            (datetime(2024, 2, 1), datetime(2024, 2, 15), 0.0),
            (datetime(2023, 4, 1), datetime(2023, 4, 15), -50.0),
            (datetime(2023, 4, 16), datetime(2023, 4, 30), -50.0),
            (datetime(2023, 1, 1), datetime(2023, 12, 31), -1200.0),
        ):
            amount = recurring_budget.amount_on_period(date_start, date_end)
            assert amount == pytest.approx(
                expected_amount
            ), f"Expected {expected_amount} but got {amount} on period {date_start} - {date_end}"


@pytest.fixture
def budget_no_period() -> Budget:
    """Fixture with a budget with no renewable period."""
    return Budget(
        record_id=2,
        description="Test Budget",
        amount=Amount(-200.0),
        category=Category.GROCERIES,
        time_range=TimeRange(datetime(2023, 1, 1), relativedelta(days=30)),
    )


class TestIsolatedBudget:
    """Test the budget class with no renewable period."""

    def test_matches_operation_within_budget(self, budget_no_period: Budget) -> None:
        """Test that the budget matches operations within the budget."""
        for operation_date in (
            datetime(2023, 1, 15),
            datetime(2023, 1, 30),
            datetime(2023, 1, 1),
        ):
            historic_operation = HistoricOperation(
                unique_id=1,
                description="Test Operation",
                amount=Amount(-100.0),
                category=budget_no_period.category,
                date=operation_date,
            )
            assert budget_no_period.matcher.match(historic_operation)

    def test_matches_operation_outside_budget(self, budget_no_period: Budget) -> None:
        """Test that the budget does not match operations outside the budget."""
        for operation_date in (datetime(2023, 2, 1), datetime(2022, 12, 30)):
            historic_operation = HistoricOperation(
                unique_id=1,
                description="Test Operation",
                amount=Amount(-100.0),
                category=budget_no_period.category,
                date=operation_date,
            )
            assert not budget_no_period.matcher.match(historic_operation)

    def test_matches_different_category(self, budget_no_period: Budget) -> None:
        """Test that the budget does not match operations with different categories."""
        operation_date = datetime(2023, 1, 15)
        historic_operation = HistoricOperation(
            unique_id=1,
            description="Test Operation",
            amount=Amount(-100.0),
            category=Category.OTHER,
            date=operation_date,
        )
        assert not budget_no_period.matcher.match(historic_operation)

    def test_amount_on_period(self, budget_no_period: Budget) -> None:
        """Test the amount on period for a budget with no renewable period."""
        for date_start, date_end, expected_amount in (
            (datetime(2023, 1, 1), datetime(2023, 1, 31), -200.0),
            (datetime(2022, 12, 1), datetime(2023, 2, 15), -200.0),
            (datetime(2023, 2, 1), datetime(2023, 2, 15), 0.0),
            (datetime(2023, 1, 1), datetime(2023, 1, 15), -100.0),
            (datetime(2023, 1, 16), datetime(2023, 1, 30), -100.0),
        ):
            amount = budget_no_period.amount_on_period(date_start, date_end)
            assert amount == pytest.approx(
                expected_amount
            ), f"Expected {expected_amount} but got {amount} on period {date_start} - {date_end}"


class TestBudgetReplaceTypeErrors:
    """Tests for TypeError when passing invalid types to Budget.replace()."""

    @pytest.fixture
    def budget(self) -> Budget:
        """Create a budget for testing."""
        return Budget(
            record_id=1,
            description="Test Budget",
            amount=Amount(-100.0),
            category=Category.GROCERIES,
            time_range=TimeRange(datetime(2023, 1, 1), relativedelta(months=1)),
        )

    def test_replace_invalid_record_id(self, budget: Budget) -> None:
        """Test Budget.replace() raises TypeError for invalid record_id."""
        with pytest.raises(TypeError, match="record_id must be int or None"):
            budget.replace(record_id="1")

    def test_replace_invalid_description(self, budget: Budget) -> None:
        """Test Budget.replace() raises TypeError for invalid description."""
        with pytest.raises(TypeError, match="description must be str"):
            budget.replace(description=123)

    def test_replace_invalid_amount(self, budget: Budget) -> None:
        """Test Budget.replace() raises TypeError for invalid amount."""
        with pytest.raises(TypeError, match="amount must be Amount"):
            budget.replace(amount=-100.0)

    def test_replace_invalid_category(self, budget: Budget) -> None:
        """Test Budget.replace() raises TypeError for invalid category."""
        with pytest.raises(TypeError, match="category must be Category"):
            budget.replace(category="GROCERIES")

    def test_replace_invalid_time_range(self, budget: Budget) -> None:
        """Test Budget.replace() raises TypeError for invalid time_range."""
        with pytest.raises(TypeError, match="time_range must be TimeRangeInterface"):
            budget.replace(time_range="2023-01-01")


class TestBudgetSplitAt:
    """Tests for Budget.split_at() method."""

    def test_split_at_returns_terminated_and_continuation(self) -> None:
        """Test split_at returns two Budgets."""
        budget = Budget(
            record_id=1,
            description="Groceries",
            amount=Amount(-400.0),
            category=Category.GROCERIES,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
                relativedelta(months=1),
                datetime(2025, 12, 31),
            ),
        )

        terminated, continuation = budget.split_at(datetime(2025, 6, 1))

        # Terminated ends day before first new iteration (June 1)
        assert terminated.time_range.last_date == datetime(2025, 5, 31)
        assert terminated.id == 1  # Keeps original ID

        # Continuation starts at first iteration >= split date
        assert continuation.time_range.initial_date == datetime(2025, 6, 1)
        assert continuation.id is None  # New record
        assert continuation.description == "Groceries"
        assert continuation.amount == -400.0
        assert continuation.category == Category.GROCERIES

    def test_split_at_with_new_amount(self) -> None:
        """Test split_at with new amount for continuation."""
        budget = Budget(
            record_id=1,
            description="Groceries",
            amount=Amount(-400.0),
            category=Category.GROCERIES,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
                relativedelta(months=1),
            ),
        )

        _, continuation = budget.split_at(
            datetime(2025, 6, 1), new_amount=Amount(-500.0)
        )

        assert continuation.amount == -500.0

    def test_split_at_with_new_period(self) -> None:
        """Test split_at with new period for continuation."""
        budget = Budget(
            record_id=1,
            description="Groceries",
            amount=Amount(-400.0),
            category=Category.GROCERIES,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
                relativedelta(months=1),
            ),
        )

        _, continuation = budget.split_at(
            datetime(2025, 6, 1), new_period=relativedelta(months=3)
        )

        assert continuation.time_range.period == relativedelta(months=3)

    def test_split_at_with_new_duration(self) -> None:
        """Test split_at with new duration for continuation."""
        budget = Budget(
            record_id=1,
            description="Groceries",
            amount=Amount(-400.0),
            category=Category.GROCERIES,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
                relativedelta(months=1),
            ),
        )

        _, continuation = budget.split_at(
            datetime(2025, 6, 1), new_duration=relativedelta(months=2)
        )

        assert continuation.time_range.duration == relativedelta(months=2)

    def test_split_at_non_periodic_raises_error(self) -> None:
        """Test split_at raises ValueError for non-periodic budget."""
        budget = Budget(
            record_id=1,
            description="One-time",
            amount=Amount(-100.0),
            category=Category.OTHER,
            time_range=TimeRange(datetime(2025, 1, 1), relativedelta(months=1)),
        )

        with pytest.raises(ValueError, match="Cannot split a non-periodic"):
            budget.split_at(datetime(2025, 6, 1))
