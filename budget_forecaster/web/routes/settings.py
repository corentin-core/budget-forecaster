"""Réglages: bank connection status, imports inbox, margin threshold (read-only)."""

import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import NamedTuple

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse, Response

from budget_forecaster.core.types import SyncRun, SyncRunStatus, SyncSource
from budget_forecaster.i18n import _
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    ConsentStatus,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import SwileClient
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)
from budget_forecaster.infrastructure.bank_sources.sync_all import sync_all_sources
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.import_service import ImportResult
from budget_forecaster.web.dependencies import (
    get_app_service,
    get_config,
    get_consent_service,
    get_repository,
    get_swile_client,
    get_swile_token_store,
    refresh_forecast,
)
from budget_forecaster.web.enrollment import clear_flash, read_flash
from budget_forecaster.web.rendering import render_template

router = APIRouter()

_SYNC_HISTORY_LIMIT = 10


class ConnectionStatus(NamedTuple):
    """The bank connection state shown in Réglages."""

    configured: bool
    has_consent: bool
    status: ConsentStatus | None
    valid_until: date | None


def _connection_status(consent_service: ConsentService | None) -> ConnectionStatus:
    if consent_service is None:
        return ConnectionStatus(False, False, None, None)
    state = consent_service.state()
    valid_until = state.valid_until.date() if state.valid_until else None
    has_consent = consent_service.current_consent() is not None
    return ConnectionStatus(True, has_consent, state.status, valid_until)


def _consent_created_at(consent_service: ConsentService | None) -> datetime | None:
    """When the current consent was granted, for flagging pre-renewal failures."""
    if (
        consent_service is None
        or (consent := consent_service.current_consent()) is None
    ):
        return None
    return consent.created_at


def _latest_run(repository: RepositoryInterface, source: SyncSource) -> SyncRun | None:
    """Most recent run for one source, for the Sync card summary line."""
    recent = repository.get_recent_sync_runs(1, source=source)
    return recent[0] if recent else None


@router.get("/settings")
async def settings(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    consent_service: ConsentService | None = Depends(get_consent_service),
    repository: RepositoryInterface = Depends(get_repository),
    swile_token_store: SwileTokenStore = Depends(get_swile_token_store),
) -> Response:
    """Render the operational settings page.

    Any enrollment outcome left in the flash cookie is shown once, then cleared.
    """
    connection = _connection_status(consent_service)
    flash = read_flash(request, request.app.state.flash_serializer)
    last_bank = _latest_run(repository, SyncSource.ENABLE_BANKING)
    last_swile = _latest_run(repository, SyncSource.SWILE)
    response = render_template(
        request,
        "settings.html",
        active="settings",
        connection=connection,
        flash=flash,
        sync_runs=repository.get_recent_sync_runs(_SYNC_HISTORY_LIMIT),
        last_bank=last_bank,
        last_swile=last_swile,
        last_sync_at=max(
            (run.ran_at for run in (last_bank, last_swile) if run), default=None
        ),
        consent_created_at=_consent_created_at(consent_service),
        swile_enrolled=swile_token_store.load() is not None,
        inbox_path=app.inbox_path,
        pending=tuple(app.get_supported_exports_in_inbox()),
        margin_threshold=app.margin_threshold,
        currency=app.currency,
    )
    if flash is not None:
        clear_flash(response)
    return response


@router.post("/settings/sync")
async def sync_now(
    app: ApplicationService = Depends(get_app_service),
    consent_service: ConsentService | None = Depends(get_consent_service),
    repository: RepositoryInterface = Depends(get_repository),
    config: Config = Depends(get_config),
    swile_token_store: SwileTokenStore = Depends(get_swile_token_store),
    swile_client: SwileClient = Depends(get_swile_client),
) -> Response:
    """Sync every connected source, then refresh the cached account and forecast once.

    The sync does blocking network I/O on the event-loop thread (the shared SQLite
    connection is bound to it, so it can't be offloaded). A slow source stalls other
    requests for its duration — acceptable at personal scale, manual and rare. Reload
    only when at least one source succeeded, so reload_account tolerates an empty DB.
    """
    runs = sync_all_sources(
        repository, config, consent_service, swile_token_store, swile_client
    )
    if any(run.status is SyncRunStatus.OK for run in runs):
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


def _import_result_fragment(
    request: Request,
    app: ApplicationService,
    *,
    result: ImportResult | None = None,
    error: str | None = None,
) -> Response:
    """Render the inline import-result fragment swapped into the Imports card."""
    return render_template(
        request,
        "fragments/import_result.html",
        active="settings",
        result=result,
        error=error,
        currency=app.currency,
    )


@router.post("/settings/import")
async def import_file(
    request: Request,
    file: UploadFile | None = File(None),
    app: ApplicationService = Depends(get_app_service),
) -> Response:
    """Import an uploaded bank export through the shared import service.

    The adapter factory dispatches on the file name (BNP on the .xls suffix,
    Swile on the swile-export-YYYY-MM-DD.zip pattern), so the upload keeps its
    original basename in a throwaway temp dir. Runs on the event-loop thread
    like the manual sync: the shared SQLite connection is bound to it.
    """
    if file is None or not (name := Path(file.filename or "").name):
        return _import_result_fragment(request, app, error=_("No file selected."))

    tmp_dir = Path(tempfile.mkdtemp(prefix="budget-import-"))
    tmp_path = tmp_dir / name
    try:
        tmp_path.write_bytes(await file.read())

        if not app.is_supported_export(tmp_path):
            return _import_result_fragment(
                request, app, error=_("Unsupported file: {}").format(name)
            )

        result = app.import_file(tmp_path)
        if result.success:
            app.reload_account()
            refresh_forecast(app)
        return _import_result_fragment(request, app, result=result)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
