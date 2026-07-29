"""Derive the state of past iterations of planned operations.

An iteration no historic operation matched is late, and stays counted in the
forecast until the user decides what to do with it or the late horizon passes.

The forecast (through the actualizer) and the overdue list share this derivation,
so both agree on what "late" means.
"""

from collections.abc import Mapping, Set
from datetime import date, timedelta
from typing import Final, NamedTuple

from budget_forecaster.core.types import (
    IterationAction,
    IterationDate,
    IterationState,
    PlannedOperationId,
)
from budget_forecaster.domain.operation.iteration_resolution import IterationResolution
from budget_forecaster.domain.operation.planned_operation import PlannedOperation

LATE_HORIZON: Final = timedelta(days=31)
"""How long an unmatched iteration keeps weighing on the forecast.

Undecided iterations older than this stop being counted, and say so in the
overdue list rather than dropping out of it.
"""

OVERDUE_LISTING_WINDOW: Final = 2 * LATE_HORIZON
"""How far back the overdue list reaches.

One late horizon to be counted, one more to be noticed. An iteration nobody acted
on by then leaves the list; a decision taken on it is still honoured.
"""


class PastIteration(NamedTuple):
    """An iteration due by the balance date that no operation matched."""

    planned_operation_id: PlannedOperationId
    iteration_date: IterationDate
    description: str
    amount: float
    currency: str
    state: IterationState
    effective_date: date | None
    """The date the forecast counts the amount on; None when it is not counted."""

    postponed_to: date | None = None
    """The date the user chose, whatever the state that choice ended up producing."""


def derive_past_iterations(
    planned_operation: PlannedOperation,
    balance_date: date,
    matched_iterations: Set[date],
    resolutions: Mapping[IterationDate, IterationResolution],
    since: date | None = None,
) -> tuple[PastIteration, ...]:
    """Derive the state of every unmatched iteration due by the balance date.

    Args:
        planned_operation: The operation to walk.
        balance_date: The account's balance date.
        matched_iterations: Iteration dates already linked to an operation.
        resolutions: The user's decisions, keyed by iteration date.
        since: Oldest iteration to look at. A decision is always honoured, however
            old the iteration it applies to. Defaults to the operation's own start,
            which is unbounded for an operation backdated by years.

    Returns:
        The unmatched past iterations, oldest first.
    """
    if planned_operation.id is None:
        return ()

    horizon_start = balance_date - LATE_HORIZON
    late_date = balance_date + timedelta(days=1)
    window_start = min([since, *resolutions]) if since is not None else None
    past: list[PastIteration] = []

    for date_range in planned_operation.date_range.iterate_over_date_ranges(
        from_date=window_start
    ):
        if (iteration_date := date_range.start_date) > balance_date:
            break
        if window_start is not None and iteration_date < window_start:
            continue
        if iteration_date in matched_iterations:
            continue

        resolution = resolutions.get(iteration_date)
        state, effective_date = _derive_state(
            resolution, iteration_date, horizon_start, balance_date, late_date
        )
        past.append(
            PastIteration(
                planned_operation_id=planned_operation.id,
                iteration_date=iteration_date,
                description=planned_operation.description,
                amount=planned_operation.amount,
                currency=planned_operation.currency,
                state=state,
                effective_date=effective_date,
                postponed_to=resolution.postponed_to if resolution else None,
            )
        )

    return tuple(past)


def _derive_state(
    resolution: IterationResolution | None,
    iteration_date: date,
    horizon_start: date,
    balance_date: date,
    late_date: date,
) -> tuple[IterationState, date | None]:
    """Return the state of one unmatched iteration and the date it counts on."""
    if resolution is None:
        if iteration_date >= horizon_start:
            return IterationState.LATE, late_date
        return IterationState.EXPIRED, None

    if resolution.action is IterationAction.SKIP:
        return IterationState.SKIPPED, None

    if (postponed_to := resolution.postponed_to) is None:
        raise ValueError("A postponed iteration must carry a new date")
    if postponed_to > balance_date:
        return IterationState.POSTPONED, postponed_to
    if postponed_to >= horizon_start:
        # The chosen date passed with nothing to match: late again, on its own age.
        return IterationState.LATE, late_date
    return IterationState.EXPIRED, None


def index_resolutions(
    resolutions: tuple[IterationResolution, ...],
) -> dict[PlannedOperationId, dict[IterationDate, IterationResolution]]:
    """Index decisions by planned operation, then by iteration date."""
    indexed: dict[PlannedOperationId, dict[IterationDate, IterationResolution]] = {}
    for resolution in resolutions:
        indexed.setdefault(resolution.planned_operation_id, {})[
            resolution.iteration_date
        ] = resolution
    return indexed
