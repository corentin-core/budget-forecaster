"""Tests for the split of each month's gap to the plan into causes."""

from datetime import date

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
)
from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.forecast.plan_gaps import (
    GapCause,
    GapItem,
    compute_plan_gaps,
)

_JULY, _AUGUST = date(2026, 7, 1), date(2026, 8, 1)
_MONTHS = (_JULY, _AUGUST)


def _op(
    op_id: int, day: date, amount: float, category: Category = Category.GROCERIES
) -> HistoricOperation:
    return HistoricOperation(
        unique_id=op_id,
        description=f"OP {op_id}",
        amount=Amount(amount, "EUR"),
        category=category,
        operation_date=day,
    )


def _link(op_id: int, kind: LinkType, target_id: int, iteration: date) -> OperationLink:
    return OperationLink(
        operation_unique_id=op_id,
        target_type=kind,
        target_id=target_id,
        iteration_date=iteration,
    )


def _budget(months_per_period: int = 1, amount: float = -400.0) -> Budget:
    return Budget(
        record_id=1,
        description="Groceries",
        amount=Amount(amount, "EUR"),
        category=Category.GROCERIES,
        date_range=RecurringDateRange(
            DateRange(_JULY, relativedelta(months=months_per_period)),
            relativedelta(months=months_per_period),
        ),
    )


def _electricity() -> PlannedOperation:
    return PlannedOperation(
        record_id=2,
        description="Electricity",
        amount=Amount(-85.0, "EUR"),
        category=Category.ELECTRICITY,
        date_range=RecurringDay(date(2026, 7, 5), relativedelta(months=1)),
    )


def _only(items: tuple[GapItem, ...], cause: GapCause) -> GapItem:
    (item,) = (item for item in items if item.cause is cause)
    return item


class TestCauses:
    """Each cause takes its own share of the gap."""

    def test_budget_overspent(self) -> None:
        """Operations linked to a budget, against its amount, month by month."""
        gaps = compute_plan_gaps(
            (_op(1, date(2026, 7, 10), -470.0), _op(2, date(2026, 8, 10), -380.0)),
            Forecast(operations=(), budgets=(_budget(),)),
            (
                _link(1, LinkType.BUDGET, 1, _JULY),
                _link(2, LinkType.BUDGET, 1, _AUGUST),
            ),
            _MONTHS,
        )

        budget = _only(gaps.items, GapCause.BUDGET)
        assert budget.gaps == (-70.0, 20.0)
        assert budget.operation_count == 2
        assert gaps.average() == -25.0

    def test_planned_operation_paid_at_another_amount_or_not_paid(self) -> None:
        """A paid occurrence counts its difference, an unpaid one its whole amount."""
        gaps = compute_plan_gaps(
            (_op(1, date(2026, 7, 6), -110.0, Category.ELECTRICITY),),
            Forecast(operations=(_electricity(),), budgets=()),
            (_link(1, LinkType.PLANNED_OPERATION, 2, date(2026, 7, 5)),),
            _MONTHS,
        )

        assert _only(gaps.items, GapCause.OTHER_AMOUNT).gaps == (-25.0, 0.0)
        unpaid = _only(gaps.items, GapCause.NOT_PAID)
        assert unpaid.gaps == (0.0, 85.0)
        assert unpaid.missed == (date(2026, 8, 5),)

    def test_payment_late_counts_in_the_month_of_its_occurrence(self) -> None:
        """A July occurrence paid on August 2nd is a July payment."""
        gaps = compute_plan_gaps(
            (_op(1, date(2026, 8, 2), -85.0, Category.ELECTRICITY),),
            Forecast(operations=(_electricity(),), budgets=()),
            (_link(1, LinkType.PLANNED_OPERATION, 2, date(2026, 7, 5)),),
            _MONTHS,
        )

        assert [item.cause for item in gaps.items] == [GapCause.NOT_PAID]
        assert gaps.month_totals() == (0.0, 85.0)

    def test_unlinked_operations_by_category_and_sign(self) -> None:
        """Unlinked spending and income are unplanned, per category."""
        gaps = compute_plan_gaps(
            (
                _op(1, date(2026, 7, 3), -40.0, Category.HEALTH_CARE),
                _op(2, date(2026, 8, 3), -20.0, Category.HEALTH_CARE),
                _op(3, date(2026, 8, 9), 30.0, Category.HEALTH_CARE),
            ),
            Forecast(operations=(), budgets=()),
            (),
            _MONTHS,
        )

        spent = _only(gaps.items, GapCause.UNPLANNED_EXPENSE)
        assert (spent.category, spent.gaps, spent.operation_count) == (
            Category.HEALTH_CARE,
            (-40.0, -20.0),
            2,
        )
        assert _only(gaps.items, GapCause.UNPLANNED_INCOME).gaps == (0.0, 30.0)

    def test_link_to_a_deleted_target_is_unplanned(self) -> None:
        """An operation whose target is gone counts as unplanned."""
        gaps = compute_plan_gaps(
            (_op(1, date(2026, 7, 6), -60.0),),
            Forecast(operations=(), budgets=()),
            (_link(1, LinkType.BUDGET, 99, _JULY),),
            _MONTHS,
        )

        assert _only(gaps.items, GapCause.UNPLANNED_EXPENSE).gaps == (-60.0, 0.0)

    def test_on_plan_items_are_left_out(self) -> None:
        """An item with no gap over the window is not listed."""
        gaps = compute_plan_gaps(
            (
                _op(1, date(2026, 7, 6), -85.0, Category.ELECTRICITY),
                _op(2, date(2026, 8, 6), -85.0, Category.ELECTRICITY),
            ),
            Forecast(operations=(_electricity(),), budgets=()),
            (
                _link(1, LinkType.PLANNED_OPERATION, 2, date(2026, 7, 5)),
                _link(2, LinkType.PLANNED_OPERATION, 2, date(2026, 8, 5)),
            ),
            _MONTHS,
        )

        assert not gaps.items

    def test_multi_month_budget(self) -> None:
        """A two-month budget plans half of its amount in each month."""
        gaps = compute_plan_gaps(
            (_op(1, date(2026, 7, 20), -900.0),),
            Forecast(operations=(), budgets=(_budget(2, -1000.0),)),
            (_link(1, LinkType.BUDGET, 1, _JULY),),
            _MONTHS,
        )

        budget = _only(gaps.items, GapCause.BUDGET)
        assert budget.planned == (-500.0, -500.0)
        assert round(budget.total) == 100
