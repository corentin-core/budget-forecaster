"""Opérations: the filterable ledger plus inline/bulk categorize and linking."""

from datetime import date
from typing import NamedTuple
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from starlette.datastructures import FormData

from budget_forecaster.core.types import Category, LinkType
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.exceptions import BudgetForecasterError
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_service import OperationFilter
from budget_forecaster.web import linking
from budget_forecaster.web.dependencies import get_app_service, refresh_forecast
from budget_forecaster.web.formatting import sorted_categories
from budget_forecaster.web.redirects import safe_local_path
from budget_forecaster.web.rendering import render_template

router = APIRouter()

_PAGE_SIZE = 50


class OperationRow(NamedTuple):
    """A ledger line with its link status resolved for display."""

    operation: HistoricOperation
    linked: bool
    target_kind: str  # "budget" | "planned", empty when unlinked
    target_id: int
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


def filters_from_form(form: FormData) -> LedgerFilters:
    """Parse the filter bar from a posted body: htmx sends it there, not in the URL."""
    return get_filters(
        search=str(form.get("search", "")),
        category=str(form.get("category", "")),
        date_from=str(form.get("date_from", "")),
        date_to=str(form.get("date_to", "")),
        uncategorized=str(form.get("uncategorized", "")) == "true",
    )


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
    budgets = {b.id: b.description for b in app.get_all_budgets() if b.id is not None}
    planned = {
        p.id: p.description
        for p in app.get_all_planned_operations()
        if p.id is not None
    }
    links = {link.operation_unique_id: link for link in app.get_all_links()}
    rows = []
    for operation in operations:
        if (link := links.get(operation.unique_id)) is None:
            rows.append(OperationRow(operation, False, "", 0, ""))
            continue
        is_budget = link.target_type is LinkType.BUDGET
        names = budgets if is_budget else planned
        rows.append(
            OperationRow(
                operation,
                True,
                "budget" if is_budget else "planned",
                link.target_id,
                linking.target_display_name(names, link.target_id),
            )
        )
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
        categories=sorted_categories(),
        filters=filters,
        currency=app.currency,
        total=total,
        query=_query(filters),
        next_offset=next_offset if next_offset < total else None,
    )


def _safe_back(value: str) -> str:
    """Only allow same-app relative paths as a back link."""
    return safe_local_path(value, "/operations")


@router.get("/operations/{operation_id}")
async def operation_detail(
    operation_id: int,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    return_to: str = "/operations",
) -> Response:
    """Render the operation detail page."""
    operation = app.get_operation_by_id(operation_id)
    return render_template(
        request,
        "operation_detail.html",
        active="operations",
        operation=operation,
        current=linking.current_link(app, operation_id),
        categories=sorted_categories(),
        currency=app.currency,
        return_to=_safe_back(return_to),
    )


@router.get("/operations/{operation_id}/link")
async def link_page(
    operation_id: int,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    target_type: str = "planned",
    return_to: str = "/operations",
) -> Response:
    """Render the link page: operation info + score-ranked candidates."""
    operation = app.get_operation_by_id(operation_id)
    candidates = linking.build_candidates(app, operation, target_type)
    shown, hidden = linking.filter_candidates(candidates, "", False)
    return render_template(
        request,
        "link.html",
        active="operations",
        operation=operation,
        target_type=target_type,
        candidates=shown,
        hidden_count=hidden,
        current=linking.current_link(app, operation_id),
        currency=app.currency,
        return_to=_safe_back(return_to),
    )


@router.get("/operations/{operation_id}/link/candidates")
async def link_candidates(
    operation_id: int,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    target_type: str = "planned",
    q: str = "",
    show_all: bool = Query(default=False, alias="all"),
) -> Response:
    """Return the filtered candidate list fragment (search / show-all)."""
    operation = app.get_operation_by_id(operation_id)
    candidates = linking.build_candidates(app, operation, target_type)
    shown, hidden = linking.filter_candidates(candidates, q, show_all)
    return render_template(
        request,
        "fragments/candidate_list.html",
        active="operations",
        operation=operation,
        candidates=shown,
        hidden_count=hidden,
        target_type=target_type,
        currency=app.currency,
    )


