"""Réglages: bank connection status, imports inbox, margin threshold (read-only)."""

import logging
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import NamedTuple

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response

from budget_forecaster.core.types import SyncRun, SyncRunStatus, SyncSource
from budget_forecaster.exceptions import (
    BackupError,
    BudgetForecasterError,
    DatabaseBusyError,
)
from budget_forecaster.i18n import _
from budget_forecaster.infrastructure.backup import BackupKind, BackupService
from budget_forecaster.infrastructure.backup_preview import (
    BackupPreview,
    preview_backup,
)
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
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.import_service import ImportResult
from budget_forecaster.web.backup_flash import (
    BackupFlash,
    clear_backup_flash,
    read_backup_flash,
    set_backup_flash,
)
from budget_forecaster.web.dependencies import (
    get_app_service,
    get_backup_service,
    get_config,
    get_consent_service,
    get_repository,
    get_swile_client,
    get_swile_token_store,
    refresh_forecast,
)
from budget_forecaster.web.enrollment import clear_flash, read_flash
from budget_forecaster.web.formatting import format_signed_eur
from budget_forecaster.web.rendering import render_template

logger = logging.getLogger("budget_forecaster")

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
    backup_service: BackupService = Depends(get_backup_service),
) -> Response:
    """Render the operational settings page.

    Any enrollment or backup outcome left in a flash cookie is shown once, then
    cleared.
    """
    connection = _connection_status(consent_service)
    flash = read_flash(request, request.app.state.flash_serializer)
    backup_flash = read_backup_flash(request, request.app.state.flash_serializer)
    last_bank = _latest_run(repository, SyncSource.ENABLE_BANKING)
    last_swile = _latest_run(repository, SyncSource.SWILE)
    response = render_template(
        request,
        "settings.html",
        active="settings",
        connection=connection,
        flash=flash,
        backup_flash=backup_flash,
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
        backups=backup_service.get_backups(),
    )
    if flash is not None:
        clear_flash(response)
    if backup_flash is not None:
        clear_backup_flash(response)
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


# --- Backups ---------------------------------------------------------------


class PreviewView(NamedTuple):
    """The preview fragment's view model: metrics of both DBs plus deltas."""

    name: str
    preview: BackupPreview
    delta_operations: int
    delta_balance: float
    delta_days: int | None
    summary: str
    older_schema: bool


def _migrate_scratch(scratch: Path) -> None:
    """Upgrade a restored scratch database to the current schema before the swap."""
    repository = SqliteRepository(scratch)
    try:
        repository.initialize()
    finally:
        repository.close()


def _reload_after_restore(app: ApplicationService) -> None:
    """Reopen the account and forecast after the database file was swapped."""
    try:
        app.reload_account()
    except BudgetForecasterError:
        logger.warning("Restore reload skipped: no account data")
    refresh_forecast(app)


def _preview_view(name: str, preview: BackupPreview) -> PreviewView:
    """Build the preview view model with a plain-language delta summary."""
    delta_ops = preview.backup.operation_count - preview.current.operation_count
    delta_balance = (
        preview.backup.total_balance.value - preview.current.total_balance.value
    )
    current_date = preview.current.latest_operation_date
    backup_date = preview.backup.latest_operation_date
    delta_days = (
        (backup_date - current_date).days
        if current_date is not None and backup_date is not None
        else None
    )
    summary = _("Compared to now: {ops:+d} operations, balance {balance}.").format(
        ops=delta_ops, balance=format_signed_eur(delta_balance)
    )
    return PreviewView(
        name=name,
        preview=preview,
        delta_operations=delta_ops,
        delta_balance=delta_balance,
        delta_days=delta_days,
        summary=summary,
        older_schema=preview.backup.schema_version < preview.current.schema_version,
    )


