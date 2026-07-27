"""Parse budget / planned-operation edit forms into domain objects.

Builds targets from the edit form fields: description, amount, category, start
date, optional recurrence (period + end), and — for budgets — an occurrence
duration. Every parse failure raises FormError with a translated, user-facing
message.
"""

from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import NamedTuple

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
    SingleDay,
)
from budget_forecaster.core.duration import DurationUnit, unit_to_relativedelta
from budget_forecaster.core.types import BudgetId, Category, PlannedOperationId
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.i18n import _

Form = Mapping[str, str]


class FormError(ValueError):
    """A form value failed validation; the message is safe to show the user."""


def form_to_dict(form: Mapping[str, object]) -> dict[str, str]:
    """Keep only string form fields, dropping any file uploads, so the parsers
    get a plain str mapping."""
    return {key: value for key, value in form.items() if isinstance(value, str)}


def _amount(form: Form, currency: str) -> Amount:
    try:
        return Amount(float(form.get("amount", "").strip()), currency)
    except ValueError as exc:
        raise FormError(_("Amount must be a number")) from exc


def _category(form: Form) -> Category:
    try:
        return Category[form.get("category", "").strip()]
    except KeyError as exc:
        raise FormError(_("Invalid category")) from exc


def _required_date(form: Form, key: str) -> date:
    try:
        return datetime.strptime(form.get(key, "").strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise FormError(_("Date must be in YYYY-MM-DD format")) from exc


def _optional_date(form: Form, key: str) -> date | None:
    if not form.get(key, "").strip():
        return None
    return _required_date(form, key)


def _duration(form: Form, value_key: str, unit_key: str) -> relativedelta:
    try:
        if (value := int(form.get(value_key, "").strip())) <= 0:
            raise ValueError
    except ValueError as exc:
        raise FormError(_("Duration must be a positive integer")) from exc
    try:
        unit = DurationUnit(form.get(unit_key, "").strip())
    except ValueError as exc:
        raise FormError(_("Unit is required")) from exc
    return unit_to_relativedelta(value, unit)


def _optional_duration(
    form: Form, value_key: str, unit_key: str
) -> relativedelta | None:
    if not form.get(value_key, "").strip():
        return None
    return _duration(form, value_key, unit_key)


def _description(form: Form) -> str:
    if not (description := form.get("description", "").strip()):
        raise FormError(_("Description is required"))
    return description


def parse_budget(form: Form, currency: str, budget_id: BudgetId | None) -> Budget:
    """Build a Budget from the edit form, or raise FormError."""
    start = _required_date(form, "start_date")
    duration = _duration(form, "duration_value", "duration_unit")
    inner = DateRange(start, duration)

    date_range: DateRange | RecurringDateRange
    if form.get("recurring") == "yes":
        end = _optional_date(form, "end_date")
        if end is not None and end < start:
            raise FormError(_("End date cannot be before the start date"))
        period = _duration(form, "period_value", "period_unit")
        date_range = RecurringDateRange(inner, period, end)
    elif _optional_date(form, "end_date") is not None:
        raise FormError(_("End date only applies to recurring operations"))
    else:
        date_range = inner

    return Budget(
        record_id=budget_id,
        description=_description(form),
        amount=_amount(form, currency),
        category=_category(form),
        date_range=date_range,
    )


def parse_planned(
    form: Form, currency: str, op_id: PlannedOperationId | None
) -> PlannedOperation:
    """Build a PlannedOperation from the edit form, or raise FormError."""
    start = _required_date(form, "start_date")

    date_range: SingleDay | RecurringDay
    if form.get("recurring") == "yes":
        end = _optional_date(form, "end_date")
        if end is not None and end < start:
            raise FormError(_("End date cannot be before the start date"))
        period = _duration(form, "period_value", "period_unit")
        date_range = RecurringDay(start, period, end)
    elif _optional_date(form, "end_date") is not None:
        raise FormError(_("End date only applies to recurring operations"))
    else:
        date_range = SingleDay(start)

    operation = PlannedOperation(
        record_id=op_id,
        description=_description(form),
        amount=_amount(form, currency),
        category=_category(form),
        date_range=date_range,
    )
    _apply_matcher_params(operation, form)
    return operation


def _apply_matcher_params(operation: PlannedOperation, form: Form) -> None:
    """Set matcher keywords and tolerances from the optional advanced fields,
    keeping the domain defaults when a field is left blank."""
    hints_str = form.get("keywords", "").strip()
    hints = {h.strip() for h in hints_str.split(",") if h.strip()}

    approx_days_str = form.get("approx_days", "").strip()
    try:
        if (approx_days := int(approx_days_str) if approx_days_str else 5) < 0:
            raise ValueError
    except ValueError as exc:
        raise FormError(_("Date tolerance must be a positive integer")) from exc

    approx_ratio_str = form.get("approx_ratio", "").strip()
    try:
        if (approx_ratio := float(approx_ratio_str) if approx_ratio_str else 0.05) < 0:
            raise ValueError
    except ValueError as exc:
        raise FormError(_("Amount tolerance must be a number")) from exc

    operation.set_matcher_params(
        description_hints=hints,
        approximation_date_range=timedelta(days=approx_days),
        approximation_amount_ratio=approx_ratio,
    )


class BudgetSplit(NamedTuple):
    """Post-split budget values; each None keeps the original."""

    split_date: date
    new_amount: Amount | None
    new_period: relativedelta | None
    new_duration: relativedelta | None


class PlannedSplit(NamedTuple):
    """Post-split planned-operation values; each None keeps the original."""

    split_date: date
    new_amount: Amount | None
    new_period: relativedelta | None


def _split_amount(form: Form, currency: str) -> Amount | None:
    if not form.get("split_amount", "").strip():
        return None
    try:
        return Amount(float(form["split_amount"].strip()), currency)
    except ValueError as exc:
        raise FormError(_("Amount must be a number")) from exc


def parse_budget_split(form: Form, currency: str) -> BudgetSplit:
    """Parse the split section of the budget form, or raise FormError."""
    return BudgetSplit(
        split_date=_required_date(form, "split_date"),
        new_amount=_split_amount(form, currency),
        new_period=_optional_duration(form, "split_period_value", "split_period_unit"),
        new_duration=_optional_duration(
            form, "split_duration_value", "split_duration_unit"
        ),
    )


def parse_planned_split(form: Form, currency: str) -> PlannedSplit:
    """Parse the split section of the planned-operation form, or raise FormError."""
    return PlannedSplit(
        split_date=_required_date(form, "split_date"),
        new_amount=_split_amount(form, currency),
        new_period=_optional_duration(form, "split_period_value", "split_period_unit"),
    )