@router.get("/operations/{operation_id}/link/iterations")
async def link_iterations(
    operation_id: int,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    target_type: str = "planned",
    target_id: int = 0,
    offset: int = 0,
) -> Response:
    """Render the iteration picker fragment for a chosen target."""
    operation = app.get_operation_by_id(operation_id)
    target = linking.target_object(app, target_type, target_id)
    window, iterations, best_iso = linking.build_iterations(operation, target, offset)
    return render_template(
        request,
        "fragments/link_iterations.html",
        active="operations",
        operation_id=operation_id,
        target_type=target_type,
        target_id=target_id,
        offset=offset,
        window=window,
        iterations=iterations,
        best_iso=best_iso,
        target_name=target.description,
    )


@router.post("/operations/{operation_id}/link")
async def create_link(
    operation_id: int,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Create a manual link to the chosen target iteration."""
    form = await request.form()
    target_type = str(form.get("target_type", "planned"))
    back = RedirectResponse(url=f"/operations/{operation_id}/link", status_code=303)
    try:
        target_id = int(str(form.get("target_id", "")))
        iteration_date = date.fromisoformat(str(form.get("iteration_date", "")))
        operation = app.get_operation_by_id(operation_id)
        target = linking.target_object(app, target_type, target_id)
    except (ValueError, BudgetForecasterError):
        return back
    app.create_manual_link(operation, target, iteration_date)
    refresh_forecast(app)
    return RedirectResponse(url="/operations", status_code=303)


@router.post("/operations/{operation_id}/unlink")
async def unlink(
    operation_id: int,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Remove the operation's link."""
    app.delete_link(operation_id)
    refresh_forecast(app)
    return RedirectResponse(url="/operations", status_code=303)


@router.post("/operations/{operation_id}/categorize")
async def categorize_one(
    operation_id: int,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    filters: LedgerFilters = Depends(get_filters),
    view: str = "row",
) -> Response:
    """Categorize a single operation; swap back what the caller shows of it.

    The ledger asks for its row, the detail page for its category field. Both get
    the badge refreshed out of band.
    """
    form = await request.form()
    if (category := _category(str(form.get("category", "")))) is None:
        return Response(status_code=400)
    app.categorize_operations((operation_id,), category)
    app.save_operation_changes()
    refresh_forecast(app)
    operation = app.get_operation_by_id(operation_id)
    if view == "detail":
        return render_template(
            request,
            "fragments/detail_cat_and_badge.html",
            active="operations",
            operation=operation,
            categories=sorted_categories(),
        )
    return render_template(
        request,
        "fragments/row_and_badge.html",
        active="operations",
        row=_rows(app, (operation,))[0],
        categories=sorted_categories(),
        currency=app.currency,
        query=_query(filters),
    )


@router.post("/operations/categorize")
async def categorize_bulk(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Categorize the selected operations; re-render the ledger + badge."""
    form = await request.form()
    filters = filters_from_form(form)
    category = _category(str(form.get("bulk_category", "")))
    ids = tuple(
        int(i)
        for i in form.getlist("ids")
        if isinstance(i, str) and i.lstrip("-").isdigit()
    )
    if category is None or not ids:
        query = _query(filters)
        url = f"/operations?{query}" if query else "/operations"
        return RedirectResponse(url=url, status_code=303)
    app.categorize_operations(ids, category)
    app.save_operation_changes()
    refresh_forecast(app)
    matches = app.get_operations(filters.criteria)
    return render_template(
        request,
        "fragments/area_and_badge.html",
        active="operations",
        rows=_rows(app, matches[:_PAGE_SIZE]),
        categories=sorted_categories(),
        filters=filters,
        currency=app.currency,
        total=len(matches),
        query=_query(filters),
        next_offset=_PAGE_SIZE if _PAGE_SIZE < len(matches) else None,
    )
