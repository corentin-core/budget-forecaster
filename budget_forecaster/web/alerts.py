"""Derive the in-app consent banner from the live consent state.

Sync-run history is a later slice (#293 sub-issue 3); this covers consent only.
"""

from datetime import date
from typing import NamedTuple

from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    ConsentStatus,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentService,
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
