"""Link-flow view models: score-ranked candidates and the iteration window.

Mirrors the two TUI link modals (target pick, then iteration pick) as data the
link page and its HTMX iteration fragment render.
"""

from datetime import date, timedelta
from typing import NamedTuple

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.types import LinkType
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_range import OperationRange
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_link_service import (
    compute_match_score,
)

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


def filter_candidates(
    candidates: tuple[Candidate, ...], query: str, show_all: bool
) -> tuple[tuple[Candidate, ...], int]:
    """Narrow the candidate list; return (shown, hidden_count).

    A search matches on description and shows every match. Otherwise only strong
    matches show, falling back to the top few, with the rest behind "show all".
    """
    if query:
        needle = query.casefold()
        matches = tuple(c for c in candidates if needle in c.description.casefold())
        return matches, 0
    if show_all:
        return candidates, 0
    strong = tuple(c for c in candidates if c.score >= _MIN_SCORE)
    shown = strong if len(strong) >= _MIN_SHOWN else candidates[:_CAP]
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
