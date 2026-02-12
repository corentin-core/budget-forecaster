"""Module with tests for the OperationRange class."""
from datetime import date, timedelta

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import DateRange, RecurringDateRange
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.operation_range import OperationRange


@pytest.fixture
def operation_range() -> OperationRange:
    """Fixture to create an OperationRange object."""
    return OperationRange(
        "Test Operation",
        Amount(100, "EUR"),
        Category.GROCERIES,
        DateRange(date(2023, 1, 1), relativedelta(days=30)),
    )


class TestOperationRange:
    """Tests for the OperationRange class."""

    def test_amount_on_period_full_period(
        self, operation_range: OperationRange
    ) -> None:
        """Test the amount_on_period method for a full period."""
        assert (
            operation_range.amount_on_period(date(2023, 1, 1), date(2023, 1, 31))
            == 100.0
        )

    def test_amount_on_period_partial_period(
        self, operation_range: OperationRange
    ) -> None:
        """Test the amount_on_period method for a partial period."""
        assert (
            operation_range.amount_on_period(date(2022, 12, 15), date(2023, 1, 15))
            == 50.0
        )
        assert (
            operation_range.amount_on_period(date(2023, 1, 16), date(2023, 2, 15))
            == 50.0
        )

    def test_amount_on_period_no_overlap(self, operation_range: OperationRange) -> None:
        """Test the amount_on_period method for a period with no overlap."""
        assert (
            operation_range.amount_on_period(date(2023, 2, 1), date(2023, 2, 28)) == 0.0
        )

    def test_amount_on_period_future_period(
        self, operation_range: OperationRange
    ) -> None:
        """Test the amount_on_period method for a future period."""
        assert (
            operation_range.amount_on_period(date(2023, 12, 1), date(2023, 12, 31))
            == 0.0
        )

    def test_amount_on_period_expired_period(
        self, operation_range: OperationRange
    ) -> None:
        """Test the amount_on_period method for an expired period."""
        assert (
            operation_range.amount_on_period(date(2022, 12, 1), date(2022, 12, 31))
            == 0.0
        )

    def test_replace_with_new_description(
        self, operation_range: OperationRange
    ) -> None:
        """Test the replace method with a new description."""
        new_operation_range = operation_range.replace(description="New Description")
        assert new_operation_range.description == "New Description"
        assert new_operation_range.amount == 100.0
        assert new_operation_range.category == Category.GROCERIES
        assert new_operation_range.date_range == operation_range.date_range

    def test_replace_with_new_amount(self, operation_range: OperationRange) -> None:
        """Test the replace method with a new amount."""
        new_operation_range = operation_range.replace(amount=Amount(200, "EUR"))
        assert new_operation_range.description == "Test Operation"
        assert new_operation_range.amount == 200.0
        assert new_operation_range.category == Category.GROCERIES
        assert new_operation_range.date_range == operation_range.date_range


@pytest.fixture
def periodic_operation_range() -> OperationRange:
    """Fixture to create a PeriodicOperationRange object."""
    return OperationRange(
        "Test Operation",
        Amount(100, "EUR"),
        Category.GROCERIES,
        RecurringDateRange(
            DateRange(date(2023, 1, 1), relativedelta(months=1)),
            relativedelta(months=1),
            date(2023, 12, 31),
        ),
    )


