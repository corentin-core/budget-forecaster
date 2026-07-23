"""Opérations: the filterable, paginated ledger (read-only)."""

from datetime import date
from typing import NamedTuple
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_service import OperationFilter
from budget_forecaster.web.dependencies import get_app_service
from budget_forecaster.web.rendering import render_template

router = APIRouter()

_PAGE_SIZE = 50


class OperationRow(NamedTuple):
    """A ledger line with its link status resolved for display."""

    operation: HistoricOperation
    linked: bool
    target_name: str


class LedgerFilters(NamedTuple):
    """Raw filter values from the query string, plus the parsed criteria."""

    search: str
    category: str
    date_from: str
    date_to: str
    uncategorized: bool
    criteria: OperationFilter


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


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
    date_from: str = "",
    date_to: str = "",
    uncategorized: bool = False,
) -> LedgerFilters:
    """Parse the ledger query parameters into filter criteria."""
    criteria = OperationFilter(
        search_text=search or None,
        category=_category(category),
        date_from=_date(date_from),
        date_to=_date(date_to),
        uncategorized_only=uncategorized,
    )
    return LedgerFilters(search, category, date_from, date_to, uncategorized, criteria)


def _query(filters: LedgerFilters) -> str:
    """Serialize the active filters for the 'show more' link (offset excluded)."""
    params = {}
    if filters.search:
        params["search"] = filters.search
    if filters.category:
        params["category"] = filters.category
    if filters.date_from:
        params["date_from"] = filters.date_from
    if filters.date_to:
        params["date_to"] = filters.date_to
    if filters.uncategorized:
        params["uncategorized"] = "true"
    return urlencode(params)


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
    offset: int = 0,
) -> Response:
    """Render the ledger page, or a fragment for filter/pagination requests."""
    matches = app.get_operations(filters.criteria)
    total = len(matches)
    rows = _rows(app, matches[offset : offset + _PAGE_SIZE])
    next_offset = offset + _PAGE_SIZE
    if request.headers.get("HX-Request"):
        # offset > 0 is a "show more" (append rows only); offset 0 is a filter
        # change (replace the whole ledger area, so the count refreshes too).
        template = (
            "fragments/ledger_rows.html" if offset else "fragments/ledger_area.html"
        )
    else:
        template = "operations.html"
    return render_template(
        request,
        template,
        active="operations",
        rows=rows,
        categories=tuple(Category),
        filters=filters,
        currency=app.currency,
        total=total,
        query=_query(filters),
        next_offset=next_offset if next_offset < total else None,
    )
