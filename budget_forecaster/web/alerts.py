"""Derive the in-app banners: live consent state and the last sync outcome."""

from datetime import date, datetime, timezone
from typing import NamedTuple

from budget_forecaster.core.types import SyncRunStatus
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    ConsentStatus,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
)
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)


class ConsentAlert(NamedTuple):
    """A consent state worth surfacing to the user (EXPIRING or EXPIRED)."""

    status: ConsentStatus
    valid_until: date | None


def consent_alert(consent_service: ConsentService | None) -> ConsentAlert | None:
    """Return an alert when consent is expiring or expired, else None.

    None also when Enable Banking is not configured (no service): a missing
    integration is not an alert.
    """
    if consent_service is None:
        return None
    state = consent_service.state()
    if state.status is ConsentStatus.VALID:
        return None
    valid_until = state.valid_until.date() if state.valid_until else None
    return ConsentAlert(state.status, valid_until)


class SyncFailureAlert(NamedTuple):
    """The most recent sync run, surfaced because it failed."""

    ran_at: datetime
    error: str | None


def sync_failure_alert(
    repository: RepositoryInterface,
    consent_service: ConsentService | None,
) -> SyncFailureAlert | None:
    """Return an alert when the latest sync failed, unless the consent banner
    already covers it or a later re-authorization has made it stale."""
    recent = repository.get_recent_sync_runs(1)
    if not recent or recent[0].status is not SyncRunStatus.FAILED:
        return None
    latest = recent[0]
    if consent_service is not None and (consent := consent_service.current_consent()):
        # An expired consent already raises the consent banner; don't double up.
        if consent.status(datetime.now(timezone.utc)) is ConsentStatus.EXPIRED:
            return None
        # A failure from before the current consent is stale: re-authorized since.
        if consent.created_at > latest.ran_at:
            return None
    return SyncFailureAlert(latest.ran_at, latest.error)
