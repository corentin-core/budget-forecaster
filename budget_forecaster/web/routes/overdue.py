"""Decisions on overdue iterations: postpone, stop counting, restore.

Each write answers with the row it changed plus an out-of-band refresh of the
margin hero, the card head and the nav badge, so every number the user can see
moves with their decision without a full page reload.
"""

from datetime import date
from typing import Any, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from budget_forecaster.core.types import PlannedOperationId
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web import forms
from budget_forecaster.web.alerts import sync_is_broken
from budget_forecaster.web.dependencies import get_app_service, refresh_forecast
from budget_forecaster.web.rendering import render_template
from budget_forecaster.web.viewmodels import (
    OverdueCard,
    OverdueRow,
    build_overdue_card,
    margin_status,
)

router = APIRouter()

_FROM_DECIDED_LIST = "decided-"


class _Target(NamedTuple):
    """The iteration a request acts on, once found in the card."""

    card: OverdueCard
    row: OverdueRow


def _parse_iteration_date(raw: str) -> date:
    """Read the iteration date out of the path, 404 on anything else."""
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=404) from exc
    if parsed.isoformat() != raw:
        # fromisoformat also accepts week dates; keep one URL per iteration.
        raise HTTPException(status_code=404)
    return parsed


def _sync_broken(request: Request) -> bool:
    """Whether the imported data is known to be incomplete."""
    return sync_is_broken(
        request.app.state.repository, request.app.state.consent_service
    )


def _find_target(
    request: Request,
    app: ApplicationService,
    op_id: PlannedOperationId,
    iteration_date: date,
) -> _Target:
    """Locate an iteration that still awaits a decision, refusing otherwise.

    404 when it is not derived as overdue: a stale row must not record a
    decision about an iteration that does not exist. 409 when a sync failed,
    which is also why the card withholds its buttons — hiding them in the
    template is not the barrier.
    """
    card = build_overdue_card(app, sync_broken=_sync_broken(request))
    row = next(
        (
            candidate
            for candidate in card.rows
            if candidate.planned_operation_id == op_id
            and candidate.iteration_date == iteration_date
        ),
        None,
    )
    if row is None:
        raise HTTPException(status_code=404)
    if card.sync_broken:
        raise HTTPException(status_code=409, detail="sync failed")
    return _Target(card, row)


def _oob_context(app: ApplicationService) -> dict[str, Any]:
    """The figures the out-of-band fragments refresh: margin, count, badge."""
    margin = app.get_available_margin(date.today().replace(day=1))
    card = build_overdue_card(app)
    return {
        "margin": margin,
        "margin_status": margin_status(margin),
        "card": card,
        "overdue_count": len(card.rows),
        "currency": app.currency,
    }


@router.get("/overdue/{op_id}/{iteration_date}/postpone")
async def postpone_form(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Return the in-place postponement form for one overdue iteration."""
    target = _find_target(request, app, op_id, _parse_iteration_date(iteration_date))
    return render_template(
        request,
        "fragments/overdue_postpone.html",
        active="home",
        card=target.card,
        row=target.row,
        currency=app.currency,
    )


@router.get("/overdue/{op_id}/{iteration_date}/row")
async def row_fragment(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Return the row as it stands, used to cancel out of the postpone form."""
    target = _find_target(request, app, op_id, _parse_iteration_date(iteration_date))
    return render_template(
        request,
        "fragments/overdue_row.html",
        active="home",
        card=target.card,
        row=target.row,
        currency=app.currency,
    )


def _decided_response(
    request: Request,
    app: ApplicationService,
    row: OverdueRow,
    *,
    released: float | None = None,
    postponed_to: date | None = None,
) -> Response:
    """Render the settled row with its undo, plus the out-of-band figures."""
    return render_template(
        request,
        "fragments/overdue_decided.html",
        active="home",
        row=row,
        released=released,
        postponed_to=postponed_to,
        **_oob_context(app),
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
    target = _find_target(request, app, op_id, parsed)
    submitted = forms.form_to_dict(await request.form())
    try:
        postponed_to = date.fromisoformat(submitted.get("postponed_to", "").strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid date") from exc
    if postponed_to <= date.today():
        # A date already gone leaves the iteration late on the spot.
        raise HTTPException(status_code=400, detail="date must be in the future")

    try:
        app.postpone_iteration(op_id, parsed, postponed_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    refresh_forecast(app)
    return _decided_response(request, app, target.row, postponed_to=postponed_to)


@router.post("/overdue/{op_id}/{iteration_date}/skip")
async def skip(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Stop counting an overdue iteration that never happened."""
    parsed = _parse_iteration_date(iteration_date)
    target = _find_target(request, app, op_id, parsed)
    app.skip_iteration(op_id, parsed)
    refresh_forecast(app)
    return _decided_response(request, app, target.row, released=abs(target.row.amount))


@router.post("/overdue/{op_id}/{iteration_date}/restore")
async def restore(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Undo a decision, putting the iteration back where it was."""
    parsed = _parse_iteration_date(iteration_date)
    stored = app.get_iteration_resolutions(op_id)
    if not any(item.iteration_date == parsed for item in stored):
        raise HTTPException(status_code=404)
    app.restore_iteration(op_id, parsed)
    refresh_forecast(app)

    # The decided list lives on the planned operation's page, where neither the
    # card's markup nor its out-of-band targets exist.
    if (request.headers.get("HX-Target") or "").startswith(_FROM_DECIDED_LIST):
        return render_template(request, "fragments/empty.html", active="targets")

    context = _oob_context(app)
    card = context["card"]
    row = next(
        (
            candidate
            for candidate in card.rows
            if candidate.planned_operation_id == op_id
            and candidate.iteration_date == parsed
        ),
        None,
    )
    if row is None:
        # Nothing to put back: a link settled the iteration meanwhile.
        return render_template(
            request, "fragments/overdue_gone.html", active="home", **context
        )
    return render_template(
        request,
        "fragments/overdue_row.html",
        active="home",
        row=row,
        oob_refresh=True,
        **context,
    )
