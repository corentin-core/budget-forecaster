"""Month in which a linked operation counts.

A planned operation is due on a date, so an operation paid early or late still
counts in the month of the iteration it settles.
A budget period is a window, so an operation counts in its own month, clamped
into the period it is linked to.
"""

from datetime import date

from budget_forecaster.core.types import IterationDate, LinkType
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.operation_link import OperationLink


def linked_month(
    link: OperationLink, operation_date: date, budgets: tuple[Budget, ...]
) -> date:
    """Return the first day of the month in which the linked operation counts.

    Args:
        link: The link of the operation.
        operation_date: The date of the linked operation.
        budgets: The budgets the link may target.

    Returns:
        The first day of the attribution month.
    """
    if link.target_type is not LinkType.BUDGET:
        return link.iteration_date.replace(day=1)

    budget = next((b for b in budgets if b.id == link.target_id), None)
    period = (
        budget.date_range.current_date_range(link.iteration_date)
        if budget is not None
        else None
    )
    if period is None:
        return operation_date.replace(day=1)
    clamped = min(max(operation_date, period.start_date), period.last_date)
    return clamped.replace(day=1)


def budget_period_start(budget: Budget, iteration_date: IterationDate) -> IterationDate:
    """Return the start of the budget period holding a link's iteration date.

    A manual link keeps its iteration date when the budget is edited, so the date
    may no longer be a period start.
    """
    period = budget.date_range.current_date_range(iteration_date)
    return period.start_date if period is not None else iteration_date
