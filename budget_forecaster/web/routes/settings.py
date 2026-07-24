"""Réglages: bank connection status, imports inbox, margin threshold (read-only)."""

from typing import NamedTuple

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response

from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    ConsentStatus,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web.dependencies import (
    get_app_service,
    get_consent_service,
    refresh_forecast,
)
from budget_forecaster.web.rendering import render_template

router = APIRouter()


class ConnectionStatus(NamedTuple):
    """The bank connection state shown in Réglages."""

    configured: bool
    status: ConsentStatus | None
    valid_until: object | None


def _connection_status(consent_service: ConsentService | None) -> ConnectionStatus:
    if consent_service is None:
        return ConnectionStatus(False, None, None)
    state = consent_service.state()
    valid_until = state.valid_until.date() if state.valid_until else None
    return ConnectionStatus(True, state.status, valid_until)


@router.get("/settings")
async def settings(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    consent_service: ConsentService | None = Depends(get_consent_service),
) -> Response:
    """Render the operational settings page."""
    return render_template(
        request,
        "settings.html",
        active="settings",
        connection=_connection_status(consent_service),
        inbox_path=app.inbox_path,
        pending=tuple(app.get_supported_exports_in_inbox()),
        margin_threshold=app.margin_threshold,
        currency=app.currency,
    )


@router.post("/settings/threshold")
async def set_threshold(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Update the safety margin threshold that colours the available margin."""
    form = await request.form()
    raw = str(form.get("threshold", "")).replace(",", ".").strip()
    try:
        app.margin_threshold = float(raw)
    except ValueError:
        return RedirectResponse(url="/settings", status_code=303)
    refresh_forecast(app)
    return RedirectResponse(url="/settings", status_code=303)
