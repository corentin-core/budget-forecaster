"""Link-flow view models: score-ranked candidates and the iteration window.

Both directions live here. From an operation the user picks a target then an
iteration; from an overdue iteration the user picks the operation that is it.
The two rank with the same score, so they agree on any single pair.
"""

from datetime import date, timedelta
from typing import NamedTuple, Protocol, TypeVar

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.types import LinkType, OperationId
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_range import OperationRange
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_link_service import (
    compute_match_score,
)
from budget_forecaster.services.operation.operation_service import OperationFilter

_SCORE_WINDOW = timedelta(days=60)  # look this far around the op for the best score


class Candidate(NamedTuple):
    """A link target ranked against the operation."""

    kind: str  # "budget" | "planned"
    target_id: int
    description: str
    amount: float
    category_key: str
    score: float
    reason: str


class Iteration(NamedTuple):
    """One iteration date offered for linking, with its match score."""

    iso: str
    label: str
    score: float


def _best_score(operation: HistoricOperation, target: OperationRange) -> float:
    best = 0.0
    start = operation.operation_date - _SCORE_WINDOW
    for iteration in target.date_range.iterate_over_date_ranges(start):
        if iteration.start_date > operation.operation_date + _SCORE_WINDOW:
            break
        best = max(best, compute_match_score(operation, target, iteration.start_date))
    return best


def _reason(operation: HistoricOperation, target: OperationRange) -> str:
    if abs(float(operation.amount)) == abs(float(target.amount)):
        return _("same amount")
    if (
        abs(abs(float(operation.amount)) - abs(float(target.amount)))
        <= abs(float(target.amount)) * 0.05
    ):
        return _("close amount")
    return ""


def build_candidates(
    app: ApplicationService, operation: HistoricOperation, target_type: str
) -> tuple[Candidate, ...]:
    """Rank all targets of the given type against the operation, best first."""
    targets: tuple[Budget | PlannedOperation, ...]
    if target_type == "planned":
        targets = app.get_all_planned_operations()
        kind = "planned"
    else:
        targets = app.get_all_budgets()
        kind = "budget"

    candidates = [
        Candidate(
            kind=kind,
            target_id=t.id,
            description=t.description,
            amount=float(t.amount),
            category_key=t.category.name,
            score=_best_score(operation, t),
            reason=_reason(operation, t),
        )
        for t in targets
        if t.id is not None
    ]
    candidates.sort(key=lambda c: c.score, reverse=True)
    return tuple(candidates)


_MIN_SCORE = 15.0  # hide weaker candidates behind "show all"
_MIN_SHOWN = 5
_CAP = 10


class Rankable(Protocol):
    """What the shared candidate filter needs of a candidate."""

    @property
    def description(self) -> str:
        """The text a search matches on."""

    @property
    def score(self) -> float:
        """How well the candidate matches, 0-100."""


_RankableT = TypeVar("_RankableT", bound=Rankable)


def filter_candidates(
    candidates: tuple[_RankableT, ...],
    query: str,
    show_all: bool,
    *,
    min_score: float = _MIN_SCORE,
    pad_with_weak: bool = True,
) -> tuple[tuple[_RankableT, ...], int]:
    """Narrow the candidate list; return (shown, hidden_count).

    A search matches on description and shows every match. Otherwise only strong
    matches show, with the rest behind "show all".

    Args:
        candidates: The ranked candidates, best first.
        query: A search text, or empty.
        show_all: Whether the user asked for the weak matches too.
        min_score: The floor a candidate must clear to show by default.
        pad_with_weak: Fall back to the top few when too few clear the floor.
    """
    if query:
        needle = query.casefold()
        matches = tuple(c for c in candidates if needle in c.description.casefold())
        return matches, 0
    if show_all:
        return candidates, 0
    shown = tuple(c for c in candidates if c.score >= min_score)
    if pad_with_weak and len(shown) < _MIN_SHOWN:
        shown = candidates[:_CAP]
    return shown, len(candidates) - len(shown)


def build_iterations(
    operation: HistoricOperation, target: OperationRange, offset_months: int
) -> tuple[str, tuple[Iteration, ...], str]:
    """Return (window label, iterations in the window, best iso date).

    The window is ±2 months around the operation date shifted by offset_months.
    """
    center = operation.operation_date + relativedelta(months=offset_months)
    window_start = center - relativedelta(months=2)
    window_end = center + relativedelta(months=2)

    scored: list[tuple[date, float]] = []
    for iteration in target.date_range.iterate_over_date_ranges(
        window_start - timedelta(days=31)
    ):
        if iteration.start_date < window_start:
            continue
        if iteration.start_date > window_end:
            break
        scored.append(
            (
                iteration.start_date,
                compute_match_score(operation, target, iteration.start_date),
            )
        )

    best_iso = ""
    if scored:
        best_iso = max(scored, key=lambda s: s[1])[0].isoformat()

    scored.sort(key=lambda s: s[0])
    iterations = tuple(
        Iteration(iso=d.isoformat(), label=d.strftime("%d/%m/%Y"), score=score)
        for d, score in scored
    )
    window_label = f"{window_start.strftime('%m/%Y')} → {window_end.strftime('%m/%Y')}"
    return window_label, iterations, best_iso


