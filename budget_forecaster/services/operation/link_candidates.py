"""Rank the two ends of a link against each other.

Both directions of manual linking ask the same question — how well does this
operation fit that dated occurrence — and answer it with the matching score, so
they agree wherever they overlap. From an operation the caller ranks the
targets; from an occurrence it ranks the operations that could have paid it.

The strict matcher cannot serve the second direction: an occurrence is offered
for linking precisely because matching it failed.

These functions take the data, not a repository: the caller decides which
operations and targets are worth scoring.
"""

import enum
from datetime import date, timedelta
from typing import Final, NamedTuple

from budget_forecaster.core.types import TargetId
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_range import OperationRange
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.operation.operation_link_service import (
    compute_match_score,
)

CANDIDATE_WINDOW: Final = timedelta(days=60)
"""How far apart an operation and an occurrence may be and still be compared."""

_CLOSE_AMOUNT_RATIO: Final = 0.05


class AmountMatch(enum.StrEnum):
    """How well a candidate's amount agrees, the strongest signal of the two."""

    EXACT = enum.auto()
    CLOSE = enum.auto()
    OFF = enum.auto()


def amount_match(
    operation: HistoricOperation,
    target: OperationRange,
    ratio: float = _CLOSE_AMOUNT_RATIO,
) -> AmountMatch:
    """Compare the two amounts, ignoring their sign."""
    theirs = abs(float(target.amount))
    if (ours := abs(float(operation.amount))) == theirs:
        return AmountMatch.EXACT
    if theirs and abs(ours - theirs) <= theirs * ratio:
        return AmountMatch.CLOSE
    return AmountMatch.OFF


def best_score(
    operation: HistoricOperation,
    target: OperationRange,
    window: timedelta = CANDIDATE_WINDOW,
) -> float:
    """The best score any of the target's occurrences within window reaches.

    Both bounds are checked here: a one-off target yields its single day whatever
    from_date it is given, so asking the iterator is not enough.
    """
    earliest = operation.operation_date - window
    latest = operation.operation_date + window
    best = 0.0
    for iteration in target.date_range.iterate_over_date_ranges(earliest):
        if iteration.start_date > latest:
            break
        if iteration.start_date < earliest:
            continue
        best = max(best, compute_match_score(operation, target, iteration.start_date))
    return best


class ScoredTarget(NamedTuple):
    """A persisted budget or planned operation ranked against one operation."""

    target: Budget | PlannedOperation
    target_id: TargetId
    score: float
    amount_match: AmountMatch


def rank_targets(
    operation: HistoricOperation, targets: tuple[Budget | PlannedOperation, ...]
) -> tuple[ScoredTarget, ...]:
    """Rank targets against one operation, best first.

    Each target is scored on its own best-fitting occurrence, since the caller
    has not chosen one yet. An unsaved target is left out: a link to it could
    not be persisted.
    """
    scored = []
    for target in targets:
        if (target_id := target.id) is None:
            continue
        scored.append(
            ScoredTarget(
                target=target,
                target_id=target_id,
                score=best_score(operation, target),
                amount_match=amount_match(operation, target),
            )
        )
    scored.sort(key=lambda s: s.score, reverse=True)
    return tuple(scored)


class ScoredOperation(NamedTuple):
    """An operation ranked against one dated occurrence."""

    operation: HistoricOperation
    score: float
    amount_match: AmountMatch


def rank_operations(
    target: PlannedOperation,
    iteration_date: date,
    operations: tuple[HistoricOperation, ...],
) -> tuple[ScoredOperation, ...]:
    """Rank the operations that could have paid one occurrence, best first.

    Only operations of the target's own sign are considered: a credit never pays
    an expense. Ties break on distance to the occurrence, then on id, so the
    order is stable.
    """
    expense = float(target.amount) < 0
    scored = [
        ScoredOperation(
            operation=operation,
            score=compute_match_score(operation, target, iteration_date),
            amount_match=amount_match(operation, target),
        )
        for operation in operations
        if (float(operation.amount) < 0) == expense
    ]
    scored.sort(
        key=lambda s: (
            -s.score,
            abs((s.operation.operation_date - iteration_date).days),
            s.operation.unique_id,
        )
    )
    return tuple(scored)
