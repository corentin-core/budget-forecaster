"""Swile OAuth2 enrollment and sync.

Enrollment is copy-paste: a bookmarklet on team.swile.co copies the refresh
token, the user pastes it into the form here (same-origin, session-authed), so
no cross-origin POST or CORS is involved. Enrolling runs one sync right away so
the user sees data immediately.
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response

from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import SwileClient
from budget_forecaster.infrastructure.bank_sources.swile_oauth.consent_service import (
    SwileConsentService,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.sync_runner import (
    perform_sync,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.web.dependencies import (
    get_app_service,
    get_config,
    get_repository,
    get_swile_client,
    get_swile_token_store,
    refresh_forecast,
)
from budget_forecaster.web.enrollment import Flash, set_flash

logger = logging.getLogger("budget_forecaster")

router = APIRouter()


def _flash_redirect(request: Request, flash: Flash) -> Response:
    """Redirect to Réglages carrying a one-shot flash outcome."""
    response = RedirectResponse(url="/settings", status_code=303)
    set_flash(
        response,
        request.app.state.flash_serializer,
        flash,
        secure=request.app.state.web_secrets.secure_cookies,
    )
    return response


def _sync_and_refresh(
    repository: RepositoryInterface,
    token_store: SwileTokenStore,
    client: SwileClient,
    config: Config,
    app: ApplicationService,
) -> None:
    """Sync Swile, then refresh the cached account and forecast."""
    perform_sync(repository, token_store, config.accounts, client=client)
    app.reload_account()
    refresh_forecast(app)


@router.post("/settings/swile/enroll")
async def enroll(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    token_store: SwileTokenStore = Depends(get_swile_token_store),
    client: SwileClient = Depends(get_swile_client),
    repository: RepositoryInterface = Depends(get_repository),
    config: Config = Depends(get_config),
) -> Response:
    """Store the pasted refresh token, then sync once.

    A blank field or a token the refresh endpoint rejects flashes an error and
    stores nothing.
    """
    form = await request.form()
    if not (refresh_token := str(form.get("refresh_token", "")).strip()):
        return _flash_redirect(request, Flash.SWILE_ERROR)

    consent_service = SwileConsentService(client, token_store)
    try:
        consent_service.enroll(refresh_token)
    except Exception:  # pylint: disable=broad-except
        logger.exception("Swile enrollment failed")
        return _flash_redirect(request, Flash.SWILE_ERROR)

    _sync_and_refresh(repository, token_store, client, config, app)
    return _flash_redirect(request, Flash.SWILE_LINKED)


@router.post("/settings/swile/sync")
async def sync_now(
    app: ApplicationService = Depends(get_app_service),
    token_store: SwileTokenStore = Depends(get_swile_token_store),
    client: SwileClient = Depends(get_swile_client),
    repository: RepositoryInterface = Depends(get_repository),
    config: Config = Depends(get_config),
) -> Response:
    """Run a Swile sync now, then refresh the cached account and forecast.

    Like the bank sync, this does blocking network I/O on the event-loop thread;
    acceptable at personal scale (manual, rare).
    """
    _sync_and_refresh(repository, token_store, client, config, app)
    return RedirectResponse(url="/settings", status_code=303)
