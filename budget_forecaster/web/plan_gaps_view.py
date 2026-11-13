"""The "Gaps to plan" card: what weighs most in the gap between plan and actual."""

from typing import NamedTuple
from urllib.parse import urlencode

from dateutil.relativedelta import relativedelta

from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.plan_gaps import GapCause, GapItem, PlanGaps
from budget_forecaster.web.formatting import (
    category_name,
    format_date,
    format_eur_rounded,
    format_short_month,
)

GAP_PERIODS = (3, 6, 12)
DEFAULT_GAP_MONTHS = 6
CARD_ROWS = 7

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


class GapRow(NamedTuple):
    """An item that weighs on the gap, ready to read."""

    name: str
    cause: str
    color: str
    diagnosis: str
    average: float
    url: str


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


def _url(item: GapItem, gaps: PlanGaps) -> str:
    if item.target is not None:
        kind = "budget" if isinstance(item.target, Budget) else "planned"
        return f"/targets/{kind}/{item.target.id}?" + urlencode(
            {"return_to": "/trends#gaps"}
        )
    last_day = gaps.months[-1] + relativedelta(months=1, days=-1)
    return "/operations?" + urlencode(
        {
            "category": item.category.value,
            "date_from": gaps.months[0].isoformat(),
            "date_to": last_day.isoformat(),
            "unlinked": "true",
        }
    )


def _row(item: GapItem, gaps: PlanGaps, currency: str) -> GapRow:
    name = (
        item.target.description
        if item.target is not None
        else category_name(item.category.value)
    )
    cause = _cause_labels()[item.cause][1]
    if item.cause is GapCause.BUDGET:
        cause = _("budget over") if item.total < 0 else _("budget under")
    return GapRow(
        name=name,
        cause=cause,
        color=_COLORS[item.cause],
        diagnosis=_diagnosis(item, gaps, currency),
        average=gaps.average((item,)),
        url=_url(item, gaps),
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
) -> GapCard:
    """The card over the last period months that are over.

    Args:
        app: The application service.
        period: How many months that are over to compare.
        limit: How many items to list, all of them when None.
        cause: The only cause to list, every cause when None.
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
        rows=tuple(_row(item, gaps, app.currency) for item in items),
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
