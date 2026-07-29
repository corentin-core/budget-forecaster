"""Read-only view models derived from ApplicationService data.

Groups categories and computes consumption for the web month view and home
health from the same database.
"""

from datetime import date, datetime, timedelta
from typing import NamedTuple

import pandas as pd
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.date_range import (
    DateRangeInterface,
    RecurringDateRange,
    RecurringDay,
)
from budget_forecaster.core.duration import DurationUnit, relativedelta_to_unit
from budget_forecaster.core.types import PlannedOperationId
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import (
    CategoryBudget,
    ForecastSourceType,
    MarginInfo,
    MonthlySummary,
)
from budget_forecaster.web.formatting import category_name

Target = Budget | PlannedOperation

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
    elif is_income:
        # Under-realized income (salary not received yet) is normal, not "bad".
        bad = False
    else:
        bad = over
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
    planned_expenses: tuple[CategoryRow, ...]
    planned_income: tuple[CategoryRow, ...]
    unforecasted: tuple[CategoryRow, ...]
    exp_planned: float
    exp_actual: float
    exp_forecast: float
    exp_remaining: float
    inc_planned: float
    inc_actual: float
    inc_forecast: float
    inc_remaining: float
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


class _SideTotals(NamedTuple):
    planned: float
    actual: float
    forecast: float
    remaining: float


def _side_totals(rows: list[CategoryRow], *, is_income: bool) -> _SideTotals:
    side = [r for r in rows if r.is_income == is_income]
    return _SideTotals(
        planned=sum(r.planned for r in side),
        actual=sum(r.actual for r in side),
        forecast=sum(r.forecast for r in side),
        remaining=sum(r.remaining for r in side),
    )


def build_month_view(app: ApplicationService, month: date) -> MonthView:
    """Assemble the month review for the given first-of-month date."""
    summary = _find_summary(app.get_monthly_summary(), month)
    categories = summary["categories"] if summary else {}
    rows = [_row(key, data) for key, data in categories.items()]

    forecasted = [r for r in rows if r.is_forecasted]
    planned_expenses = _sorted_rows([r for r in forecasted if not r.is_income])
    planned_income = _sorted_rows([r for r in forecasted if r.is_income])
    unforecasted = _sorted_rows([r for r in rows if not r.is_forecasted])

    exp = _side_totals(rows, is_income=False)
    inc = _side_totals(rows, is_income=True)
    total_forecast = exp.forecast + inc.forecast

    show_margin = month >= date.today().replace(day=1)
    margin = app.get_available_margin(month) if show_margin else None

    return MonthView(
        month=month,
        prev_month=add_months(month, -1),
        next_month=add_months(month, 1),
        planned_expenses=planned_expenses,
        planned_income=planned_income,
        unforecasted=unforecasted,
        exp_planned=exp.planned,
        exp_actual=exp.actual,
        exp_forecast=exp.forecast,
        exp_remaining=exp.remaining,
        inc_planned=inc.planned,
        inc_actual=inc.actual,
        inc_forecast=inc.forecast,
        inc_remaining=inc.remaining,
        total_planned=exp.planned + inc.planned,
        total_actual=exp.actual + inc.actual,
        total_forecast=total_forecast,
        total_remaining=total_forecast - exp.actual - inc.actual,
        margin=margin,
        show_margin=show_margin and margin is not None,
    )


class TargetFormView(NamedTuple):
    """Edit-form field values for a budget or planned operation."""

    kind: str  # "budget" | "planned"
    is_new: bool
    is_planned: bool
    has_duration: bool  # budgets carry an occurrence duration; planned ops don't
    target_id: int | None
    description: str
    amount: str
    category: str  # Category member name
    start_date: str
    duration_value: str
    duration_unit: str
    recurring: bool
    period_value: str
    period_unit: str
    end_date: str
    can_split: bool
    keywords: str
    approx_days: str
    approx_ratio: str


def _amount_field(value: float) -> str:
    return f"{float(value):g}"


def _duration_fields(rd: relativedelta | None) -> tuple[str, str]:
    value, unit = relativedelta_to_unit(rd or relativedelta(months=1))
    return str(value), unit.value


def _end_date_field(range_: DateRangeInterface) -> str:
    if isinstance(range_, (RecurringDateRange, RecurringDay)):
        if range_.last_date != date.max:
            return range_.last_date.strftime("%Y-%m-%d")
    return ""


