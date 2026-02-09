"""Tests for the categorize_operations function."""
from datetime import date

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDay, SingleDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.operation.operations_categorizer import (
    categorize_operations,
)


def _make_operation(
    unique_id: int = 1,
    description: str = "SUPERMARKET CARREFOUR",
    amount: float = -85.20,
    category: Category = Category.OTHER,
    operation_date: date = date(2025, 1, 15),
) -> HistoricOperation:
    return HistoricOperation(
        unique_id=unique_id,
        description=description,
        amount=Amount(amount, "EUR"),
        category=category,
        operation_date=operation_date,
    )


def _make_planned(
    record_id: int = 1,
    amount: float = -85.20,
    category: Category = Category.GROCERIES,
    start_date: date = date(2025, 1, 15),
    recurrence: relativedelta | None = relativedelta(months=1),
    hints: set[str] | None = None,
) -> PlannedOperation:
    if recurrence is not None:
        date_range = RecurringDay(start_date, recurrence)
    else:
        date_range = SingleDay(start_date)
    planned = PlannedOperation(
        record_id=record_id,
        description="Planned operation",
        amount=Amount(amount, "EUR"),
        category=category,
        date_range=date_range,
    )
    if hints is not None:
        planned = planned.set_matcher_params(description_hints=hints)
    return planned


