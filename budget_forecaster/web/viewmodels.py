"""Read-only view models derived from ApplicationService data.

Replicates the review screen's category grouping and consumption logic so the
web month view and home health match the TUI for the same database.
"""

from datetime import date, datetime
from typing import NamedTuple

import pandas as pd

from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import (
    CategoryBudget,
    MarginInfo,
    MonthlySummary,
)
from budget_forecaster.web.formatting import category_name

_CONSUMPTION_TOLERANCE = 1.01  # 1% over before it counts as over budget


def month_to_date(raw: object) -> date:
    """Normalize a monthly-summary month key to a first-of-month date.

    pandas Timestamp is a datetime subclass, so it takes the datetime branch.
    """
    if isinstance(raw, datetime):
        return raw.date().replace(day=1)
    if isinstance(raw, date):
        return raw.replace(day=1)
    if isinstance(raw, str):
        timestamp = pd.Timestamp(raw)
        return date(timestamp.year, timestamp.month, 1)
    raise TypeError(f"Unsupported month key: {raw!r}")


def add_months(month: date, delta: int) -> date:
    """Return the first of the month delta months away from month."""
    index = month.year * 12 + (month.month - 1) + delta
    return date(index // 12, index % 12 + 1, 1)


class Consumption(NamedTuple):
    """Actual-vs-planned consumption for one category."""

    ratio: float
    over: bool
    bad: bool


def consumption(
    actual: float, planned: float, *, is_income: bool
) -> Consumption | None:
    """Compute the consumption bar state, or None when nothing is planned."""
    if planned == 0:
        return None
    ratio = abs(actual) / abs(planned)
    over = ratio > _CONSUMPTION_TOLERANCE
    if (planned > 0) != (actual > 0) and actual != 0:
        bad = planned > 0 > actual
    else:
        bad = (over and not is_income) or (
            not over and is_income and ratio < 1.0 / _CONSUMPTION_TOLERANCE
        )
    return Consumption(ratio=ratio, over=over, bad=bad)


class CategoryRow(NamedTuple):
    """One category line in the month view."""

    key: str
    planned: float
    actual: float
    forecast: float
    remaining: float
    is_income: bool
    is_forecasted: bool
    consumption: Consumption | None


class MonthView(NamedTuple):
    """The month review: category rows, totals, navigation and margin."""

    month: date
    prev_month: date
    next_month: date
    forecasted: tuple[CategoryRow, ...]
    unforecasted: tuple[CategoryRow, ...]
    total_planned: float
    total_actual: float
    total_forecast: float
    total_remaining: float
    margin: MarginInfo | None
    show_margin: bool


class MonthHealth(NamedTuple):
    """This-month expense health for the home glance."""

    month: date
    planned: float
    actual: float
    ratio: float | None
    rows: tuple[CategoryRow, ...]


def _row(key: str, data: CategoryBudget) -> CategoryRow:
    return CategoryRow(
        key=key,
        planned=data["planned"],
        actual=data["actual"],
        forecast=data["forecast"],
        remaining=data["forecast"] - data["actual"],
        is_income=data["is_income"],
        is_forecasted=data["planned"] != 0,
        consumption=consumption(
            data["actual"], data["planned"], is_income=data["is_income"]
        ),
    )


def _sorted_rows(rows: list[CategoryRow]) -> tuple[CategoryRow, ...]:
    # Expenses before incomes, then alphabetical by translated name.
    return tuple(sorted(rows, key=lambda r: (r.is_income, category_name(r.key))))


def _find_summary(
    summaries: list[MonthlySummary], month: date
) -> MonthlySummary | None:
    for summary in summaries:
        if month_to_date(summary["month"]) == month:
            return summary
    return None


def build_month_view(app: ApplicationService, month: date) -> MonthView:
    """Assemble the month review for the given first-of-month date."""
    summary = _find_summary(app.get_monthly_summary(), month)
    categories = summary["categories"] if summary else {}
    rows = [_row(key, data) for key, data in categories.items()]

    forecasted = _sorted_rows([r for r in rows if r.is_forecasted])
    unforecasted = _sorted_rows([r for r in rows if not r.is_forecasted])

    total_planned = sum(r.planned for r in rows)
    total_actual = sum(r.actual for r in rows)
    total_forecast = sum(r.forecast for r in rows)

    show_margin = month >= date.today().replace(day=1)
    margin = app.get_available_margin(month) if show_margin else None

    return MonthView(
        month=month,
        prev_month=add_months(month, -1),
        next_month=add_months(month, 1),
        forecasted=forecasted,
        unforecasted=unforecasted,
        total_planned=total_planned,
        total_actual=total_actual,
        total_forecast=total_forecast,
        total_remaining=total_forecast - total_actual,
        margin=margin,
        show_margin=show_margin and margin is not None,
    )


def build_month_health(app: ApplicationService, month: date) -> MonthHealth | None:
    """Summarize this month's expense consumption for the home glance."""
    if (summary := _find_summary(app.get_monthly_summary(), month)) is None:
        return None
    rows = [_row(key, data) for key, data in summary["categories"].items()]
    expenses = [r for r in rows if not r.is_income and r.is_forecasted]
    planned = sum(r.planned for r in expenses)
    actual = sum(r.actual for r in expenses)
    ratio = abs(actual) / abs(planned) if planned else None
    return MonthHealth(
        month=month,
        planned=planned,
        actual=actual,
        ratio=ratio,
        rows=_sorted_rows(expenses),
    )