def build_target_form(
    kind: str, target: Target | None, *, default_category: str
) -> TargetFormView:
    """Assemble the edit-form values for a new or existing target."""
    is_new = target is None or target.id is None
    is_planned = kind == "planned"
    recurring_type = RecurringDay if is_planned else RecurringDateRange
    recurring = target is not None and isinstance(target.date_range, recurring_type)

    if target is None:
        duration_value, duration_unit = _duration_fields(None)
        period_value, period_unit = _duration_fields(None)
        return TargetFormView(
            kind=kind,
            is_new=True,
            is_planned=is_planned,
            has_duration=not is_planned,
            target_id=None,
            description="",
            amount="100" if is_planned else "-100",
            category=default_category,
            start_date=date.today().strftime("%Y-%m-%d"),
            duration_value=duration_value,
            duration_unit=duration_unit,
            recurring=False,
            period_value=period_value,
            period_unit=period_unit,
            end_date="",
            can_split=False,
            keywords="",
            approx_days="5",
            approx_ratio="0.05",
        )

    period = (
        target.date_range.period
        if isinstance(target.date_range, (RecurringDateRange, RecurringDay))
        else None
    )
    period_value, period_unit = _duration_fields(period)
    duration_value, duration_unit = _duration_fields(
        None if is_planned else target.date_range.duration
    )
    keywords, approx_days, approx_ratio = "", "5", "0.05"
    if isinstance(target, PlannedOperation):
        keywords = ", ".join(sorted(target.matcher.description_hints))
        approx_days = str(
            int(target.matcher.approximation_date_range.total_seconds() / 86400)
        )
        approx_ratio = str(target.matcher.approximation_amount_ratio)

    return TargetFormView(
        kind=kind,
        is_new=is_new,
        is_planned=is_planned,
        has_duration=not is_planned,
        target_id=target.id,
        description=target.description,
        amount=_amount_field(target.amount),
        category=target.category.name,
        start_date=target.date_range.start_date.strftime("%Y-%m-%d"),
        duration_value=duration_value,
        duration_unit=duration_unit,
        recurring=recurring,
        period_value=period_value,
        period_unit=period_unit,
        end_date=_end_date_field(target.date_range),
        can_split=not is_new and recurring,
        keywords=keywords,
        approx_days=approx_days,
        approx_ratio=approx_ratio,
    )


def target_form_from_submitted(
    kind: str, submitted: dict[str, str], target_id: int | None
) -> TargetFormView:
    """Rebuild the form view from raw submitted values, so a validation error
    re-renders with what the user typed rather than the stored target."""
    get = submitted.get
    return TargetFormView(
        kind=kind,
        is_new=target_id is None,
        is_planned=kind == "planned",
        has_duration=kind != "planned",
        target_id=target_id,
        description=get("description", ""),
        amount=get("amount", ""),
        category=get("category", ""),
        start_date=get("start_date", ""),
        duration_value=get("duration_value", "1"),
        duration_unit=get("duration_unit", "months"),
        recurring=get("recurring") == "yes",
        period_value=get("period_value", "1"),
        period_unit=get("period_unit", "months"),
        end_date=get("end_date", ""),
        can_split=False,
        keywords=get("keywords", ""),
        approx_days=get("approx_days", "5"),
        approx_ratio=get("approx_ratio", "0.05"),
    )


class TargetRow(NamedTuple):
    """One line in the /targets management list."""

    kind: str  # "budget" | "planned"
    id: int
    description: str
    amount: float
    category: str
    period_label: str
    range_label: str
    active: bool  # still running (not fully in the past)


def _period_label(range_: DateRangeInterface) -> str:
    if not isinstance(range_, (RecurringDateRange, RecurringDay)):
        return _("one-off")
    value, unit = relativedelta_to_unit(range_.period)
    unit_word = {
        DurationUnit.DAYS: _("days"),
        DurationUnit.WEEKS: _("weeks"),
        DurationUnit.MONTHS: _("months"),
        DurationUnit.YEARS: _("years"),
    }[unit]
    return f"{value} {unit_word}"


def _range_label(range_: DateRangeInterface) -> str:
    if not isinstance(range_, (RecurringDateRange, RecurringDay)):
        return range_.start_date.strftime("%d/%m/%Y")
    start = range_.start_date.strftime("%m/%Y")
    if range_.last_date == date.max:
        return _("since {}").format(start)
    return f"{start} → {range_.last_date.strftime('%m/%Y')}"


def _target_row(kind: str, target: Target) -> TargetRow:
    return TargetRow(
        kind=kind,
        id=target.id or 0,
        description=target.description,
        amount=float(target.amount),
        category=target.category.value,
        period_label=_period_label(target.date_range),
        range_label=_range_label(target.date_range),
        active=target.date_range.last_date >= date.today(),
    )


def build_target_list(
    app: ApplicationService,
) -> tuple[tuple[TargetRow, ...], tuple[TargetRow, ...]]:
    """Return (budgets, planned operations) as management-list rows."""
    budgets = tuple(_target_row("budget", b) for b in app.get_all_budgets())
    planned = tuple(_target_row("planned", p) for p in app.get_all_planned_operations())
    return budgets, planned


class SourceRow(NamedTuple):
    """A planned source (budget or planned op) inside a category drill-down."""

    kind: str  # "budget" | "planned"
    source_id: int | None
    description: str
    amount: float
    periodicity: str


class AttributedOpRow(NamedTuple):
    """An operation attributed to a category inside the drill-down."""

    operation_id: int
    operation_date: date
    description: str
    amount: float
    link_target_name: str
    cross_month_annotation: str


