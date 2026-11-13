"""Why months that are over ended away from the plan.

For each month, actual minus planned is split into causes that add up to it, with
the same attribution as the month view: a linked operation counts in its linked
month, and the plan comes from the current budgets and planned operations.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import NamedTuple

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.types import Category, IterationDate, LinkType
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.link_attribution import linked_month
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation


class GapCause(StrEnum):
    """Why an item ended away from the plan."""

    BUDGET = "budget"
    OTHER_AMOUNT = "other_amount"
    NOT_PAID = "not_paid"
    UNPLANNED_EXPENSE = "unplanned_expense"
    UNPLANNED_INCOME = "unplanned_income"


class GapItem(NamedTuple):
    """A budget, a planned operation or a category, with its monthly figures.

    Each tuple has one value per month of the window, oldest first.
    """

    cause: GapCause
    category: Category
    target: Budget | PlannedOperation | None
    planned: tuple[float, ...]
    actual: tuple[float, ...]
    operation_count: int
    missed: tuple[IterationDate, ...]

    @property
    def gaps(self) -> tuple[float, ...]:
        """Actual minus planned, per month."""
        return tuple(a - p for a, p in zip(self.actual, self.planned))

    @property
    def total(self) -> float:
        """Actual minus planned over the window."""
        return sum(self.actual) - sum(self.planned)


class PlanGaps(NamedTuple):
    """The months compared, and every item away from the plan in them."""

    months: tuple[date, ...]
    items: tuple[GapItem, ...]

    def average(self, items: tuple[GapItem, ...] | None = None) -> float:
        """Average monthly gap of the given items, of all of them by default."""
        if not self.months:
            return 0.0
        chosen = self.items if items is None else items
        return sum(item.total for item in chosen) / len(self.months)

    def month_totals(self) -> tuple[float, ...]:
        """Actual minus planned of each month, all causes together."""
        return tuple(
            sum(item.gaps[index] for item in self.items)
            for index in range(len(self.months))
        )

    def cause_averages(self) -> dict[GapCause, float]:
        """Average monthly gap of each cause, every cause present."""
        return {
            cause: self.average(tuple(i for i in self.items if i.cause is cause))
            for cause in GapCause
        }


def _month_end(month: date) -> date:
    return month + relativedelta(months=1, days=-1)


@dataclass
class _Item:
    """The running figures of one item."""

    cause: GapCause
    category: Category
    target: Budget | PlannedOperation | None
    planned: list[float]
    actual: list[float]
    operation_count: int = 0
    missed: list[IterationDate] = field(default_factory=list)

    def freeze(self) -> GapItem:
        """The finished item."""
        return GapItem(
            cause=self.cause,
            category=self.category,
            target=self.target,
            planned=tuple(self.planned),
            actual=tuple(self.actual),
            operation_count=self.operation_count,
            missed=tuple(sorted(self.missed)),
        )


class _Gaps:
    """Accumulates the figures of each item over the window."""

    def __init__(self, months: tuple[date, ...]) -> None:
        self._index = {month: index for index, month in enumerate(months)}
        self._items: dict[tuple[GapCause, object], _Item] = {}

    def index_of(self, day: date) -> int | None:
        """The window index of the month holding day, None outside the window."""
        return self._index.get(day.replace(day=1))

    def item(
        self,
        cause: GapCause,
        category: Category,
        target: Budget | PlannedOperation | None = None,
    ) -> _Item:
        """The item of a target, or of a category when there is no target."""
        if (key := (cause, target.id if target is not None else category)) not in (
            self._items
        ):
            size = len(self._index)
            self._items[key] = _Item(
                cause, category, target, [0.0] * size, [0.0] * size
            )
        return self._items[key]

    def items(self) -> tuple[GapItem, ...]:
        """The items away from the plan, largest gap first."""
        kept = [
            item.freeze()
            for item in self._items.values()
            if round(sum(item.actual) - sum(item.planned), 2) != 0
        ]
        return tuple(sorted(kept, key=lambda item: abs(item.total), reverse=True))


_Paid = defaultdict[tuple[int, IterationDate], list[HistoricOperation]]


class _Plan(NamedTuple):
    """The stored budgets and planned operations, by id."""

    planned_ops: dict[int, PlannedOperation]
    budgets: dict[int, Budget]
    all_budgets: tuple[Budget, ...]


class _Links(NamedTuple):
    """What the links say about each operation."""

    linked_ids: set[int]
    unplanned_month: dict[int, date]  # linked to a target that is gone
    paid: _Paid


def compute_plan_gaps(
    operations: tuple[HistoricOperation, ...],
    forecast: Forecast,
    links: tuple[OperationLink, ...],
    months: tuple[date, ...],
) -> PlanGaps:
    """Split actual minus planned of each month into its causes.

    Args:
        operations: Every operation of the account.
        forecast: The current budgets and planned operations.
        links: Every operation link.
        months: The first day of each month to compare, oldest first.

    Returns:
        The items away from the plan; their gaps add up to each month's total.
    """
    gaps = _Gaps(months)
    plan = _Plan(
        planned_ops={op.id: op for op in forecast.operations if op.id is not None},
        budgets={b.id: b for b in forecast.budgets if b.id is not None},
        all_budgets=forecast.budgets,
    )
    read = _read_links(gaps, plan, operations, links)
    for index, month in enumerate(months):
        _add_planned_operations(gaps, plan.planned_ops, read.paid, month, index)
        for budget in plan.budgets.values():
            if amount := budget.amount_on_period(month, _month_end(month)):
                gaps.item(GapCause.BUDGET, budget.category, budget).planned[
                    index
                ] += amount

    _add_stale_payments(gaps, plan, read.paid)
    _add_unplanned(gaps, operations, read)
    return PlanGaps(months=months, items=gaps.items())


def _read_links(
    gaps: _Gaps,
    plan: _Plan,
    operations: tuple[HistoricOperation, ...],
    links: tuple[OperationLink, ...],
) -> _Links:
    """Count budget operations in their linked month, and index the rest."""
    by_id = {operation.unique_id: operation for operation in operations}
    read = _Links(set(), {}, defaultdict(list))
    for link in links:
        if (operation := by_id.get(link.operation_unique_id)) is None:
            continue
        month = linked_month(link, operation.operation_date, plan.all_budgets)
        if link.target_type is LinkType.PLANNED_OPERATION and (
            link.target_id in plan.planned_ops
        ):
            read.linked_ids.add(operation.unique_id)
            read.paid[link.target_id, link.iteration_date].append(operation)
        elif link.target_type is LinkType.BUDGET and link.target_id in plan.budgets:
            read.linked_ids.add(operation.unique_id)
            if (index := gaps.index_of(month)) is not None:
                budget = plan.budgets[link.target_id]
                item = gaps.item(GapCause.BUDGET, budget.category, budget)
                item.actual[index] += float(operation.amount)
                item.operation_count += 1
        else:
            read.unplanned_month[operation.unique_id] = month
    return read


def _add_stale_payments(gaps: _Gaps, plan: _Plan, paid: _Paid) -> None:
    """Count payments of occurrences the planned operation no longer has."""
    for (op_id, iteration), operations_paid in paid.items():
        if (index := gaps.index_of(iteration)) is not None:
            planned_op = plan.planned_ops[op_id]
            item = gaps.item(GapCause.OTHER_AMOUNT, planned_op.category, planned_op)
            item.actual[index] += sum(float(op.amount) for op in operations_paid)
            item.operation_count += len(operations_paid)


def _add_unplanned(
    gaps: _Gaps, operations: tuple[HistoricOperation, ...], read: _Links
) -> None:
    """Count every operation no plan covers, by category and sign."""
    for operation in operations:
        if operation.unique_id in read.linked_ids or operation.amount == 0:
            continue
        day = read.unplanned_month.get(operation.unique_id, operation.operation_date)
        if (index := gaps.index_of(day)) is None:
            continue
        cause = (
            GapCause.UNPLANNED_EXPENSE
            if operation.amount < 0
            else GapCause.UNPLANNED_INCOME
        )
        item = gaps.item(cause, operation.category)
        item.actual[index] += float(operation.amount)
        item.operation_count += 1


def _add_planned_operations(
    gaps: _Gaps,
    planned_ops: dict[int, PlannedOperation],
    paid: _Paid,
    month: date,
    index: int,
) -> None:
    """Count each occurrence of the month as paid at its amount or not paid."""
    month_end = _month_end(month)
    for op_id, planned_op in planned_ops.items():
        amount = float(planned_op.amount)
        for occurrence in planned_op.date_range.iterate_over_date_ranges(
            from_date=month
        ):
            if (day := occurrence.start_date) < month:
                continue
            if day > month_end:
                break
            if operations_paid := paid.pop((op_id, day), []):
                item = gaps.item(GapCause.OTHER_AMOUNT, planned_op.category, planned_op)
                item.actual[index] += sum(float(op.amount) for op in operations_paid)
                item.operation_count += len(operations_paid)
            else:
                item = gaps.item(GapCause.NOT_PAID, planned_op.category, planned_op)
                item.missed.append(day)
            item.planned[index] += amount
