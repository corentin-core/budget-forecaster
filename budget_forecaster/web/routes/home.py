"""Accueil: the phone glance — balance, available margin, month health, upcoming."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import MarginInfo
from budget_forecaster.web.dependencies import get_app_service
from budget_forecaster.web.rendering import render_template
from budget_forecaster.web.viewmodels import build_month_health

router = APIRouter()

_PAGE_SIZE = 10
_HORIZON_DAYS = 90


def _margin_status(margin: MarginInfo | None) -> str | None:
    """Colour bucket for the available margin: bad below the threshold, warn
    when the buffer is thin, good otherwise."""
    if margin is None:
        return None
    if margin["available_margin"] < 0:
        return "bad"
    if margin["available_margin"] < margin["threshold"]:
        return "warn"
    return "good"


@router.get("/")
async def home(
    request: Request, app: ApplicationService = Depends(get_app_service)
) -> Response:
    """Render the home dashboard."""
    month_start = date.today().replace(day=1)
    upcoming = app.get_upcoming_planned_iterations(_HORIZON_DAYS)
    return render_template(
        request,
        "home.html",
        active="home",
        balance=app.balance,
        balance_date=app.balance_date,
        currency=app.currency,
        margin=(margin := app.get_available_margin(month_start)),
        margin_status=_margin_status(margin),
        health=build_month_health(app, month_start),
        uncategorized=len(app.get_uncategorized_operations()),
        upcoming=upcoming[:_PAGE_SIZE],
        upcoming_next=_PAGE_SIZE if len(upcoming) > _PAGE_SIZE else None,
    )


@router.get("/upcoming")
async def upcoming_page(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    offset: int = 0,
) -> Response:
    """Return the next page of upcoming iterations (HTMX 'show more')."""
    upcoming = app.get_upcoming_planned_iterations(_HORIZON_DAYS)
    page = upcoming[offset : offset + _PAGE_SIZE]
    next_offset = offset + _PAGE_SIZE
    return render_template(
        request,
        "fragments/upcoming_page.html",
        active="home",
        upcoming=page,
        currency=app.currency,
        upcoming_next=next_offset if next_offset < len(upcoming) else None,
    )
