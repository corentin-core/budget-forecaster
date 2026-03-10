"""Tests for creating planned operations from historic operations."""

# pylint: disable=protected-access,too-few-public-methods

from datetime import date

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import SingleDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.tui.modals.planned_operation_edit import (
    PlannedOperationEditModal,
)


def _make_operation(
    unique_id: int = 1,
    description: str = "NETFLIX",
    amount: float = -17.99,
    category: Category = Category.ENTERTAINMENT,
    op_date: date | None = None,
) -> HistoricOperation:
    """Create a test operation."""
    return HistoricOperation(
        unique_id=unique_id,
        operation_date=op_date or date(2025, 1, 15),
        description=description,
        amount=Amount(amount, "EUR"),
        category=category,
    )


class TestPlanOperationEditModalIsNew:
    """Tests for _is_new logic with pre-filled operations."""

    def test_is_new_when_no_operation(self) -> None:
        """Modal is new when no operation is passed."""
        modal = PlannedOperationEditModal(operation=None)
        assert modal._is_new is True

    def test_is_new_when_operation_has_no_id(self) -> None:
        """Modal is new when operation has no record_id (pre-filled from historic)."""
        prefilled = PlannedOperation(
            record_id=None,
            description="NETFLIX",
            amount=Amount(-17.99, "EUR"),
            category=Category.ENTERTAINMENT,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        modal = PlannedOperationEditModal(operation=prefilled)
        assert modal._is_new is True

    def test_is_not_new_when_operation_has_id(self) -> None:
        """Modal is not new when editing an existing operation."""
        existing = PlannedOperation(
            record_id=42,
            description="NETFLIX",
            amount=Amount(-17.99, "EUR"),
            category=Category.ENTERTAINMENT,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        modal = PlannedOperationEditModal(operation=existing)
        assert modal._is_new is False


class TestPrefilledPlannedOperation:
    """Tests for building a pre-filled PlannedOperation from HistoricOperation."""

    def test_prefilled_operation_has_correct_fields(self) -> None:
        """Pre-filled operation copies description, amount, category, date."""
        historic = _make_operation(
            description="NETFLIX",
            amount=-17.99,
            category=Category.ENTERTAINMENT,
            op_date=date(2025, 1, 15),
        )

        prefilled = PlannedOperation(
            record_id=None,
            description=historic.description,
            amount=Amount(historic.amount, historic.currency),
            category=historic.category,
            date_range=SingleDay(historic.operation_date),
        )

        assert prefilled.id is None
        assert prefilled.description == "NETFLIX"
        assert prefilled.amount == -17.99
        assert prefilled.category == Category.ENTERTAINMENT
        assert prefilled.date_range.start_date == date(2025, 1, 15)
