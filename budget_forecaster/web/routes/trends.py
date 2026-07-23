"""Tendances: balance evolution over time + expense breakdown by category."""

from datetime import date
from typing import NamedTuple

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_service import OperationFilter
from budget_forecaster.web.dependencies import get_app_service
from budget_forecaster.web.rendering import render_template
from budget_forecaster.web.viewmodels import add_months

router = APIRouter()

_PERIODS = (1, 3, 6, 12)
_DEFAULT_PERIOD = 3
_SPARK_WIDTH = 600
_SPARK_HEIGHT = 120


class BalancePoint(NamedTuple):
    """A balance-evolution sample placed on the sparkline viewBox."""

    day: date
    balance: float
    x: float
    y: float


class Sparkline(NamedTuple):
    """A balance sparkline ready to render as an SVG polyline."""

    points: tuple[BalancePoint, ...]
    polyline: str
    lowest: float
    highest: float
    width: int
    height: int


class ExpenseSlice(NamedTuple):
    """One category's expense total and its share of the largest."""

    key: str
    amount: float
    ratio: float


def _sparkline(samples: list[tuple[date, float]]) -> Sparkline | None:
    if len(samples) < 2:
        return None
    balances = [balance for _, balance in samples]
    lowest, highest = min(balances), max(balances)
    span = highest - lowest or 1.0
    last = len(samples) - 1
    points = []
    for index, (day, balance) in enumerate(samples):
        x = _SPARK_WIDTH * index / last
        y = _SPARK_HEIGHT * (1 - (balance - lowest) / span)
        points.append(BalancePoint(day, balance, round(x, 1), round(y, 1)))
    polyline = " ".join(f"{p.x},{p.y}" for p in points)
    return Sparkline(
        tuple(points), polyline, lowest, highest, _SPARK_WIDTH, _SPARK_HEIGHT
    )


def _expense_breakdown(
    app: ApplicationService, months: int
) -> tuple[ExpenseSlice, ...]:
    today = date.today()
    criteria = OperationFilter(
        date_from=add_months(today.replace(day=1), -months),
        date_to=today,
        max_amount=0,
    )
    totals = app.get_category_totals(criteria)
    amounts = {category: abs(total) for category, total in totals.items() if total != 0}
    if not amounts:
        return ()
    largest = max(amounts.values())
    ordered = sorted(amounts.items(), key=lambda item: item[1], reverse=True)
    return tuple(
        ExpenseSlice(str(category), amount, amount / largest)
        for category, amount in ordered
    )


@router.get("/tendances")
async def trends(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    months: int = _DEFAULT_PERIOD,
) -> Response:
    """Render balance evolution and expense breakdown for the chosen window."""
    period = months if months in _PERIODS else _DEFAULT_PERIOD
    return render_template(
        request,
        "trends.html",
        active="trends",
        sparkline=_sparkline(app.get_balance_evolution_summary()),
        expenses=_expense_breakdown(app, period),
        currency=app.currency,
        period=period,
        periods=_PERIODS,
    )
