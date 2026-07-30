"""What to do with an overdue iteration: link it, postpone it, stop counting it.

Linking is the primary answer, since the usual reason a payment shows up here is
that it happened and the matcher missed it. The two decisions answer the rest.

Each HTMX write answers with the row it changed plus an out-of-band refresh of
the margin hero, the card head and the nav badge, so every number the user can
see moves with their decision without a full page reload. Submitted from the
picker page, which has none of those, they redirect instead.
"""

from datetime import date
from typing import Any, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from starlette.datastructures import FormData

from budget_forecaster.core.types import PlannedOperationId
from budget_forecaster.exceptions import BudgetForecasterError
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web import forms, linking
from budget_forecaster.web.alerts import sync_is_broken
from budget_forecaster.web.dependencies import get_app_service, refresh_forecast
from budget_forecaster.web.redirects import safe_local_path
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


def _find_row(
    request: Request,
    app: ApplicationService,
    op_id: PlannedOperationId,
    iteration_date: date,
) -> _Target:
    """Locate an iteration that still awaits an answer, 404 otherwise.

    A stale row must not act on an iteration the derivation no longer produces.
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
    return _Target(card, row)


def _find_target(
    request: Request,
    app: ApplicationService,
    op_id: PlannedOperationId,
    iteration_date: date,
) -> _Target:
    """Locate an iteration a decision may be recorded about.

    409 when a sync failed, which is also why the card withholds its buttons —
    hiding them in the template is not the barrier. The picker is not gated: an
    operation that is there can be linked whatever a failed sync left out.
    """
    target = _find_row(request, app, op_id, iteration_date)
    if target.card.sync_broken:
        raise HTTPException(status_code=409, detail="sync failed")
    return target


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


def _safe_back(value: str) -> str:
    """Only allow same-app relative paths as a back link."""
    return safe_local_path(value, "/")


class PickerQuery(NamedTuple):
    """What the picker's URL asks of the candidate list."""

    query: str = ""
    show_all: bool = False
    return_to: str = "/"


def get_picker_query(
    q: str = "",
    show_all: bool = Query(default=False, alias="all"),
    return_to: str = "/",
) -> PickerQuery:
    """Read the candidate list's query parameters, as the ledger does its filters."""
    return PickerQuery(q.strip(), show_all, return_to)


def _picker_context(
    request: Request,
    app: ApplicationService,
    op_id: PlannedOperationId,
    iteration_date: date,
    asked: PickerQuery,
) -> dict[str, Any]:
    """Everything the picker page and its list fragment render."""
    target = _find_row(request, app, op_id, iteration_date)
    planned = app.get_planned_operation_by_id(op_id)
    candidates = linking.build_operation_candidates(
        app, planned, iteration_date, asked.query
    )
    shown, hidden = linking.filter_operation_candidates(
        candidates, asked.query, asked.show_all
    )
    return {
        "card": target.card,
        "row": target.row,
        "candidates": shown,
        "hidden_count": hidden,
        "query": asked.query,
        "balance_date": app.balance_date,
        "currency": app.currency,
        "return_to": _safe_back(asked.return_to),
    }


@router.get("/overdue/{op_id}/{iteration_date}/link")
async def link_page(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    return_to: str = "/",
) -> Response:
    """Render the picker: the operations that could have paid this iteration."""
    parsed = _parse_iteration_date(iteration_date)
    return render_template(
        request,
        "overdue_link.html",
        active="home",
        **_picker_context(
            request, app, op_id, parsed, PickerQuery(return_to=return_to)
        ),
    )


@router.get("/overdue/{op_id}/{iteration_date}/link/candidates")
async def link_candidates(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    asked: PickerQuery = Depends(get_picker_query),
) -> Response:
    """Return the candidate list fragment (search / show-all)."""
    parsed = _parse_iteration_date(iteration_date)
    return render_template(
        request,
        "fragments/operation_candidate_list.html",
        active="home",
        **_picker_context(request, app, op_id, parsed, asked),
    )


@router.post("/overdue/{op_id}/{iteration_date}/link")
async def create_link(
    op_id: int,
    iteration_date: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Count an operation for this iteration, replacing any link it carried."""
    parsed = _parse_iteration_date(iteration_date)
    _find_row(request, app, op_id, parsed)
    planned = app.get_planned_operation_by_id(op_id)
    submitted = forms.form_to_dict(await request.form())
    try:
        operation = app.get_operation_by_id(int(submitted.get("operation_id", "")))
    except (ValueError, BudgetForecasterError) as exc:
        raise HTTPException(status_code=404) from exc
    if (float(operation.amount) < 0) != (float(planned.amount) < 0):
        raise HTTPException(status_code=400, detail="opposite sign")

    app.create_manual_link(operation, planned, parsed)
    refresh_forecast(app)
    return RedirectResponse(
        url=_safe_back(submitted.get("return_to", "/")), status_code=303
    )


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
    """Return the row as it stands, used to cancel out of the postpone form.

    Open: the user was deciding a second ago, and cancelling one date should not
    cost them the tap that got the issues on screen.
    """
    target = _find_target(request, app, op_id, _parse_iteration_date(iteration_date))
    return render_template(
        request,
        "fragments/overdue_row.html",
        active="home",
        card=target.card,
        row=target.row,
        currency=app.currency,
        row_open=True,
    )


def _decided_response(
    request: Request,
    app: ApplicationService,
    row: OverdueRow,
    *,
    released: float | None = None,
    postponed_to: date | None = None,
    back: str | None = None,
) -> Response:
    """Render the settled row with its undo, plus the out-of-band figures.

    The picker page carries neither the row nor the out-of-band targets, so a
    decision taken from there redirects rather than swapping nothing.
    """
    if back is not None:
        return RedirectResponse(url=back, status_code=303)
    return render_template(
        request,
        "fragments/overdue_decided.html",
        active="home",
        row=row,
        released=released,
        postponed_to=postponed_to,
        **_oob_context(app),
    )


def _chosen_date(form: FormData) -> str:
    """The postponement date the user picked, or empty.

    The chips and the free date field share a name, so clicking a chip also
    submits an empty text field; flattening the form to a dict would keep that
    empty one and reject the request.
    """
    return next(
        (
            raw.strip()
            for raw in form.getlist("postponed_to")
            if isinstance(raw, str) and raw.strip()
        ),
        "",
    )


def _redirect_back(submitted: dict[str, str]) -> str | None:
    """Where a submit that states a back target goes, or None to swap in place.

    The picker page states one; the card's own forms swap the row instead.
    """
    if back := submitted.get("return_to", "").strip():
        return _safe_back(back)
    return None


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
    form = await request.form()
    submitted = forms.form_to_dict(form)
    try:
        postponed_to = date.fromisoformat(_chosen_date(form))
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
    return _decided_response(
        request,
        app,
        target.row,
        postponed_to=postponed_to,
        back=_redirect_back(submitted),
    )


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
    submitted = forms.form_to_dict(await request.form())
    app.skip_iteration(op_id, parsed)
    refresh_forecast(app)
    return _decided_response(
        request,
        app,
        target.row,
        released=abs(target.row.amount),
        back=_redirect_back(submitted),
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
        # Nothing to put back: a link settled the iteration meanwhile, or it aged
        # past the listing window while the decision held it out of the card.
        return render_template(
            request, "fragments/overdue_gone.html", active="home", **context
        )
    # Open: undoing a decision means another one is coming.
    return render_template(
        request,
        "fragments/overdue_row.html",
        active="home",
        row=row,
        oob_refresh=True,
        row_open=True,
        **context,
    )
