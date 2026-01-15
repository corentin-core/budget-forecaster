"""Module with tests for the budget class."""
from datetime import datetime

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.time_range import PeriodicTimeRange, TimeRange
from budget_forecaster.types import Category


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
