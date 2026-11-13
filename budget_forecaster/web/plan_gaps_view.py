"""The "Gaps to plan" card: what weighs most in the gap between plan and actual."""

from datetime import date
from typing import NamedTuple
from urllib.parse import urlencode

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import REVIEWED_MONTHS
from budget_forecaster.services.forecast.plan_gaps import GapCause, GapItem, PlanGaps
from budget_forecaster.web.formatting import (
    category_name,
    format_date,
    format_eur,
    format_eur_rounded,
    format_short_month,
)
from budget_forecaster.web.viewmodels import can_end_today

GAP_PERIODS = (3, 6, REVIEWED_MONTHS)
DEFAULT_GAP_MONTHS = 6
CARD_ROWS = 7
MIN_FIX_GAP = 5.0
"""A gap under this much a month is not worth changing the plan for."""

_COLORS = {
    GapCause.BUDGET: "#2f6df6",
    GapCause.UNPLANNED_EXPENSE: "#e2711d",
    GapCause.OTHER_AMOUNT: "#7c5cff",
    GapCause.UNPLANNED_INCOME: "#0aa5a5",
    GapCause.NOT_PAID: "#b8860b",
}


def _cause_labels() -> dict[GapCause, tuple[str, str]]:
    """(chip label, row label) of each cause, in the current language."""
    return {
        GapCause.BUDGET: (_("Budgets"), ""),
        GapCause.UNPLANNED_EXPENSE: (_("Unplanned spending"), _("unplanned spending")),
        GapCause.OTHER_AMOUNT: (_("Paid another amount"), _("paid another amount")),
        GapCause.UNPLANNED_INCOME: (_("Unplanned income"), _("unplanned income")),
        GapCause.NOT_PAID: (_("Planned, never paid"), _("planned, never paid")),
    }


class CauseChip(NamedTuple):
    """One cause and its average monthly gap; picking it filters the list."""

    key: str
    label: str
    color: str
    average: float
    active: bool


class GapFix(NamedTuple):
    """A button under a row that corrects the plan.

    With an action, the button asks its question on the card and posts the
    fields there; its link opens the same change on the edit page. Without
    one, the button is that link.
    """

    label: str
    question: str = ""
    action: str = ""
    fields: tuple[tuple[str, str], ...] = ()
    url: str = ""


class GapRow(NamedTuple):
    """An item that weighs on the gap, ready to read."""

    name: str
    cause: str
    color: str
    diagnosis: str
    average: float
    url: str
    fix: GapFix | None = None


class MonthBar(NamedTuple):
    """The net gap of one month, placed on a shared scale."""

    label: str
    total: float
    top_pct: float
    height_pct: float
    url: str


class GapCard(NamedTuple):
    """Everything the card and the full list render."""

    months: int
    period: int
    periods: tuple[int, ...]
    cause: str  # the cause the list is filtered on, empty for every cause
    average: float
    chips: tuple[CauseChip, ...]
    rows: tuple[GapRow, ...]
    item_count: int
    bars: tuple[MonthBar, ...]
    zero_pct: float


def _amount(value: float, currency: str) -> str:
    return format_eur_rounded(abs(value), currency)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _budget_diagnosis(item: GapItem, currency: str) -> str:
    active = [(p, a) for p, a in zip(item.planned, item.actual) if p]
    planned = _mean([p for p, _a in active])
    actual = _mean([a for _p, a in active])
    words = {
        "actual": _amount(actual, currency),
        "planned": _amount(planned, currency),
    }
    if planned > 0:
        return _("{actual} received on average for {planned} planned").format(**words)
    over = sum(1 for p, a in active if a < p)
    text = _("{actual} spent on average for {planned} planned").format(**words)
    if over:
        text += _(", over in {over} months out of {n}").format(over=over, n=len(active))
    return text


def _diagnosis(item: GapItem, gaps: PlanGaps, currency: str) -> str:
    match item.cause:
        case GapCause.BUDGET:
            return _budget_diagnosis(item, currency)
        case GapCause.OTHER_AMOUNT:
            paid = [(p, a) for p, a in zip(item.planned, item.actual) if p or a]
            words = {
                "actual": _amount(_mean([a for _p, a in paid]), currency),
                "planned": _amount(_mean([p for p, _a in paid]), currency),
            }
            if sum(item.planned) > 0:
                return _("{actual} received on average for {planned} planned").format(
                    **words
                )
            return _("{actual} paid on average for {planned} planned").format(**words)
        case GapCause.NOT_PAID:
            return _(
                "{count} occurrence(s) without payment, the last on {date}"
            ).format(count=len(item.missed), date=format_date(item.missed[-1]))
        case _:
            return _("{count} operation(s), {total} over {n} months").format(
                count=item.operation_count,
                total=_amount(sum(item.actual), currency),
                n=len(gaps.months),
            )


