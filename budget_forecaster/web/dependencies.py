"""FastAPI dependencies exposing the singletons built at startup on app.state."""

import logging

from fastapi import Request

from budget_forecaster.exceptions import BudgetForecasterError
from budget_forecaster.infrastructure.backup import BackupService
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import SwileClient
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.services.application_service import ApplicationService

logger = logging.getLogger("budget_forecaster")


def get_app_service(request: Request) -> ApplicationService:
    """Return the shared ApplicationService."""
    return request.app.state.app_service


def refresh_forecast(app: ApplicationService) -> None:
    """Reload the forecast and recompute the report after a write.

    reload_forecast() alone drops the cached report; the month/home/trends views
    read that report, so the web must recompute it eagerly. Tolerates an empty
    database.
    """
    app.reload_forecast()
    try:
        app.compute_report()
    except BudgetForecasterError:
        logger.warning("Report recompute skipped: no account data")


def get_consent_service(request: Request) -> ConsentService | None:
    """Return the consent service, or None when Enable Banking is not configured."""
    return request.app.state.consent_service


def get_swile_token_store(request: Request) -> SwileTokenStore:
    """Return the shared Swile token store."""
    return request.app.state.swile_token_store


def get_swile_client(request: Request) -> SwileClient:
    """Return the shared Swile HTTP client."""
    return request.app.state.swile_client


def get_repository(request: Request) -> RepositoryInterface:
    """Return the shared repository."""
    return request.app.state.repository


def get_config(request: Request) -> Config:
    """Return the loaded configuration."""
    return request.app.state.config


def get_backup_service(request: Request) -> BackupService:
    """Return the shared backup service."""
    return request.app.state.backup_service
