"""Tests for the upcoming planned operations on the dashboard."""

from datetime import date

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay, SingleDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.application_service import (
    UpcomingIteration,
    get_upcoming_iterations,
)
from budget_forecaster.tui.screens.dashboard import format_period


def _make_recurring_op(
    record_id: int,
    description: str,
    amount: float,
    start_date: date,
    period: relativedelta,
    end_date: date | None = None,
) -> PlannedOperation:
    """Create a recurring planned operation for testing."""
    return PlannedOperation(
        record_id=record_id,
        description=description,
        amount=Amount(amount, "EUR"),
        category=Category.GROCERIES,
        date_range=RecurringDay(start_date, period, end_date),
    )


def _make_single_op(
    record_id: int,
    description: str,
    amount: float,
    op_date: date,
) -> PlannedOperation:
    """Create a one-time planned operation for testing."""
    return PlannedOperation(
        record_id=record_id,
        description=description,
        amount=Amount(amount, "EUR"),
        category=Category.GROCERIES,
        date_range=SingleDay(op_date),
    )


class TestGetUpcomingIterations:
    """Tests for get_upcoming_iterations function."""

    def test_empty_when_no_operations(self) -> None:
        """Return empty tuple when no planned operations exist."""
        result = get_upcoming_iterations((), date(2025, 3, 1))
        assert not result

    def test_recurring_operation_within_horizon(self) -> None:
        """Include next iteration of a recurring operation within 30 days."""
        op = _make_recurring_op(
            1, "Rent", -850.0, date(2025, 1, 1), relativedelta(months=1)
        )
        result = get_upcoming_iterations(
            (op,), reference_date=date(2025, 3, 1), horizon_days=30
        )
        assert result == (
            UpcomingIteration(
                iteration_date=date(2025, 3, 1),
                description="Rent",
                amount=-850.0,
                currency="EUR",
                period=relativedelta(months=1),
            ),
        )

    def test_recurring_operation_multiple_iterations(self) -> None:
        """Include all weekly iterations that fall within the 30-day window."""
        op = _make_recurring_op(
            1, "Weekly", -50.0, date(2025, 1, 6), relativedelta(weeks=1)
        )
        result = get_upcoming_iterations(
            (op,), reference_date=date(2025, 3, 1), horizon_days=30
        )
        # Expect 4-5 weekly iterations in a 30-day window
        assert len(result) >= 4
        assert all(it.description == "Weekly" for it in result)
        assert all(
            date(2025, 3, 1) <= it.iteration_date <= date(2025, 3, 31) for it in result
        )

    def test_single_day_operation_in_range(self) -> None:
        """Include a one-time operation whose date falls within the horizon."""
        op = _make_single_op(1, "One-time", -200.0, date(2025, 3, 15))
        result = get_upcoming_iterations(
            (op,), reference_date=date(2025, 3, 1), horizon_days=30
        )
        assert result == (
            UpcomingIteration(
                iteration_date=date(2025, 3, 15),
                description="One-time",
                amount=-200.0,
                currency="EUR",
                period=None,
            ),
        )

    def test_single_day_operation_before_reference_excluded(self) -> None:
        """Exclude a one-time operation whose date is before the reference date."""
        op = _make_single_op(1, "Past", -100.0, date(2025, 2, 1))
        result = get_upcoming_iterations(
            (op,), reference_date=date(2025, 3, 1), horizon_days=30
        )
        assert not result

    def test_single_day_operation_beyond_horizon_excluded(self) -> None:
        """Exclude a one-time operation whose date is beyond the 30-day horizon."""
        op = _make_single_op(1, "Far future", -100.0, date(2025, 5, 1))
        result = get_upcoming_iterations(
            (op,), reference_date=date(2025, 3, 1), horizon_days=30
        )
        assert not result

    def test_sorted_by_date_ascending(self) -> None:
        """Return iterations sorted by date, closest first."""
        ops = (
            _make_single_op(1, "Late", -100.0, date(2025, 3, 20)),
            _make_single_op(2, "Early", -200.0, date(2025, 3, 5)),
            _make_single_op(3, "Middle", -150.0, date(2025, 3, 12)),
        )
        result = get_upcoming_iterations(
            ops, reference_date=date(2025, 3, 1), horizon_days=30
        )
        assert tuple(it.description for it in result) == (
            "Early",
            "Middle",
            "Late",
        )

    def test_expired_recurring_operation_excluded(self) -> None:
        """Exclude a recurring operation that expired before the reference date."""
        op = _make_recurring_op(
            1,
            "Expired",
            -50.0,
            date(2024, 1, 1),
            relativedelta(months=1),
            end_date=date(2025, 2, 1),
        )
        result = get_upcoming_iterations(
            (op,), reference_date=date(2025, 3, 1), horizon_days=30
        )
        assert not result

    def test_mixed_operations(self) -> None:
        """Include only future iterations from a mix of recurring/one-time/past ops."""
        ops = (
            _make_recurring_op(
                1,
                "Monthly rent",
                -850.0,
                date(2025, 1, 1),
                relativedelta(months=1),
            ),
            _make_single_op(2, "One-time purchase", -300.0, date(2025, 3, 10)),
            _make_single_op(3, "Past one-time", -100.0, date(2025, 1, 15)),
        )
        result = get_upcoming_iterations(
            ops, reference_date=date(2025, 3, 1), horizon_days=30
        )
        assert len(result) == 2
        assert result[0].description == "Monthly rent"
        assert result[0].iteration_date == date(2025, 3, 1)
        assert result[1].description == "One-time purchase"
        assert result[1].iteration_date == date(2025, 3, 10)

    def test_reference_date_on_iteration_day_included(self) -> None:
        """An iteration on exactly the reference date should be included."""
        op = _make_recurring_op(
            1, "Rent", -850.0, date(2025, 1, 15), relativedelta(months=1)
        )
        result = get_upcoming_iterations(
            (op,), reference_date=date(2025, 3, 15), horizon_days=30
        )
        assert any(it.iteration_date == date(2025, 3, 15) for it in result)


class TestFormatPeriod:
    """Tests for format_period function."""

    def test_none_returns_dash(self) -> None:
        """Return dash for a non-recurring (None period) operation."""
        assert format_period(None) == "-"

    def test_monthly(self) -> None:
        """Format a 1-month period."""
        assert format_period(relativedelta(months=1)) == "1 mo."

    def test_yearly(self) -> None:
        """Format a 1-year period."""
        assert format_period(relativedelta(years=1)) == "1 yr."

    def test_weekly(self) -> None:
        """Format a 2-week period."""
        assert format_period(relativedelta(weeks=2)) == "2 wk."

    def test_daily(self) -> None:
        """Format a 5-day period."""
        assert format_period(relativedelta(days=5)) == "5 d."

    @pytest.mark.parametrize(
        "period,expected",
        [
            (relativedelta(months=3), "3 mo."),
            (relativedelta(months=6), "6 mo."),
        ],
        ids=["quarterly", "semi-annual"],
    )
    def test_multi_month_periods(self, period: relativedelta, expected: str) -> None:
        """Format multi-month periods (quarterly, semi-annual)."""
        assert format_period(period) == expected
