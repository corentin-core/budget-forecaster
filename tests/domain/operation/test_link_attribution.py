"""Tests for the month in which a linked operation counts."""

from datetime import date

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import DateRange
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.link_attribution import linked_month
from budget_forecaster.domain.operation.operation_link import OperationLink

_HOLIDAYS = Budget(
    record_id=1,
    description="Holidays",
    amount=Amount(-1000.0),
    category=Category.LEISURE,
    date_range=DateRange(date(2025, 7, 1), relativedelta(months=2)),
)


def _link(target_type: LinkType, target_id: int = 1) -> OperationLink:
    return OperationLink(
        operation_unique_id=1,
        target_type=target_type,
        target_id=target_id,
        iteration_date=date(2025, 7, 1),
    )


def test_planned_operation_counts_in_its_due_month() -> None:
    """A late payment of a planned operation counts in the month it was due."""
    month = linked_month(
        _link(LinkType.PLANNED_OPERATION), date(2025, 8, 3), (_HOLIDAYS,)
    )

    assert month == date(2025, 7, 1)


@pytest.mark.parametrize(
    ("operation_date", "expected"),
    [
        (date(2025, 8, 10), date(2025, 8, 1)),
        (date(2025, 6, 28), date(2025, 7, 1)),
        (date(2025, 9, 2), date(2025, 8, 1)),
    ],
    ids=["inside the period", "before the period", "after the period"],
)
def test_budget_operation_counts_in_its_month_within_the_period(
    operation_date: date, expected: date
) -> None:
    """A budget operation counts in its own month, clamped into the period."""
    assert (
        linked_month(_link(LinkType.BUDGET), operation_date, (_HOLIDAYS,)) == expected
    )


def test_unknown_budget_counts_in_the_operation_month() -> None:
    """Without its budget, an operation counts in its own month."""
    month = linked_month(_link(LinkType.BUDGET, target_id=99), date(2025, 9, 2), ())

    assert month == date(2025, 9, 1)
