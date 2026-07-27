"""Tendances: balance evolution over time + expense breakdown by category."""

from datetime import date, timedelta
from math import pi
from typing import NamedTuple

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from budget_forecaster.core.types import Category
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_service import OperationFilter
from budget_forecaster.web.dependencies import get_app_service
from budget_forecaster.web.formatting import (
    category_name,
    format_date,
    format_eur,
    format_eur_rounded,
)
from budget_forecaster.web.rendering import render_template

router = APIRouter()

_PERIODS = (1, 3, 6, 12)
_DEFAULT_PERIOD = 3
_SPARK_WIDTH = 600
_SPARK_HEIGHT = 300
_SPARK_PADDING = 0.06  # headroom above/below the plotted range
_SPARK_XTICKS = 4
_PIE_RADIUS = 78
_PIE_CIRCUMFERENCE = 2 * pi * _PIE_RADIUS
_THRESHOLD_MIN = 0.0
_THRESHOLD_MAX = 10.0
_OTHER_COLOR = "#9ca3af"  # neutral grey, off-palette, for the folded "Other" slice
_PALETTE = (
    "#2f6df6",
    "#1f9d55",
    "#d64545",
    "#b8860b",
    "#7c5cff",
    "#e2711d",
    "#0aa5a5",
    "#c2185b",
)


class SparkPoint(NamedTuple):
    """A balance sample, in viewBox coordinates and preformatted for a tooltip."""

    x: float
    y: float
    label: str
    value: str


class AxisMark(NamedTuple):
    """A y-axis reference: an SVG line position plus a gutter label."""

    y: float  # viewBox y
    top_pct: float  # position for the HTML label (percent from top)
    text: str


class Sparkline(NamedTuple):
    """A balance sparkline: polyline, hover points, and axis references."""

    points: tuple[SparkPoint, ...]
    polyline: str
    width: int
    height: int
    labels: tuple[AxisMark, ...]
    zero: AxisMark | None
    threshold: AxisMark | None
    x_labels: tuple[str, ...]


class ExpenseSlice(NamedTuple):
    """One donut segment: its share of the total and its dash geometry.

    members lists the folded categories (name, amount) for the "Other" slice; it is
    empty for a plain single-category slice.
    """

    label: str
    amount: float
    average: float
    fraction: float
    color: str
    dash: float
    offset: float
    members: tuple[tuple[str, float], ...] = ()


class Breakdown(NamedTuple):
    """Expense breakdown as donut segments plus the period total."""

    slices: tuple[ExpenseSlice, ...]
    total: float
    radius: float
    circumference: float


class GroupedExpense(NamedTuple):
    """A donut entry before geometry: a category (or the folded 'Other' bucket).

    members lists the folded categories (name, amount) for the "Other" bucket; empty
    for a plain single-category entry.
    """

    label: str
    amount: float
    members: tuple[tuple[str, float], ...] = ()


def _x_labels(samples: list[tuple[date, float]]) -> tuple[str, ...]:
    """Evenly spaced date labels for the x-axis (first .. last)."""
    last = len(samples) - 1
    indices = sorted(
        {round(i * last / (_SPARK_XTICKS - 1)) for i in range(_SPARK_XTICKS)}
    )
    return tuple(format_date(samples[i][0]) for i in indices)


def _sparkline(
    samples: list[tuple[date, float]], currency: str, threshold: float
) -> Sparkline | None:
    if len(samples) < 2:
        return None
    balances = [balance for _, balance in samples]
    lowest, highest = min(balances), max(balances)

    # Widen the plotted range so zero and the threshold are always on-scale.
    low = min(lowest, 0.0, threshold)
    high = max(highest, 0.0, threshold)
    pad = (high - low or 1.0) * _SPARK_PADDING
    low -= pad
    high += pad
    span = high - low or 1.0

    def y_of(value: float) -> float:
        return round(_SPARK_HEIGHT * (high - value) / span, 1)

    def mark(value: float, text: str) -> AxisMark:
        return AxisMark(y_of(value), round((high - value) / span * 100, 1), text)

    last = len(samples) - 1
    points = tuple(
        SparkPoint(
            round(_SPARK_WIDTH * index / last, 1),
            y_of(balance),
            format_date(day),
            format_eur(balance, currency),
        )
        for index, (day, balance) in enumerate(samples)
    )
    zero = mark(0.0, "0") if low <= 0 <= high else None
    return Sparkline(
        points=points,
        polyline=" ".join(f"{p.x},{p.y}" for p in points),
        width=_SPARK_WIDTH,
        height=_SPARK_HEIGHT,
        labels=(
            mark(highest, format_eur_rounded(highest, currency)),
            mark(lowest, format_eur_rounded(lowest, currency)),
        ),
        zero=zero,
        threshold=mark(threshold, format_eur_rounded(threshold, currency)),
        x_labels=_x_labels(samples),
    )


