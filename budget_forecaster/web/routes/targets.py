"""Budget and planned-operation management: the /targets list, per-target edit
pages, and the create / update / delete / split writes.

A ``kind`` path segment ("budget" | "planned") selects the target type; both map
to symmetric ApplicationService methods. Every write refreshes the forecast.
"""

import logging
from typing import NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.exceptions import BudgetForecasterError
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web import forms, linking
from budget_forecaster.web.dependencies import get_app_service, refresh_forecast
from budget_forecaster.web.formatting import sorted_categories
from budget_forecaster.web.redirects import safe_local_path
from budget_forecaster.web.rendering import render_template
from budget_forecaster.web.viewmodels import (
    OperationSeed,
    Target,
    TargetFormView,
    build_operation_seed,
    build_planned_form_from_operation,
    build_target_form,
    build_target_list,
    target_form_from_submitted,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_PLANNED = "planned"


def _safe_return_to(value: str | None) -> str:
    """Keep redirects inside the app: only same-origin relative paths."""
    return safe_local_path(value, "/targets")


def _require_kind(kind: str) -> None:
    if kind not in ("budget", _PLANNED):
        raise HTTPException(status_code=404)


def _get_target(app: ApplicationService, kind: str, target_id: int) -> Target:
    if kind == _PLANNED:
        return app.get_planned_operation_by_id(target_id)
    return app.get_budget_by_id(target_id)


class TargetFilters(NamedTuple):
    """Parsed /targets query state: which list, and how it's filtered."""

    view: str
    query: str
    category: str
    active_only: bool


def get_target_filters(
    view: str = "budget",
    q: str = "",
    category: str = "",
    active: str = "",
    submitted: str = "",
) -> TargetFilters:
    """Parse the management filters; default to active-only until the form is
    submitted, then honour the checkbox."""
    active_only = (active == "true") if submitted else True
    return TargetFilters(view, q, category, active_only)


def _filter_rows(rows: tuple, filters: TargetFilters) -> tuple:
    """Narrow management rows by search text, category value and active state."""
    needle = filters.query.casefold()
    return tuple(
        r
        for r in rows
        if (not filters.active_only or r.active)
        and (not filters.category or r.category == filters.category)
        and (not needle or needle in r.description.casefold())
    )


@router.get("/targets")
async def targets_list(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    filters: TargetFilters = Depends(get_target_filters),
) -> Response:
    """Render the management page: budgets or planned operations (one at a time)."""
    budgets, planned = build_target_list(app)
    rows = planned if filters.view == "planned" else budgets
    return render_template(
        request,
        "targets.html",
        active="targets",
        rows=_filter_rows(rows, filters),
        view=filters.view,
        query=filters.query,
        category=filters.category,
        active_only=filters.active_only,
        categories=sorted_categories(),
        currency=app.currency,
    )


def _source_operation(
    app: ApplicationService, operation_id: int
) -> HistoricOperation | None:
    """The operation a form is seeded from, or None when it is not seeded.

    A stale or tampered id is treated as no seed rather than an error: the form
    still works, it just starts empty.
    """
    if operation_id <= 0:
        return None
    try:
        return app.get_operation_by_id(operation_id)
    except BudgetForecasterError:
        logger.warning("No operation %d to seed the form from", operation_id)
        return None


def _submitted_source(
    app: ApplicationService, submitted: dict[str, str]
) -> HistoricOperation | None:
    """The seed operation carried through the form, if any."""
    raw = submitted.get("source_operation_id", "")
    return _source_operation(app, int(raw)) if raw.lstrip("-").isdigit() else None


@router.get("/targets/{kind}/new")
async def new_target(
    kind: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    category: str = "OTHER",
    return_to: str = "/targets",
    from_operation: int = 0,
) -> Response:
    """Render the create form, seeded from an operation when one is given."""
    _require_kind(kind)
    operation = None
    if kind == _PLANNED:
        operation = _source_operation(app, from_operation)
    if operation is None:
        form = build_target_form(kind, None, default_category=category)
        seed = None
    else:
        form = build_planned_form_from_operation(operation)
        seed = build_operation_seed(app, operation)
    return _render_edit(request, app, form, _safe_return_to(return_to), seed=seed)


@router.get("/targets/{kind}/{target_id}")
async def edit_target(
    kind: str,
    target_id: int,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    return_to: str = "/targets",
) -> Response:
    """Render the edit form for an existing budget or planned operation."""
    _require_kind(kind)
    target = _get_target(app, kind, target_id)
    form = build_target_form(kind, target, default_category="OTHER")
    return _render_edit(request, app, form, _safe_return_to(return_to))


@router.post("/targets/{kind}")
async def create_target(
    kind: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Create a budget or planned operation from the submitted form."""
    _require_kind(kind)
    return await _write(request, app, kind, target_id=None, action="create")


@router.post("/targets/{kind}/{target_id}")
async def update_target(
    kind: str,
    target_id: int,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Update an existing budget or planned operation."""
    _require_kind(kind)
    return await _write(request, app, kind, target_id=target_id, action="update")


@router.post("/targets/{kind}/{target_id}/delete")
async def delete_target(
    kind: str,
    target_id: int,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Delete a budget or planned operation."""
    _require_kind(kind)
    if kind == _PLANNED:
        app.delete_planned_operation(target_id)
    else:
        app.delete_budget(target_id)
    refresh_forecast(app)
    submitted = forms.form_to_dict(await request.form())
    return RedirectResponse(
        url=_safe_return_to(submitted.get("return_to")), status_code=303
    )


@router.post("/targets/{kind}/{target_id}/split")
async def split_target(
    kind: str,
    target_id: int,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Split a recurring budget or planned operation at a date."""
    _require_kind(kind)
    submitted = forms.form_to_dict(await request.form())
    try:
        if kind == _PLANNED:
            planned_split = forms.parse_planned_split(submitted, app.currency)
            app.split_planned_operation_at_date(
                target_id,
                planned_split.split_date,
                planned_split.new_amount,
                planned_split.new_period,
            )
        else:
            budget_split = forms.parse_budget_split(submitted, app.currency)
            app.split_budget_at_date(
                target_id,
                budget_split.split_date,
                budget_split.new_amount,
                budget_split.new_period,
                budget_split.new_duration,
            )
    except (forms.FormError, ValueError) as exc:
        form = build_target_form(
            kind, _get_target(app, kind, target_id), default_category="OTHER"
        )
        return _render_edit(
            request,
            app,
            form,
            _safe_return_to(submitted.get("return_to")),
            error=str(exc),
        )
    refresh_forecast(app)
    return RedirectResponse(
        url=_safe_return_to(submitted.get("return_to")), status_code=303
    )


async def _write(
    request: Request,
    app: ApplicationService,
    kind: str,
    *,
    target_id: int | None,
    action: str,
) -> Response:
    """Parse and persist a create/update, or re-render the form on error."""
    submitted = forms.form_to_dict(await request.form())
    is_planned = kind == _PLANNED
    try:
        if is_planned:
            op = forms.parse_planned(submitted, app.currency, target_id)
            if action == "create":
                _link_source(app, submitted, app.add_planned_operation(op))
            else:
                app.update_planned_operation(op)
        else:
            budget = forms.parse_budget(submitted, app.currency, target_id)
            if action == "create":
                app.add_budget(budget)
            else:
                app.update_budget(budget)
    except forms.FormError as exc:
        form = target_form_from_submitted(kind, submitted, target_id)
        operation = _submitted_source(app, submitted) if is_planned else None
        return _render_edit(
            request,
            app,
            form,
            _safe_return_to(submitted.get("return_to")),
            error=str(exc),
            seed=build_operation_seed(app, operation) if operation else None,
        )
    refresh_forecast(app)
    return RedirectResponse(
        url=_safe_return_to(submitted.get("return_to")), status_code=303
    )


def _link_source(
    app: ApplicationService, submitted: dict[str, str], created: PlannedOperation
) -> None:
    """Link the operation the form was seeded from to what it just created.

    The planned operation exists either way: a link that cannot be made is
    logged, not raised back at the user.
    """
    if (operation := _submitted_source(app, submitted)) is None:
        return
    try:
        linking.link_source_operation(app, operation.unique_id, created)
    except BudgetForecasterError:
        logger.warning(
            "Could not link operation %d to new planned operation %s",
            operation.unique_id,
            created.id,
        )


def _render_edit(
    request: Request,
    app: ApplicationService,
    form: TargetFormView,
    return_to: str,
    *,
    error: str = "",
    seed: OperationSeed | None = None,
) -> Response:
    categories = tuple((cat.name, cat.display_name) for cat in sorted_categories())
    decided = (
        app.get_iteration_resolutions(form.target_id)
        if form.is_planned and form.target_id is not None
        else ()
    )
    return render_template(
        request,
        "target_edit.html",
        # Seeded from an operation, the user is mid-flow out of Opérations.
        active="operations" if seed else "targets",
        form=form,
        categories=categories,
        return_to=return_to,
        error=error,
        currency=app.currency,
        decided=decided,
        seed=seed,
        status_code=422 if error else 200,
    )
