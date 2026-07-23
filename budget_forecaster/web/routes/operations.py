"""Opérations: the filterable ledger (read-only)."""

from datetime import date, timedelta
from typing import NamedTuple

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_service import OperationFilter
from budget_forecaster.web.dependencies import get_app_service
from budget_forecaster.web.rendering import render_template
from budget_forecaster.web.viewmodels import add_months

router = APIRouter()


class OperationRow(NamedTuple):
    """A ledger line with its link status resolved for display."""

    operation: HistoricOperation
    linked: bool
    target_name: str


class LedgerFilters(NamedTuple):
    """Raw filter values from the query string, plus the parsed criteria."""

    search: str
    category: str
    month: str
    uncategorized: bool
    criteria: OperationFilter


def _month_bounds(month: str) -> tuple[date | None, date | None]:
    if not month:
        return None, None
    try:
        year, num = month.split("-")
        start = date(int(year), int(num), 1)
    except (ValueError, TypeError):
        return None, None
    return start, add_months(start, 1) - timedelta(days=1)


def _category(value: str) -> Category | None:
    if not value:
        return None
    try:
        return Category(value)
    except ValueError:
        return None


def get_filters(
    search: str = "",
    category: str = "",
    month: str = "",
    uncategorized: bool = False,
) -> LedgerFilters:
    """Parse the ledger query parameters into filter criteria."""
    date_from, date_to = _month_bounds(month)
    criteria = OperationFilter(
        search_text=search or None,
        category=_category(category),
        date_from=date_from,
        date_to=date_to,
        uncategorized_only=uncategorized,
    )
    return LedgerFilters(search, category, month, uncategorized, criteria)


def _rows(
    app: ApplicationService, operations: tuple[HistoricOperation, ...]
) -> tuple[OperationRow, ...]:
    budgets = {b.id: b.description for b in app.get_all_budgets()}
    planned = {p.id: p.description for p in app.get_all_planned_operations()}
    links = {link.operation_unique_id: link for link in app.get_all_links()}
    rows = []
    for operation in operations:
        if (link := links.get(operation.unique_id)) is None:
            rows.append(OperationRow(operation, False, ""))
            continue
        if link.target_type is LinkType.BUDGET:
            name = budgets.get(link.target_id, "")
        else:
            name = planned.get(link.target_id, "")
        rows.append(OperationRow(operation, True, name))
    return tuple(rows)


@router.get("/operations")
async def list_operations(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    filters: LedgerFilters = Depends(get_filters),
) -> Response:
    """Render the ledger, filtered by the query parameters."""
    rows = _rows(app, app.get_operations(filters.criteria))
    template = (
        "fragments/operation_rows.html"
        if request.headers.get("HX-Request")
        else "operations.html"
    )
    return render_template(
        request,
        template,
        active="operations",
        rows=rows,
        categories=tuple(Category),
        filters=filters,
        currency=app.currency,
    )