def _grouped_expenses(
    amounts: dict[Category, float], threshold: float
) -> tuple[GroupedExpense, ...]:
    """Order expenses desc and fold sub-threshold categories into one 'Other' entry.

    A category folds when its share of the total is below threshold percent, or when it
    is the real OTHER category. The folded entry carries its members (name, amount).
    Folding happens only when at least two categories collapse: a single sub-threshold
    category that is not OTHER stays as its own entry, to avoid a lonely "Other" that
    equals one real category.
    """
    if (grand_total := sum(amounts.values())) == 0:
        return ()
    ordered = sorted(amounts.items(), key=lambda item: item[1], reverse=True)
    kept: list[GroupedExpense] = []
    folded: list[tuple[str, float]] = []
    folded_real_other = False
    for cat, amount in ordered:
        share = amount / grand_total * 100
        if cat == Category.OTHER:
            folded_real_other = True
            folded.append((category_name(str(cat)), amount))
        elif share < threshold:
            folded.append((category_name(str(cat)), amount))
        else:
            kept.append(GroupedExpense(category_name(str(cat)), amount))
    if not folded:
        return tuple(kept)
    if len(folded) == 1 and not folded_real_other:
        name, amount = folded[0]
        kept.append(GroupedExpense(name, amount))
        return tuple(kept)
    other_total = sum(amount for _name, amount in folded)
    kept.append(GroupedExpense(_("Other categories"), other_total, tuple(folded)))
    return tuple(kept)


def _slices(
    entries: tuple[GroupedExpense, ...],
    total: float,
    months: int,
) -> tuple[ExpenseSlice, ...]:
    """Turn grouped entries into donut segments, greying the folded 'Other' slice."""
    slices = []
    accumulated = 0.0
    palette_index = 0
    for entry in entries:
        fraction = entry.amount / total if total else 0.0
        if entry.members:
            color = _OTHER_COLOR
        else:
            color = _PALETTE[palette_index % len(_PALETTE)]
            palette_index += 1
        slices.append(
            ExpenseSlice(
                label=entry.label,
                amount=entry.amount,
                average=entry.amount / months,
                fraction=fraction,
                color=color,
                dash=round(fraction * _PIE_CIRCUMFERENCE, 2),
                offset=round(-accumulated * _PIE_CIRCUMFERENCE, 2),
                members=entry.members,
            )
        )
        accumulated += fraction
    return tuple(slices)


def _breakdown(app: ApplicationService, months: int) -> Breakdown:
    today = date.today()
    # Rolling window of exactly N months ending today (so average = total / N).
    criteria = OperationFilter(
        date_from=today + timedelta(days=1) - relativedelta(months=months),
        date_to=today,
        max_amount=0,
    )
    totals = app.get_category_totals(criteria)
    amounts = {category: abs(total) for category, total in totals.items() if total != 0}
    entries = _grouped_expenses(amounts, app.expense_breakdown_threshold)
    total = sum(entry.amount for entry in entries)
    slices = _slices(entries, total, months)
    return Breakdown(slices, total, _PIE_RADIUS, round(_PIE_CIRCUMFERENCE, 2))


@router.get("/trends")
async def trends(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    months: int = _DEFAULT_PERIOD,
) -> Response:
    """Render balance evolution and expense breakdown for the chosen window."""
    period = _period_from(months)
    breakdown = _breakdown(app, period)

    # A period change (HX-Request) swaps only the breakdown card, keeping the
    # balance chart and the scroll position untouched.
    if request.headers.get("HX-Request"):
        return render_template(
            request,
            "fragments/breakdown.html",
            active="trends",
            breakdown=breakdown,
            currency=app.currency,
            period=period,
            periods=_PERIODS,
            threshold=app.expense_breakdown_threshold,
        )

    # None = daily granularity, so the projected low point is actually visible.
    sparkline = _sparkline(
        app.get_balance_evolution_summary(None), app.currency, app.margin_threshold
    )
    spark_points = (
        [p._asdict() for p in sparkline.points] if sparkline is not None else []
    )
    return render_template(
        request,
        "trends.html",
        active="trends",
        sparkline=sparkline,
        spark_points=spark_points,
        breakdown=breakdown,
        currency=app.currency,
        period=period,
        periods=_PERIODS,
        threshold=app.expense_breakdown_threshold,
    )


def _period_from(raw: object) -> int:
    """Coerce a form-supplied month count to a valid period, defaulting otherwise."""
    try:
        months = int(str(raw))
    except (TypeError, ValueError):
        return _DEFAULT_PERIOD
    return months if months in _PERIODS else _DEFAULT_PERIOD


@router.post("/trends/threshold")
async def set_breakdown_threshold(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Persist the expense breakdown threshold (clamped to [0, 10]%) and re-render the
    donut. An unparseable value keeps the stored threshold."""
    form = await request.form()
    raw = str(form.get("threshold", "")).replace(",", ".").strip()
    try:
        clamped = min(_THRESHOLD_MAX, max(_THRESHOLD_MIN, float(raw)))
    except ValueError:
        clamped = app.expense_breakdown_threshold
    app.expense_breakdown_threshold = clamped

    months = _period_from(form.get("months"))
    return render_template(
        request,
        "fragments/breakdown.html",
        active="trends",
        breakdown=_breakdown(app, months),
        currency=app.currency,
        period=months,
        periods=_PERIODS,
        threshold=app.expense_breakdown_threshold,
    )