def _url(item: GapItem, gaps: PlanGaps, back: str) -> str:
    if item.target is not None:
        kind = "budget" if isinstance(item.target, Budget) else "planned"
        return f"/targets/{kind}/{item.target.id}?" + urlencode({"return_to": back})
    last_day = gaps.months[-1] + relativedelta(months=1, days=-1)
    return "/operations?" + urlencode(
        {
            "category": item.category.value,
            "date_from": gaps.months[0].isoformat(),
            "date_to": last_day.isoformat(),
            "unlinked": "true",
            "return_to": back,
        }
    )


class _FixContext(NamedTuple):
    """What every fix needs besides its item."""

    currency: str
    back: str
    today: date
    month: date  # the first day of the current month, where a split starts
    window_end: date  # the last day of the months compared


def _money(amount: float, currency: str) -> str:
    """An unsigned amount, with cents only when it has some."""
    if round(amount, 2) == round(amount):
        return format_eur_rounded(abs(amount), currency)
    return format_eur(abs(amount), currency)


def _split_fix(
    label: str, target: Budget | PlannedOperation, amount: float, fix: _FixContext
) -> GapFix | None:
    """Split the target from the current month at amount, confirmed on the card."""
    current = float(target.amount)
    if round(amount, 2) == round(current, 2):
        return None
    try:
        first = target.split_at(fix.month)[1].date_range.start_date
    except ValueError:
        return None
    kind = "budget" if isinstance(target, Budget) else "planned"
    split = {
        "split_date": fix.month.isoformat(),
        "split_amount": f"{amount:.2f}".removesuffix(".00"),
        "return_to": fix.back,
    }
    return GapFix(
        label=label,
        question=_("From {date}: {old} → {new}. Past months keep their plan.").format(
            date=format_date(first),
            old=_money(current, fix.currency),
            new=_money(amount, fix.currency),
        ),
        action=f"/targets/{kind}/{target.id}/split",
        fields=tuple(split.items()),
        url=f"/targets/{kind}/{target.id}?{urlencode(split)}#split",
    )


def _budget_fix(item: GapItem, budget: Budget, fix: _FixContext) -> GapFix | None:
    """Set the budget to what it took when it is off the same way half the time."""
    active = [(p, a) for p, a in zip(item.planned, item.actual) if p]
    same_way = sum(
        1 for p, a in active if round(a - p, 2) and (a - p > 0) == (item.total > 0)
    )
    # The months hold the budget spread over calendar days: scale the budget's own
    # amount by what was spent against it, whatever its period.
    amount = round(
        float(budget.amount) * sum(a for _p, a in active) / sum(p for p, _a in active)
    )
    if not amount or 2 * same_way < len(active):
        return None
    label = _("Set the budget to {amount}").format(
        amount=format_eur_rounded(abs(amount), fix.currency)
    )
    return _split_fix(label, budget, amount, fix)


def _amount_fix(
    item: GapItem, planned_op: PlannedOperation, fix: _FixContext
) -> GapFix | None:
    """Plan the amount the latest occurrence was paid."""
    if not item.latest_paid:
        return None
    amount = round(item.latest_paid, 2)
    label = _("Set the planned amount to {amount}").format(
        amount=format_eur_rounded(abs(amount), fix.currency)
    )
    return _split_fix(label, planned_op, amount, fix)


def _end_fix(
    item: GapItem, planned_op: PlannedOperation, fix: _FixContext
) -> GapFix | None:
    """End a planned operation whose last two occurrences went unpaid."""
    occurrences: list[date] = []
    for occurrence in planned_op.date_range.iterate_over_date_ranges():
        if occurrence.start_date > fix.window_end:
            break
        occurrences.append(occurrence.start_date)
    last_two = occurrences[-2:]
    if (
        len(last_two) < 2
        or not set(last_two) <= set(item.missed)
        or not can_end_today(planned_op, fix.today)
    ):
        return None
    return GapFix(
        label=_("Stop planning it"),
        question=_("End today? Later occurrences leave the forecast."),
        action=f"/targets/planned/{planned_op.id}/end",
        fields=(("return_to", fix.back),),
    )


def _new_budget_fix(item: GapItem, gaps: PlanGaps, fix: _FixContext) -> GapFix | None:
    """Plan a monthly budget for a category spent in half the months or more."""
    present = sum(1 for amount in item.actual if round(amount, 2))
    amount = round(item.total / len(gaps.months))
    if item.category is Category.UNCATEGORIZED or not amount:
        return None
    if 2 * present < len(gaps.months):
        return None
    query = urlencode(
        {
            "category": item.category.name,
            "amount": amount,
            "return_to": fix.back,
        }
    )
    return GapFix(
        label=_("Create a monthly budget of {amount}").format(
            amount=format_eur_rounded(abs(amount), fix.currency)
        ),
        url=f"/targets/budget/new?{query}",
    )


