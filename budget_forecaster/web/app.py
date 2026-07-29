"""FastAPI application factory.

Builds ApplicationService from config, stores it (and the consent service) as
singletons on app.state, and computes the forecast once at startup so the month
and trends views read a populated report.

Run with: uvicorn --factory budget_forecaster.web.app:create_app
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from budget_forecaster.core.types import SyncRunStatus
from budget_forecaster.exceptions import (
    BudgetForecasterError,
    BudgetNotFoundError,
    OperationNotFoundError,
    PlannedOperationNotFoundError,
)
from budget_forecaster.i18n import _, setup_i18n
from budget_forecaster.infrastructure.backup import BackupService
from budget_forecaster.infrastructure.bank_sources.enable_banking.client import (
    EnableBankingClient,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_store import (
    ConsentStore,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import SwileClient
from budget_forecaster.infrastructure.bank_sources.swile_oauth.sync_runner import (
    perform_sync as swile_perform_sync,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)
from budget_forecaster.infrastructure.bootstrap import open_repository
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.import_service import ImportService
from budget_forecaster.services.operation.iteration_resolution_service import (
    IterationResolutionService,
)
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.operation.operation_service import OperationService
from budget_forecaster.web import formatting
from budget_forecaster.web.auth import make_serializer, require_session
from budget_forecaster.web.auth import router as auth_router
from budget_forecaster.web.config import resolve_web_secrets
from budget_forecaster.web.enrollment import (
    make_flash_serializer,
    make_pending_serializer,
)
from budget_forecaster.web.rendering import render_template
from budget_forecaster.web.routes import (
    bank,
    home,
    month,
    operations,
    overdue,
    settings,
    swile,
    targets,
    trends,
)
from budget_forecaster.web.routes import health as health_route

logger = logging.getLogger("budget_forecaster")

_ENV_CONFIG = "BUDGET_CONFIG"
_PACKAGE_DIR = Path(__file__).parent


def _build_app_service(
    config: Config, repository: RepositoryInterface
) -> ApplicationService:
    """Wire the services and ApplicationService."""
    persistent_account = PersistentAccount(repository)
    return ApplicationService(
        persistent_account=persistent_account,
        import_service=ImportService(
            persistent_account,
            config.inbox_path,
            config.inbox_exclude_patterns,
            config.inbox_include_patterns,
            config.accounts,
        ),
        operation_service=OperationService(persistent_account),
        forecast_service=ForecastService(
            persistent_account, persistent_account.repository
        ),
        operation_link_service=OperationLinkService(persistent_account.repository),
        iteration_resolution_service=IterationResolutionService(
            persistent_account.repository
        ),
    )


def _build_consent_service(config: Config) -> ConsentService | None:
    """Build the consent service, or None when Enable Banking is not configured."""
    if config.enable_banking is None:
        return None
    client = EnableBankingClient(
        config.enable_banking.application_id,
        config.enable_banking.private_key_path,
        config.enable_banking.redirect_url,
    )
    return ConsentService(client, ConsentStore.default())


def _compute_report(app_service: ApplicationService) -> None:
    """Populate the cached report, tolerating an empty database."""
    try:
        app_service.compute_report()
    except BudgetForecasterError:
        logger.warning("No account data yet; forecast views will be empty")


def _startup_swile_sync(
    config: Config,
    repository: RepositoryInterface,
    app_service: ApplicationService,
    token_store: SwileTokenStore,
    client: SwileClient,
) -> None:
    """Opportunistically sync Swile at startup when a token is enrolled.

    Best-effort: perform_sync records its own outcome and never raises, so a
    failed refresh just leaves the reconnect banner for the user.

    This runs on the boot path and does blocking Swile I/O, so a slow endpoint
    delays readiness — bounded by the client's per-request timeout (a hang fails
    the run rather than stalling for minutes). Acceptable at personal scale,
    where the host boots rarely and only pending pages are fetched.
    """
    if token_store.load() is None:
        return
    logger.info("Swile enrolled; syncing at startup")
    run = swile_perform_sync(repository, token_store, config.accounts, client=client)
    if run.status is SyncRunStatus.OK:
        try:
            app_service.reload_account()
        except BudgetForecasterError:
            logger.warning("Swile startup sync: no account to reload")


def _swile_enroll_bookmarklet() -> str:
    """The draggable enroll bookmarklet, generated by build_swile_bookmarklet.py."""
    path = _PACKAGE_DIR / "static" / "swile_enroll.bookmarklet"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _build_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(_PACKAGE_DIR / "templates"))
    templates.env.globals["_"] = _
    templates.env.globals["swile_enroll_bookmarklet"] = _swile_enroll_bookmarklet()
    formatting.register_filters(templates.env)
    return templates


def create_app(config_path: Path | None = None) -> FastAPI:
    """Build the web application from the given (or env-provided) config file."""
    if config_path is None:
        config_path = Path(os.environ.get(_ENV_CONFIG, "config.yaml"))

    config = Config()
    config.parse(config_path)
    config.setup_logging()
    setup_i18n(config.language)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Build the repository on the serving thread so the single shared
        # SQLite connection is created and used from the same thread.
        logger.info("Starting Budget Forecaster web app")
        repository = open_repository(config)
        app_service = _build_app_service(config, repository)
        _startup_swile_sync(
            config,
            repository,
            app_service,
            app.state.swile_token_store,
            app.state.swile_client,
        )
        _compute_report(app_service)
        app.state.repository = repository
        app.state.app_service = app_service
        yield

    app = FastAPI(title="Budget Forecaster", lifespan=lifespan)
    app.state.config = config
    app.state.backup_service = BackupService(
        config.database_path,
        config.backup.directory,
        config.backup.max_backups,
    )
    app.state.consent_service = _build_consent_service(config)
    app.state.web_secrets = resolve_web_secrets(config)
    app.state.swile_token_store = SwileTokenStore.default(
        app.state.web_secrets.secret_key
    )
    app.state.swile_client = SwileClient()
    app.state.serializer = make_serializer(app.state.web_secrets.secret_key)
    app.state.pending_serializer = make_pending_serializer(
        app.state.web_secrets.secret_key
    )
    app.state.flash_serializer = make_flash_serializer(app.state.web_secrets.secret_key)
    app.state.templates = _build_templates()

    app.add_middleware(BaseHTTPMiddleware, dispatch=require_session)
    app.mount(
        "/static", StaticFiles(directory=str(_PACKAGE_DIR / "static")), name="static"
    )

    for not_found in (
        BudgetNotFoundError,
        PlannedOperationNotFoundError,
        OperationNotFoundError,
    ):
        app.add_exception_handler(not_found, _handle_not_found)

    app.include_router(health_route.router)
    app.include_router(auth_router)
    app.include_router(home.router)
    app.include_router(month.router)
    app.include_router(operations.router)
    app.include_router(targets.router)
    app.include_router(trends.router)
    app.include_router(overdue.router)
    app.include_router(settings.router)
    app.include_router(bank.router)
    app.include_router(swile.router)
    return app


async def _handle_not_found(request: Request, _exc: Exception) -> Response:
    """Render a 404 page (e.g. a stale link to a deleted budget or operation)."""
    return render_template(request, "not_found.html", active="", status_code=404)