class TestCategorizeOperations:
    """Tests for the categorize_operations function."""

    def test_matching_operation_gets_categorized(self) -> None:
        """Operation matching description, amount, and date gets the planned category."""
        operation = _make_operation(
            description="SUPERMARKET CARREFOUR",
            amount=-85.20,
            category=Category.OTHER,
            operation_date=date(2025, 1, 15),
        )
        planned = _make_planned(
            amount=-85.20,
            category=Category.GROCERIES,
            start_date=date(2025, 1, 15),
            hints={"CARREFOUR"},
        )
        forecast = Forecast(operations=(planned,), budgets=())

        result = categorize_operations([operation], forecast)

        assert result[0].category == Category.GROCERIES

    def test_empty_operations_returns_empty_tuple(self) -> None:
        """Empty input returns an empty tuple."""
        planned = _make_planned(hints={"CARREFOUR"})
        forecast = Forecast(operations=(planned,), budgets=())

        result = categorize_operations([], forecast)

        assert not result

    def test_empty_forecast_leaves_categories_unchanged(self) -> None:
        """No planned operations means all categories stay as-is."""
        operation = _make_operation(category=Category.OTHER)
        forecast = Forecast(operations=(), budgets=())

        result = categorize_operations([operation], forecast)

        assert result[0].category == Category.OTHER

    def test_no_description_match_skips_categorization(self) -> None:
        """Operation not matching description hints is not categorized."""
        operation = _make_operation(
            description="PHARMACY LECLERC",
            amount=-85.20,
            operation_date=date(2025, 1, 15),
        )
        planned = _make_planned(
            amount=-85.20,
            category=Category.GROCERIES,
            start_date=date(2025, 1, 1),
            hints={"CARREFOUR"},
        )
        forecast = Forecast(operations=(planned,), budgets=())

        result = categorize_operations([operation], forecast)

        assert result[0].category == Category.OTHER

    def test_amount_mismatch_skips_categorization(self) -> None:
        """Operation with different amount is not categorized."""
        operation = _make_operation(
            description="SUPERMARKET CARREFOUR",
            amount=-200.00,
            operation_date=date(2025, 1, 15),
        )
        planned = _make_planned(
            amount=-85.20,
            category=Category.GROCERIES,
            start_date=date(2025, 1, 1),
            hints={"CARREFOUR"},
        )
        forecast = Forecast(operations=(planned,), budgets=())

        result = categorize_operations([operation], forecast)

        assert result[0].category == Category.OTHER

    def test_date_range_mismatch_skips_categorization(self) -> None:
        """Operation outside the planned date range is not categorized."""
        operation = _make_operation(
            description="SUPERMARKET CARREFOUR",
            amount=-85.20,
            operation_date=date(2024, 6, 15),
        )
        planned = _make_planned(
            amount=-85.20,
            category=Category.GROCERIES,
            start_date=date(2025, 1, 1),
            recurrence=None,
            hints={"CARREFOUR"},
        )
        forecast = Forecast(operations=(planned,), budgets=())

        result = categorize_operations([operation], forecast)

        assert result[0].category == Category.OTHER

    def test_first_matching_planned_operation_wins(self) -> None:
        """When multiple planned operations match, the first one assigns its category."""
        operation = _make_operation(
            description="CARREFOUR MARKET",
            amount=-50.00,
            operation_date=date(2025, 1, 15),
        )
        first_planned = _make_planned(
            record_id=1,
            amount=-50.00,
            category=Category.GROCERIES,
            start_date=date(2025, 1, 15),
            hints={"CARREFOUR"},
        )
        second_planned = _make_planned(
            record_id=2,
            amount=-50.00,
            category=Category.OTHER,
            start_date=date(2025, 1, 15),
            hints={"CARREFOUR"},
        )
        forecast = Forecast(operations=(first_planned, second_planned), budgets=())

        result = categorize_operations([operation], forecast)

        assert result[0].category == Category.GROCERIES

    def test_planned_without_hints_never_matches(self) -> None:
        """Planned operation without description hints never matches."""
        operation = _make_operation(
            description="ANYTHING",
            amount=-85.20,
            operation_date=date(2025, 1, 15),
        )
        planned = _make_planned(
            amount=-85.20,
            category=Category.GROCERIES,
            start_date=date(2025, 1, 1),
            hints=None,
        )
        forecast = Forecast(operations=(planned,), budgets=())

        result = categorize_operations([operation], forecast)

        assert result[0].category == Category.OTHER

    def test_amount_within_tolerance_matches(self) -> None:
        """Amount within the default 5% approximation tolerance matches."""
        # Planned: -100.00, tolerance 5% => [-105.00, -95.00]
        # Operation: -103.00 => within tolerance
        operation = _make_operation(
            description="SUPERMARKET CARREFOUR",
            amount=-103.00,
            operation_date=date(2025, 1, 15),
        )
        planned = _make_planned(
            amount=-100.00,
            category=Category.GROCERIES,
            start_date=date(2025, 1, 15),
            hints={"CARREFOUR"},
        )
        forecast = Forecast(operations=(planned,), budgets=())

        result = categorize_operations([operation], forecast)

        assert result[0].category == Category.GROCERIES

    def test_amount_outside_tolerance_does_not_match(self) -> None:
        """Amount outside the 5% tolerance does not match."""
        # Planned: -100.00, tolerance 5% => [-105.00, -95.00]
        # Operation: -110.00 => outside tolerance
        operation = _make_operation(
            description="SUPERMARKET CARREFOUR",
            amount=-110.00,
            operation_date=date(2025, 1, 15),
        )
        planned = _make_planned(
            amount=-100.00,
            category=Category.GROCERIES,
            start_date=date(2025, 1, 1),
            hints={"CARREFOUR"},
        )
        forecast = Forecast(operations=(planned,), budgets=())

        result = categorize_operations([operation], forecast)

        assert result[0].category == Category.OTHER

    def test_mixed_operations_some_match_some_not(self) -> None:
        """Only operations matching planned criteria get categorized."""
        matching_op = _make_operation(
            unique_id=1,
            description="SUPERMARKET CARREFOUR",
            amount=-85.20,
            category=Category.OTHER,
            operation_date=date(2025, 1, 15),
        )
        non_matching_op = _make_operation(
            unique_id=2,
            description="RESTAURANT CHEZ PAUL",
            amount=-42.00,
            category=Category.OTHER,
            operation_date=date(2025, 1, 20),
        )
        planned = _make_planned(
            amount=-85.20,
            category=Category.GROCERIES,
            start_date=date(2025, 1, 15),
            hints={"CARREFOUR"},
        )
        forecast = Forecast(operations=(planned,), budgets=())

        result = categorize_operations([matching_op, non_matching_op], forecast)
        categories = {op.unique_id: op.category for op in result}

        assert categories == {
            1: Category.GROCERIES,
            2: Category.OTHER,
        }

    def test_date_within_approximation_range_matches(self) -> None:
        """Operation date slightly outside the exact range but within approximation matches."""
        # SingleDay on Jan 15, default approximation is 5 days
        # Operation on Jan 18 should match (within 5 days)
        operation = _make_operation(
            description="SUPERMARKET CARREFOUR",
            amount=-85.20,
            operation_date=date(2025, 1, 18),
        )
        planned = _make_planned(
            amount=-85.20,
            category=Category.GROCERIES,
            start_date=date(2025, 1, 15),
            recurrence=None,
            hints={"CARREFOUR"},
        )
        forecast = Forecast(operations=(planned,), budgets=())

        result = categorize_operations([operation], forecast)

        assert result[0].category == Category.GROCERIES

    def test_preserves_operation_order(self) -> None:
        """Returned operations maintain the same order as input."""
        ops = [
            _make_operation(unique_id=i, operation_date=date(2025, 1, i + 1))
            for i in range(1, 6)
        ]
        forecast = Forecast(operations=(), budgets=())

        result = categorize_operations(ops, forecast)

        assert tuple(op.unique_id for op in result) == (1, 2, 3, 4, 5)
