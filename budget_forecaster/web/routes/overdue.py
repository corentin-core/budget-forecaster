"""Decisions on overdue iterations: postpone, stop counting, restore.

Each write returns the row it changed plus an out-of-band refresh of the margin
hero and the nav badge, so the number the user was looking at moves with their
decision without a full page reload.
"""

from datetime import date
from typing import NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from budget_forecaster.core.types import PlannedOperationId
from budget_forecaster.exceptions import PlannedOperationNotFoundError
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web import forms
from budget_forecaster.web.dependencies import get_app_service, refresh_forecast
from budget_forecaster.web.rendering import render_template
from budget_forecaster.web.viewmodels import (
    OverdueCard,
    OverdueRow,
    build_overdue_card,
    margin_status,
)

router = APIRouter()


def _parse_iteration_date(raw: str) -> date:
    """Read the iteration date out of the path, 404 on anything else."""
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=404) from exc


class _RowContext(NamedTuple):
    """What a row fragment needs to render one overdue iteration."""

    card: OverdueCard
    row: OverdueRow | None
    currency: str


def _row_context(
    app: ApplicationService, op_id: PlannedOperationId, iteration_date: date
) -> _RowContext:
    """Find the iteration in a freshly derived card, if it still needs anything."""
    card = build_overdue_card(app)
    row = next(
        (
            candidate
            for candidate in card.rows
            if candidate.planned_operation_id == op_id
            and candidate.iteration_date == iteration_date
        ),
        None,
    )
    return _RowContext(card, row, app.currency)


def _decided_response(
    request: Request,
    app: ApplicationService,
    op_id: PlannedOperationId,
    iteration_date: date,
    outcome: str,
    released: float | None = None,
) -> Response:
    """Render the settled row plus the out-of-band margin and badge refresh."""
    return render_template(
        request,
        "fragments/overdue_decided.html",
        active="home",
        op_id=op_id,
        iteration_date=iteration_date,
        outcome=outcome,
        released=released,
        margin=(margin := app.get_available_margin(date.today().replace(day=1))),
        margin_status=margin_status(margin),
        currency=app.currency,
        balance_date=app.balance_date,
    )


@router.get("/overdue/{op_id}/{iteration_date}/postpone")
async def postpone_form(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Return the in-place postponement form for one overdue iteration."""
    parsed = _parse_iteration_date(iteration_date)
    context = _row_context(app, op_id, parsed)
    if context.row is None:
        raise HTTPException(status_code=404)
    return render_template(
        request,
        "fragments/overdue_postpone.html",
        active="home",
        card=context.card,
        row=context.row,
        currency=context.currency,
    )


@router.get("/overdue/{op_id}/{iteration_date}/row")
async def row_fragment(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Return the row as it stands, used to cancel out of the postpone form."""
    parsed = _parse_iteration_date(iteration_date)
    context = _row_context(app, op_id, parsed)
    if context.row is None:
        raise HTTPException(status_code=404)
    return render_template(
        request,
        "fragments/overdue_row.html",
        active="home",
        card=context.card,
        row=context.row,
        currency=context.currency,
    )


@router.post("/overdue/{op_id}/{iteration_date}/postpone")
async def postpone(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Move an overdue iteration to the date the user picked."""
    parsed = _parse_iteration_date(iteration_date)
    submitted = forms.form_to_dict(await request.form())
    try:
        postponed_to = date.fromisoformat(submitted.get("postponed_to", "").strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid date") from exc

    try:
        app.postpone_iteration(op_id, parsed, postponed_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    refresh_forecast(app)
    return _decided_response(request, app, op_id, parsed, "postponed")


@router.post("/overdue/{op_id}/{iteration_date}/skip")
async def skip(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Stop counting an overdue iteration that never happened."""
    parsed = _parse_iteration_date(iteration_date)
    try:
        target = app.get_planned_operation_by_id(op_id)
    except PlannedOperationNotFoundError as exc:
        raise HTTPException(status_code=404) from exc
    app.skip_iteration(op_id, parsed)
    refresh_forecast(app)
    return _decided_response(
        request, app, op_id, parsed, "skipped", released=abs(target.amount)
    )


@router.post("/overdue/{op_id}/{iteration_date}/restore")
async def restore(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Undo a decision, putting the iteration back where it was."""
    parsed = _parse_iteration_date(iteration_date)
    app.restore_iteration(op_id, parsed)
    refresh_forecast(app)
    context = _row_context(app, op_id, parsed)
    if context.row is None:
        # Nothing to put back: a link settled the iteration meanwhile.
        return render_template(
            request,
            "fragments/overdue_gone.html",
            active="home",
            margin=(margin := app.get_available_margin(date.today().replace(day=1))),
            margin_status=margin_status(margin),
            currency=context.currency,
        )
    return render_template(
        request,
        "fragments/overdue_row.html",
        active="home",
        card=context.card,
        row=context.row,
        currency=context.currency,
    )