def _fix(item: GapItem, gaps: PlanGaps, fix: _FixContext) -> GapFix | None:
    """The button that corrects the plan, when the correction is clear."""
    if abs(gaps.average((item,))) < MIN_FIX_GAP:
        return None
    match item.cause, item.target:
        case GapCause.BUDGET, Budget() as budget:
            return _budget_fix(item, budget, fix)
        case GapCause.OTHER_AMOUNT, PlannedOperation() as planned_op:
            return _amount_fix(item, planned_op, fix)
        case GapCause.NOT_PAID, PlannedOperation() as planned_op:
            return _end_fix(item, planned_op, fix)
        case (GapCause.UNPLANNED_EXPENSE | GapCause.UNPLANNED_INCOME), None:
            return _new_budget_fix(item, gaps, fix)
    return None


def _row(item: GapItem, gaps: PlanGaps, fix: _FixContext) -> GapRow:
    name = (
        item.target.description
        if item.target is not None
        else category_name(item.category.value)
    )
    cause = _cause_labels()[item.cause][1]
    if item.cause is GapCause.BUDGET and sum(item.planned) > 0:
        cause = (
            _("less received than planned")
            if item.total < 0
            else _("more received than planned")
        )
    elif item.cause is GapCause.BUDGET:
        cause = _("budget over") if item.total < 0 else _("budget under")
    return GapRow(
        name=name,
        cause=cause,
        color=_COLORS[item.cause],
        diagnosis=_diagnosis(item, gaps, fix.currency),
        average=gaps.average((item,)),
        url=_url(item, gaps, fix.back),
        fix=_fix(item, gaps, fix),
    )


def _scale(gaps: PlanGaps) -> tuple[float, float]:
    """The span of the month bars, and where zero sits from the top, in percent."""
    totals = gaps.month_totals()
    high = max([0.0, *totals])
    span = (high - min([0.0, *totals])) or 1.0
    return span, high / span * 100


def _bars(gaps: PlanGaps) -> tuple[MonthBar, ...]:
    span, zero_pct = _scale(gaps)
    return tuple(
        MonthBar(
            label=format_short_month(month),
            total=total,
            top_pct=round(zero_pct - max(total, 0.0) / span * 100, 1),
            height_pct=round(abs(total) / span * 100, 1),
            url=f"/month/{month:%Y-%m}",
        )
        for month, total in zip(gaps.months, gaps.month_totals())
    )


def _useful_periods(available: int) -> tuple[int, ...]:
    """The periods that each give another window, given the months available.

    A period longer than the history shows the same months as the shortest one
    that already covers it all.
    """
    covering = next((p for p in GAP_PERIODS if p >= available), GAP_PERIODS[-1])
    return tuple(p for p in GAP_PERIODS if p <= covering)


def build_gap_card(
    app: ApplicationService,
    period: int,
    *,
    limit: int | None = CARD_ROWS,
    cause: GapCause | None = None,
    today: date | None = None,
) -> GapCard:
    """The card over the last period months that are over.

    Args:
        app: The application service.
        period: How many months that are over to compare.
        limit: How many items to list, all of them when None.
        cause: The only cause to list, every cause when None.
        today: The day fixes start from, the real today when None.
    """
    widest = app.get_plan_gaps(max(GAP_PERIODS))
    periods = _useful_periods(len(widest.months))
    period = min(period, periods[-1])
    gaps = widest if period == max(GAP_PERIODS) else app.get_plan_gaps(period)
    labels = _cause_labels()
    averages = gaps.cause_averages()
    # A gap that rounds to nothing a month is noise, not a lead.
    worth = [
        item
        for item in gaps.items
        if round(gaps.average((item,))) != 0 and cause in (None, item.cause)
    ]
    items = worth if limit is None else worth[:limit]
    # The full list comes back to itself; the card, to the Tendances page.
    back = (
        "/trends/gaps?"
        + urlencode({"months": period, "cause": cause.value if cause else ""})
        if limit is None
        else "/trends#gaps"
    )
    today = today or date.today()
    fix = _FixContext(
        currency=app.currency,
        back=back,
        today=today,
        month=today.replace(day=1),
        window_end=(
            gaps.months[-1] + relativedelta(months=1, days=-1) if gaps.months else today
        ),
    )
    return GapCard(
        months=len(gaps.months),
        period=period,
        periods=periods,
        cause=cause.value if cause is not None else "",
        average=gaps.average(),
        chips=tuple(
            CauseChip(
                key=chip.value,
                label=labels[chip][0],
                color=color,
                average=averages[chip],
                active=chip is cause,
            )
            for chip, color in _COLORS.items()
            if round(averages[chip]) != 0
        ),
        rows=tuple(_row(item, gaps, fix) for item in items),
        item_count=len(worth),
        bars=_bars(gaps),
        zero_pct=round(_scale(gaps)[1], 1),
    )


def gap_cause(raw: str) -> GapCause | None:
    """The cause a query string asks for, None for every cause."""
    try:
        return GapCause(raw)
    except ValueError:
        return None


def gap_period(raw: object) -> int:
    """A month count from a query string, the default when it is not offered."""
    try:
        months = int(str(raw))
    except (TypeError, ValueError):
        return DEFAULT_GAP_MONTHS
    return months if months in GAP_PERIODS else DEFAULT_GAP_MONTHS
