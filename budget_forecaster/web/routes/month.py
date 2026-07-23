"""Mois: per-category planned vs actual for one month, switchable via the URL."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response

from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web.dependencies import get_app_service
from budget_forecaster.web.rendering import render_template
from budget_forecaster.web.viewmodels import build_month_view

router = APIRouter()


def _parse_month(value: str) -> date | None:
    try:
        year, month = value.split("-")
        return date(int(year), int(month), 1)
    except (ValueError, TypeError):
        return None


@router.get("/mois")
def current_month() -> Response:
    """Redirect to the current month."""
    today = date.today()
    return RedirectResponse(url=f"/mois/{today:%Y-%m}", status_code=307)


@router.get("/mois/{month}")
async def month_view(
    month: str,
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Render the month review for a yyyy-mm path segment."""
    if (parsed := _parse_month(month)) is None:
        return RedirectResponse(url="/mois", status_code=307)
    return render_template(
        request,
        "month.html",
        active="month",
        view=build_month_view(app, parsed),
        currency=app.currency,
    )