def _backup_redirect(
    request: Request, flash: BackupFlash | None = None
) -> RedirectResponse:
    """Redirect back to settings, optionally carrying a one-shot backup outcome."""
    response = RedirectResponse(url="/settings", status_code=303)
    if flash is not None:
        set_backup_flash(
            response,
            request.app.state.flash_serializer,
            flash,
            secure=request.app.state.web_secrets.secure_cookies,
        )
    return response


@router.post("/settings/backup")
async def create_backup(
    request: Request,
    backup_service: BackupService = Depends(get_backup_service),
) -> Response:
    """Create a backup on demand, then rotate old ones."""
    try:
        backup_service.create_backup(BackupKind.MANUAL)
        backup_service.rotate_backups()
    except BackupError:
        logger.exception("On-demand backup failed")
        return _backup_redirect(
            request, BackupFlash("error", _("Could not create the backup."))
        )
    return _backup_redirect(request)


@router.get("/settings/backup/preview")
async def preview_backup_route(
    request: Request,
    name: str,
    backup_service: BackupService = Depends(get_backup_service),
    config: Config = Depends(get_config),
) -> Response:
    """Render the read-only preview and restore-confirmation fragment."""
    try:
        source = backup_service.resolve_backup(name)
        preview = preview_backup(config.database_path, source)
    except BackupError:
        return render_template(
            request,
            "fragments/backup_preview.html",
            active="settings",
            error=_("This backup could not be read."),
            view=None,
        )
    return render_template(
        request,
        "fragments/backup_preview.html",
        active="settings",
        error=None,
        view=_preview_view(name, preview),
    )


@router.post("/settings/backup/restore")
async def restore_backup(
    request: Request,
    app: ApplicationService = Depends(get_app_service),
    repository: RepositoryInterface = Depends(get_repository),
    backup_service: BackupService = Depends(get_backup_service),
) -> Response:
    """Restore a backup, snapshotting current data first, then reload the app.

    Closes the shared connection before the swap so the reopen reads the
    restored file. Uses a non-blocking lock: if the daily sync holds it, fail
    fast with a retry message rather than hanging the request.
    """
    form = await request.form()
    name = str(form.get("name", ""))
    is_undo = bool(form.get("undo"))
    repository.close()
    try:
        snapshot = backup_service.restore_backup(
            name, _migrate_scratch, blocking=False, take_snapshot=not is_undo
        )
    except DatabaseBusyError:
        _reload_after_restore(app)
        return _backup_redirect(
            request,
            BackupFlash("error", _("A sync is running. Try again in a moment.")),
        )
    except BackupError:
        logger.exception("Restore failed")
        _reload_after_restore(app)
        return _backup_redirect(
            request, BackupFlash("error", _("Restore failed. Your data is unchanged."))
        )
    _reload_after_restore(app)
    if is_undo:
        # Undo is terminal: drop the snapshot it consumed so restores don't pile
        # up copies, and offer no further undo.
        backup_service.delete_backup(name)
        return _backup_redirect(request, BackupFlash("undone", ""))
    assert snapshot is not None
    return _backup_redirect(request, BackupFlash("restored", snapshot.name))


@router.post("/settings/backup/delete")
async def delete_backup(
    request: Request,
    backup_service: BackupService = Depends(get_backup_service),
) -> Response:
    """Delete a single backup by name."""
    form = await request.form()
    name = str(form.get("name", ""))
    try:
        backup_service.delete_backup(name)
    except BackupError:
        return _backup_redirect(
            request, BackupFlash("error", _("Could not delete the backup."))
        )
    return _backup_redirect(request)


@router.get("/settings/backup/download")
async def download_backup(
    request: Request,
    name: str,
    backup_service: BackupService = Depends(get_backup_service),
) -> Response:
    """Stream a backup file as an attachment, or redirect if the name is invalid."""
    try:
        source = backup_service.resolve_backup(name)
    except BackupError:
        return _backup_redirect(request, BackupFlash("error", _("Unknown backup.")))
    return FileResponse(source, filename=name, media_type="application/octet-stream")