class TestPeriodicOperationRange:
    """Tests for the PeriodicOperationRange class."""

    def test_amount_on_period_full_period(
        self, periodic_operation_range: OperationRange
    ) -> None:
        """Test the amount_on_period method for a full period."""
        for month in range(1, 12):
            assert (
                periodic_operation_range.amount_on_period(
                    date(2023, 1, 1),
                    date(2023, month + 1, 1) - timedelta(days=1),
                )
                == 100.0 * month
            )

    def test_amount_on_period_partial_period(
        self, periodic_operation_range: OperationRange
    ) -> None:
        """Test the amount_on_period method for a partial period."""
        assert (
            periodic_operation_range.amount_on_period(
                date(2023, 4, 1), date(2023, 4, 15)
            )
            == 50.0
        )
        assert (
            periodic_operation_range.amount_on_period(
                date(2023, 4, 16), date(2023, 4, 30)
            )
            == 50.0
        )

    def test_amount_on_period_future_period(
        self, periodic_operation_range: OperationRange
    ) -> None:
        """Test the amount_on_period method for a future period."""
        assert (
            periodic_operation_range.amount_on_period(
                date(2024, 1, 1), date(2024, 1, 31)
            )
            == 0.0
        )

    def test_amount_on_period_expired_period(
        self, periodic_operation_range: OperationRange
    ) -> None:
        """Test the amount_on_period method for an expired period."""
        assert (
            periodic_operation_range.amount_on_period(
                date(2022, 12, 1), date(2022, 12, 31)
            )
            == 0.0
        )

    def test_replace_with_new_description(
        self, periodic_operation_range: OperationRange
    ) -> None:
        """Test the replace method with a new description."""
        new_operation_range = periodic_operation_range.replace(
            description="New Description"
        )
        assert new_operation_range.description == "New Description"
        assert new_operation_range.amount == 100.0
        assert new_operation_range.category == Category.GROCERIES
        assert new_operation_range.date_range == periodic_operation_range.date_range

    def test_replace_with_new_amount(
        self, periodic_operation_range: OperationRange
    ) -> None:
        """Test the replace method with a new amount."""
        new_operation_range = periodic_operation_range.replace(
            amount=Amount(200, "EUR")
        )
        assert new_operation_range.description == "Test Operation"
        assert new_operation_range.amount == 200.0
        assert new_operation_range.category == Category.GROCERIES
        assert new_operation_range.date_range == periodic_operation_range.date_range


class TestOperationRangeErrors:
    """Tests for errors and edge cases in OperationRange methods."""

    def test_repr_contains_description_and_amount(self) -> None:
        """repr includes description, category, and amount."""
        op = OperationRange(
            "Grocery Shopping",
            Amount(100, "EUR"),
            Category.GROCERIES,
            DateRange(date(2023, 1, 1), relativedelta(days=30)),
        )
        assert repr(op) == (
            "2023-01-01 - 2023-01-30 - Courses - Grocery Shopping - 100 EUR"
        )

    @pytest.fixture
    def operation_range(self) -> OperationRange:
        """Create an OperationRange for testing."""
        return OperationRange(
            "Test Operation",
            Amount(100, "EUR"),
            Category.GROCERIES,
            DateRange(date(2023, 1, 1), relativedelta(days=30)),
        )

    def test_amount_on_period_invalid_date_order(
        self, operation_range: OperationRange
    ) -> None:
        """Test amount_on_period raises ValueError when start_date > end_date."""
        with pytest.raises(ValueError, match="start_date must be <= end_date"):
            operation_range.amount_on_period(date(2023, 1, 31), date(2023, 1, 1))

    def test_replace_invalid_description(self, operation_range: OperationRange) -> None:
        """Test replace() raises TypeError for invalid description."""
        with pytest.raises(TypeError, match="description must be str"):
            operation_range.replace(description=123)

    def test_replace_invalid_amount(self, operation_range: OperationRange) -> None:
        """Test replace() raises TypeError for invalid amount."""
        with pytest.raises(TypeError, match="amount must be Amount"):
            operation_range.replace(amount=100.0)

    def test_replace_invalid_category(self, operation_range: OperationRange) -> None:
        """Test replace() raises TypeError for invalid category."""
        with pytest.raises(TypeError, match="category must be Category"):
            operation_range.replace(category="GROCERIES")

    def test_replace_invalid_time_range(self, operation_range: OperationRange) -> None:
        """Test replace() raises TypeError for invalid time_range."""
        with pytest.raises(TypeError, match="date_range must be DateRangeInterface"):
            operation_range.replace(date_range="2023-01-01")