class CategoryDetailView(NamedTuple):
    """The Mois drill-down: a category's planned sources + attributed operations."""

    category: str  # Category value, as used in the URL
    category_key: str  # Category member name, for prefilling the add form
    month: date
    sources: tuple[SourceRow, ...]
    operations: tuple[AttributedOpRow, ...]
    total_planned: float
    total_actual: float


def build_category_detail(
    app: ApplicationService, category: str, month: date
) -> CategoryDetailView:
    """Assemble the drill-down for one category in one month."""
    detail = app.get_category_detail(category, month)
    category_key = detail["category"].name
    sources = tuple(
        SourceRow(
            kind=(
                "planned"
                if s["forecast_source_type"] is ForecastSourceType.PLANNED_OPERATION
                else "budget"
            ),
            source_id=s["source_id"],
            description=s["description"],
            amount=s["amount"],
            periodicity=s["periodicity"],
        )
        for s in detail["planned_sources"]
    )
    operations = tuple(
        AttributedOpRow(
            operation_id=op["operation_id"],
            operation_date=op["operation_date"],
            description=op["description"],
            amount=op["amount"],
            link_target_name=op["link_target_name"],
            cross_month_annotation=op["cross_month_annotation"],
        )
        for op in detail["operations"]
    )
    return CategoryDetailView(
        category=category,
        category_key=category_key,
        month=month,
        sources=sources,
        operations=operations,
        total_planned=detail["total_planned"],
        total_actual=detail["total_actual"],
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
    # Heaviest budgets first, so the home glance surfaces what matters.
    by_weight = tuple(sorted(expenses, key=lambda r: abs(r.planned), reverse=True))
    return MonthHealth(
        month=month,
        planned=planned,
        actual=actual,
        ratio=ratio,
        rows=by_weight,
    )


def margin_status(margin: MarginInfo | None) -> str | None:
    """Colour bucket for the available margin: bad below the threshold, warn when
    the buffer is thin, good otherwise."""
    if margin is None:
        return None
    if margin["available_margin"] < 0:
        return "bad"
    if margin["available_margin"] < margin["threshold"]:
        return "warn"
    return "good"


class OverdueRow(NamedTuple):
    """One row of the Accueil overdue card."""

    planned_operation_id: PlannedOperationId
    iteration_date: date
    description: str
    amount: float
    currency: str
    days_overdue: int
    counted_on: date | None
    """When the forecast still counts the amount; None when it no longer does."""

    postponed_to: date | None
    """The date the user had chosen, when it passed with nothing matching it."""

    next_iteration: date | None
    """The operation's next own iteration, offered as the postponement default."""

    earliest_postpone: date
    """The floor of the date field: forward of the iteration, and of today."""


class OverdueCard(NamedTuple):
    """The overdue card's state, including why it may refuse to act."""

    rows: tuple[OverdueRow, ...]
    sync_broken: bool
    """A sync failed, so operations are probably missing: no decision offered."""

    show_data_horizon: bool
    """The balance date is old enough to be worth stating before deciding."""

    balance_date: date
    tomorrow: date


_HORIZON_WORTH_SAYING = timedelta(days=3)


def _next_own_iteration(op: PlannedOperation, after: date) -> date | None:
    """The operation's first iteration strictly after the given date.

    Offered as the postponement default, so it has to be ahead of today: an
    occurrence that has already passed would be late again at once.
    """
    next_range = op.date_range.next_date_range(after)
    return next_range.start_date if next_range is not None else None


def build_overdue_card(
    app: ApplicationService, *, sync_broken: bool = False
) -> OverdueCard:
    """Build the overdue card: what awaits a decision, and whether to offer any.

    A failed sync means operations are probably missing, so the card states that
    and offers nothing rather than inviting the user to stop counting a payment
    that did happen. An old balance date is not enough to refuse: someone who
    imports their statements by hand always has one, and the card says where the
    data stops instead.

    Args:
        app: The application service.
        sync_broken: True when a sync alert is showing.
    """
    balance_date = app.balance_date
    today = date.today()
    operations = {
        op.id: op for op in app.get_all_planned_operations() if op.id is not None
    }
    rows: list[OverdueRow] = []
    for overdue in app.get_overdue_iterations():
        op = operations[overdue.planned_operation_id]
        rows.append(
            OverdueRow(
                planned_operation_id=overdue.planned_operation_id,
                iteration_date=overdue.iteration_date,
                description=overdue.description,
                amount=overdue.amount,
                currency=overdue.currency,
                days_overdue=overdue.days_overdue,
                counted_on=overdue.counted_on,
                postponed_to=overdue.postponed_to,
                next_iteration=_next_own_iteration(op, max(balance_date, today)),
                earliest_postpone=max(overdue.iteration_date, today)
                + timedelta(days=1),
            )
        )
    return OverdueCard(
        rows=tuple(rows),
        sync_broken=sync_broken,
        show_data_horizon=today - balance_date > _HORIZON_WORTH_SAYING,
        balance_date=balance_date,
        tomorrow=today + timedelta(days=1),
    )
