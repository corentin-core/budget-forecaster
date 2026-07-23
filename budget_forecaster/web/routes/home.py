"""Accueil: the phone glance — balance, available margin, month health, upcoming."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web.dependencies import get_app_service
from budget_forecaster.web.rendering import render_template
from budget_forecaster.web.viewmodels import build_month_health

router = APIRouter()


@router.get("/")
async def home(
    request: Request, app: ApplicationService = Depends(get_app_service)
) -> Response:
    """Render the home dashboard."""
    month_start = date.today().replace(day=1)
    return render_template(
        request,
        "home.html",
        active="home",
        balance=app.balance,
        currency=app.currency,
        margin=app.get_available_margin(month_start),
        health=build_month_health(app, month_start),
        upcoming=app.get_upcoming_planned_iterations(),
        uncategorized=len(app.get_uncategorized_operations()),
    )
