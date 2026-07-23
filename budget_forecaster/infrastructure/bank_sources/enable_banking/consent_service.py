"""Consent lifecycle backend for Enable Banking.

Drives enrollment, persistence, status and renewal on top of
EnableBankingClient and ConsentStore. Shared by the CLI sync and the
web enrollment UI; it holds no UI concern (redirect capture lives in the
caller).
"""

import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from budget_forecaster.infrastructure.bank_sources.enable_banking.client import (
    EnableBankingClient,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    Consent,
    ConsentStatus,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_store import (
    ConsentStore,
)

logger = logging.getLogger(__name__)

# BNP grants ~180 days; other banks may cap lower and shorten it on their side.
_DEFAULT_VALID_DAYS = 180


@dataclass(frozen=True)
class ConsentState:
    """A consent's status paired with its expiry, for callers to display."""

    status: ConsentStatus
    valid_until: datetime | None


class NoConsentError(RuntimeError):
    """Raised when an operation needs a consent but none is available."""


class ConsentService:
    """Enroll, persist, inspect and renew an Enable Banking consent."""

    def __init__(self, client: EnableBankingClient, store: ConsentStore) -> None:
        self._client = client
        self._store = store

    def list_banks(self, country: str = "FR") -> tuple[dict[str, Any], ...]:
        """List the banks available for enrollment in a country."""
        return self._client.list_aspsps(country)

    def start_enrollment(
        self,
        aspsp_name: str,
        country: str = "FR",
        valid_days: int = _DEFAULT_VALID_DAYS,
        state: str | None = None,
    ) -> str:
        """Start an authorization and return the bank redirect URL.

        The caller sends the user to the URL; the bank redirects back with a
        code to pass to complete_enrollment. state is echoed back on
        the redirect for correlation; a random one is generated when omitted.
        """
        valid_until = _now() + timedelta(days=valid_days)
        return self._client.start_authorization(
            aspsp_name=aspsp_name,
            country=country,
            valid_until=_to_api_datetime(valid_until),
            state=state or secrets.token_urlsafe(16),
        )

    def complete_enrollment(
        self, code: str, aspsp_name: str, country: str = "FR"
    ) -> Consent:
        """Exchange the authorization code for a session and persist the consent.

        aspsp_name/country identify the bank being linked so a later
        renewal can target it.
        """
        session = self._client.create_session(code)
        consent = Consent(
            session_id=session["session_id"],
            account_uids=_extract_account_uids(session),
            valid_until=_extract_valid_until(session),
            aspsp_name=aspsp_name,
            aspsp_country=country,
            created_at=_now(),
        )
        self._store.save(consent)
        logger.info(
            "Stored consent for %s: %d account(s), valid until %s",
            aspsp_name,
            len(consent.account_uids),
            consent.valid_until.date(),
        )
        return consent

    def current_consent(self) -> Consent | None:
        """Return the persisted consent, or None if none is stored."""
        return self._store.load()

    def state(self) -> ConsentState:
        """Return the current consent status and expiry.

        A missing consent reads as EXPIRED with no expiry date.
        """
        if (consent := self._store.load()) is None:
            return ConsentState(ConsentStatus.EXPIRED, None)
        return ConsentState(consent.status(_now()), consent.valid_until)

    def renew(self, state: str | None = None) -> str:
        """Start a fresh authorization for the stored bank, returning its URL.

        Renewal still needs the user to authenticate at the bank; completion
        goes through complete_enrollment with the new code.
        """
        if (consent := self._store.load()) is None:
            raise NoConsentError("No consent to renew; enroll first.")
        return self.start_enrollment(
            aspsp_name=consent.aspsp_name,
            country=consent.aspsp_country,
            state=state,
        )

    def resolve_account_uid(self, preferred: str | None = None) -> str:
        """Return the account uid to sync from the active consent.

        Fails when there is no consent, it has expired, or preferred is not
        among its accounts. With several accounts and no preferred, the
        selection is ambiguous and rejected.
        """
        if (consent := self._store.load()) is None:
            raise NoConsentError("No consent stored; run enrollment first.")
        if consent.status(_now()) is ConsentStatus.EXPIRED:
            raise NoConsentError(
                f"Consent expired on {consent.valid_until.date()}; renew it."
            )
        if preferred is not None:
            if preferred not in consent.account_uids:
                raise NoConsentError(
                    f"Account {preferred!r} is not in the current consent."
                )
            return preferred
        if len(consent.account_uids) == 1:
            return consent.account_uids[0]
        raise NoConsentError(
            "Consent unlocks several accounts; set account_uid in the config."
        )


def _extract_account_uids(session: dict[str, Any]) -> tuple[str, ...]:
    """Read account uids from a session payload (uid strings or objects)."""
    accounts = session.get("accounts", [])
    return tuple(
        account if isinstance(account, str) else account["uid"] for account in accounts
    )


def _extract_valid_until(session: dict[str, Any]) -> datetime:
    """Read the granted consent expiry from a session payload."""
    access = session.get("access", {})
    if "valid_until" not in access:
        raise ValueError("Session payload has no access.valid_until")
    return _parse_api_datetime(access["valid_until"])


def _parse_api_datetime(value: str) -> datetime:
    """Parse an API datetime as aware UTC (naive input assumed UTC)."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _to_api_datetime(value: datetime) -> str:
    """Format a datetime as the API's ...Z UTC string."""
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now() -> datetime:
    """Current aware UTC time."""
    return datetime.now(timezone.utc)
