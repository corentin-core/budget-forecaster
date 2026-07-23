"""FastAPI dependencies exposing the singletons built at startup on app.state."""

from fastapi import Request

from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.services.application_service import ApplicationService


def get_app_service(request: Request) -> ApplicationService:
    """Return the shared ApplicationService."""
    return request.app.state.app_service


def get_consent_service(request: Request) -> ConsentService | None:
    """Return the consent service, or None when Enable Banking is not configured."""
    return request.app.state.consent_service
