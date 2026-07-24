"""Réglages: bank connection status, imports inbox, margin threshold (read-only)."""

from datetime import date, datetime
from typing import NamedTuple

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response

from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    ConsentStatus,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.sync_runner import (
    perform_sync,
)
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web.dependencies import (
    get_app_service,
    get_config,
    get_consent_service,
    get_repository,
    refresh_forecast,
)
from budget_forecaster.web.rendering import render_template

router = APIRouter()

_SYNC_HISTORY_LIMIT = 10


class ConnectionStatus(NamedTuple):
    """The bank connection state shown in Réglages."""

    configured: bool
    status: ConsentStatus | None
    valid_until: date | None


def _connection_status(consent_service: ConsentService | None) -> ConnectionStatus:
    if consent_service is None:
        return ConnectionStatus(False, None, None)
    state = consent_service.state()
    valid_until = state.valid_until.date() if state.valid_until else None
    return ConnectionStatus(True, state.status, valid_until)


def _consent_created_at(consent_service: ConsentService | None) -> datetime | None:
    """When the current consent was granted, for flagging pre-renewal failures."""
    if (
        consent_service is None
        or (consent := consent_service.current_consent()) is None
    ):
        return None
    return consent.created_at


@router.get("/settings")
async def settings(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    consent_service: ConsentService | None = Depends(get_consent_service),
    repository: RepositoryInterface = Depends(get_repository),
) -> Response:
    """Render the operational settings page."""
    connection = _connection_status(consent_service)
    return render_template(
        request,
        "settings.html",
        active="settings",
        connection=connection,
        sync_runs=repository.get_recent_sync_runs(_SYNC_HISTORY_LIMIT),
        consent_created_at=_consent_created_at(consent_service),
        inbox_path=app.inbox_path,
        pending=tuple(app.get_supported_exports_in_inbox()),
        margin_threshold=app.margin_threshold,
        currency=app.currency,
    )


@router.post("/settings/sync")
async def sync_now(
    app: ApplicationService = Depends(get_app_service),
    consent_service: ConsentService | None = Depends(get_consent_service),
    repository: RepositoryInterface = Depends(get_repository),
    config: Config = Depends(get_config),
) -> Response:
    """Run a bank sync now, then refresh the cached account and forecast.

    The sync does blocking network I/O on the event-loop thread (the shared SQLite
    connection is bound to it, so it can't be offloaded). A slow bank API stalls
    other requests for its duration — acceptable at personal scale, manual and rare.
    """
    if consent_service is not None and config.enable_banking is not None:
        perform_sync(
            repository, consent_service, config.enable_banking, config.accounts
        )
        app.reload_account()
        refresh_forecast(app)
    return RedirectResponse(url="/settings", status_code=303)


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
