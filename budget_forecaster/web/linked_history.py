"""The operations counted by a budget or a planned operation, period by period.

A planned operation shows one row per occurrence, a budget one row per period,
most recent first, over a window of months ending at the balance date.
"""

from collections import defaultdict
from datetime import date
from enum import StrEnum
from typing import NamedTuple

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.date_range import DateRangeInterface
from budget_forecaster.core.types import IterationDate
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.iteration_resolution import (
    IterationAction,
    IterationResolution,
)
from budget_forecaster.domain.operation.link_attribution import budget_period_start
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web.formatting import format_date, format_month

HISTORY_STEP_MONTHS = 6


class OccurrenceState(StrEnum):
    """Where an occurrence or a period stands."""

    LINKED = "linked"
    NOT_LINKED = "not_linked"
    UPCOMING = "upcoming"
    IN_PROGRESS = "in_progress"
    POSTPONED = "postponed"
    SKIPPED = "skipped"


class LinkedOperation(NamedTuple):
    """An operation that counts for an occurrence or a period."""

    operation_id: int
    operation_date: date
    description: str
    amount: float


class Occurrence(NamedTuple):
    """One occurrence of a planned operation, or one period of a budget."""

    start: date
    label: str
    state: OccurrenceState
    operations: tuple[LinkedOperation, ...]
    total: float
    planned: float
    postponed_to: date | None
    days_late: int | None  # set while the Accueil card still lists it


class LinkedHistory(NamedTuple):
    """The occurrences shown, and the window to ask for to see older ones."""

    occurrences: tuple[Occurrence, ...]
    more_months: int | None


def _window_start(balance_date: date, months: int) -> date:
    return balance_date.replace(day=1) - relativedelta(months=months - 1)


def _period_label(period: DateRangeInterface) -> str:
    """A calendar month by its name, any other period by its first and last day."""
    start, last = period.start_date, period.last_date
    if start.day == 1 and last == start + relativedelta(months=1, days=-1):
        return format_month(start)
    return f"{format_date(start)} → {format_date(last)}"


def _linked_by_iteration(
    app: ApplicationService, target: PlannedOperation | Budget
) -> dict[IterationDate, list[LinkedOperation]]:
    operations: dict[int, HistoricOperation] = {
        op.unique_id: op for op in app.operations
    }
    linked: defaultdict[IterationDate, list[LinkedOperation]] = defaultdict(list)
    for link in app.get_links_for_target(target):
        if (operation := operations.get(link.operation_unique_id)) is None:
            continue
        key = (
            budget_period_start(target, link.iteration_date)
            if isinstance(target, Budget)
            else link.iteration_date
        )
        linked[key].append(
            LinkedOperation(
                operation_id=operation.unique_id,
                operation_date=operation.operation_date,
                description=operation.description,
                amount=float(operation.amount),
            )
        )
    for operations_of_date in linked.values():
        operations_of_date.sort(key=lambda op: op.operation_date)
    return linked


def _occurrence(  # pylint: disable=too-many-arguments
    start: date,
    label: str,
    state: OccurrenceState,
    operations: list[LinkedOperation],
    planned: float,
    *,
    postponed_to: date | None = None,
    days_late: int | None = None,
) -> Occurrence:
    return Occurrence(
        start=start,
        label=label,
        state=state,
        operations=tuple(operations),
        total=sum(op.amount for op in operations),
        planned=planned,
        postponed_to=postponed_to,
        days_late=days_late,
    )


def _past_state(
    operations: list[LinkedOperation], decision: IterationResolution | None
) -> OccurrenceState:
    if operations:
        return OccurrenceState.LINKED
    if decision is None:
        return OccurrenceState.NOT_LINKED
    if decision.action is IterationAction.POSTPONE:
        return OccurrenceState.POSTPONED
    return OccurrenceState.SKIPPED


def _planned_occurrences(
    app: ApplicationService, planned: PlannedOperation, since: date
) -> list[Occurrence]:
    if planned.id is None:
        return []
    balance_date = app.balance_date
    linked = _linked_by_iteration(app, planned)
    decisions = {
        decision.iteration_date: decision
        for decision in app.get_iteration_resolutions(planned.id)
    }
    overdue = {
        late.iteration_date: late.days_overdue
        for late in app.get_overdue_iterations()
        if late.planned_operation_id == planned.id
    }
    amount = float(planned.amount)
    rows: list[Occurrence] = []
    for occurrence in planned.date_range.iterate_over_date_ranges(from_date=since):
        if (day := occurrence.start_date) < since:
            continue
        operations = linked.pop(day, [])
        if day > balance_date and not operations:
            rows.append(
                _occurrence(day, format_date(day), OccurrenceState.UPCOMING, [], amount)
            )
            break
        decision = decisions.get(day)
        rows.append(
            _occurrence(
                day,
                format_date(day),
                _past_state(operations, decision),
                operations,
                amount,
                postponed_to=decision.postponed_to if decision else None,
                days_late=overdue.get(day),
            )
        )
    # An occurrence the planned operation no longer has keeps its operations.
    rows.extend(
        _occurrence(day, format_date(day), OccurrenceState.LINKED, operations, amount)
        for day, operations in linked.items()
        if day >= since
    )
    return rows


def _budget_periods(
    app: ApplicationService, budget: Budget, since: date
) -> list[Occurrence]:
    balance_date = app.balance_date
    linked = _linked_by_iteration(app, budget)
    amount = float(budget.amount)
    rows: list[Occurrence] = []
    for period in budget.date_range.iterate_over_date_ranges(from_date=since):
        if period.start_date > balance_date:
            break
        if period.last_date < since:
            continue
        operations = linked.get(period.start_date, [])
        if period.last_date >= balance_date:
            state = OccurrenceState.IN_PROGRESS
        elif operations:
            state = OccurrenceState.LINKED
        else:
            state = OccurrenceState.NOT_LINKED
        rows.append(
            _occurrence(
                period.start_date, _period_label(period), state, operations, amount
            )
        )
    return rows


def build_linked_history(
    app: ApplicationService, target: PlannedOperation | Budget, months: int
) -> LinkedHistory:
    """Return the occurrences or periods of the last months, most recent first.

    Args:
        app: The application service.
        target: A stored planned operation or budget.
        months: How many months back from the balance date the window covers.

    Returns:
        The occurrences, and the window that shows older ones, if any are left.
    """
    since = _window_start(app.balance_date, months)
    if isinstance(target, Budget):
        rows = _budget_periods(app, target, since)
    else:
        rows = _planned_occurrences(app, target, since)
    has_older = target.date_range.start_date < since
    return LinkedHistory(
        occurrences=tuple(sorted(rows, key=lambda row: row.start, reverse=True)),
        more_months=months + HISTORY_STEP_MONTHS if has_older else None,
    )