class CurrentLink(NamedTuple):
    """The operation's existing link, for display on the link page."""

    kind: str
    target_name: str


def current_link(app: ApplicationService, operation_id: int) -> CurrentLink | None:
    """Describe the operation's current link, or None if unlinked."""
    if (link := app.get_link_for_operation(operation_id)) is None:
        return None
    if link.target_type is LinkType.BUDGET:
        names = {b.id: b.description for b in app.get_all_budgets()}
        kind = "budget"
    else:
        names = {p.id: p.description for p in app.get_all_planned_operations()}
        kind = "planned"
    return CurrentLink(
        kind=kind, target_name=names.get(link.target_id, f"#{link.target_id}")
    )


def target_object(
    app: ApplicationService, kind: str, target_id: int
) -> Budget | PlannedOperation:
    """Return the concrete target for create_manual_link."""
    if kind == "planned":
        return app.get_planned_operation_by_id(target_id)
    return app.get_budget_by_id(target_id)


# -----------------------------------------------------------------------------
# The other direction: from an iteration, the operations that could be it
# -----------------------------------------------------------------------------

_CANDIDATE_WINDOW = timedelta(days=60)
"""How far either side of the iteration the default candidate list reaches.

A search escapes it: someone who remembers the label and gets nothing back
concludes the operation is absent.
"""


class ExistingLink(NamedTuple):
    """What already counts a candidate operation, and what it would give up."""

    target_name: str
    iteration_date: date
    is_budget: bool
    """A budget has no iteration to hand back; it just stops counting the amount."""

    is_same_target: bool
    """The link already points at the planned operation being linked to."""


class OperationCandidate(NamedTuple):
    """An operation offered as the one that paid an overdue iteration."""

    operation_id: OperationId
    operation_date: date
    description: str
    amount: float
    score: float
    reason: str
    existing: ExistingLink | None


def _existing_links(
    app: ApplicationService, target: PlannedOperation
) -> dict[OperationId, ExistingLink]:
    """Describe every operation's current link, for the candidate badges."""
    budgets = {b.id: b.description for b in app.get_all_budgets()}
    planned = {p.id: p.description for p in app.get_all_planned_operations()}
    described = {}
    for link in app.get_all_links():
        is_budget = link.target_type is LinkType.BUDGET
        names = budgets if is_budget else planned
        described[link.operation_unique_id] = ExistingLink(
            target_name=names.get(link.target_id, f"#{link.target_id}"),
            iteration_date=link.iteration_date,
            is_budget=is_budget,
            is_same_target=not is_budget and link.target_id == target.id,
        )
    return described


def _same_sign(operation: HistoricOperation, target: PlannedOperation) -> bool:
    """Whether both are expenses or both are incomes."""
    return (float(operation.amount) < 0) == (float(target.amount) < 0)


def build_operation_candidates(
    app: ApplicationService,
    target: PlannedOperation,
    iteration_date: date,
    query: str = "",
) -> tuple[OperationCandidate, ...]:
    """Rank the operations that could be the given iteration, best first.

    Args:
        app: The application service.
        target: The planned operation the iteration belongs to.
        iteration_date: The iteration being linked, fixed by the caller.
        query: A search text. Given one, every operation whose description
            matches is considered, however far from the iteration it falls.

    Returns:
        The candidates, best first, already-linked ones included so a
        mis-attribution can be corrected rather than hidden.
    """
    if query:
        criteria = OperationFilter(search_text=query)
    else:
        criteria = OperationFilter(
            date_from=iteration_date - _CANDIDATE_WINDOW,
            date_to=iteration_date + _CANDIDATE_WINDOW,
        )
    links = _existing_links(app, target)

    candidates = [
        OperationCandidate(
            operation_id=operation.unique_id,
            operation_date=operation.operation_date,
            description=operation.description,
            amount=float(operation.amount),
            score=compute_match_score(operation, target, iteration_date),
            reason=_reason(operation, target),
            existing=links.get(operation.unique_id),
        )
        for operation in app.get_operations(criteria)
        if _same_sign(operation, target)
    ]
    candidates.sort(
        key=lambda c: (
            -c.score,
            abs((c.operation_date - iteration_date).days),
            c.operation_id,
        )
    )
    return tuple(candidates)


_MIN_OPERATION_SCORE = 55.0
"""The floor an operation clears to be offered by default.

Above the 50 that falling on the right day in the right category already scores:
in any given week a dozen operations do that, so the amount has to say something.
The target floor cannot be reused — targets are few, and picking one only loads
its iterations.
"""


def filter_operation_candidates(
    candidates: tuple[OperationCandidate, ...], query: str, show_all: bool
) -> tuple[tuple[OperationCandidate, ...], int]:
    """Narrow the operation candidates; return (shown, hidden_count).

    Nothing is padded out: a list of 5% matches, ranked, reads as an answer.
    """
    return filter_candidates(
        candidates,
        query,
        show_all,
        min_score=_MIN_OPERATION_SCORE,
        pad_with_weak=False,
    )
