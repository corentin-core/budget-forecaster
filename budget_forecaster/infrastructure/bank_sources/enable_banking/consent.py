"""Enable Banking consent: the persisted state of a bank authorization.

A consent ties an authorized session to the accounts it unlocks and to the
date the bank authorization expires (~180 days for BNP; varies by bank). Its
status drives when the user must re-authenticate at the bank.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

# Default lead time before expiry at which a consent is flagged as expiring,
# giving the user time to renew before the session stops working.
_DEFAULT_EXPIRING_WITHIN = timedelta(days=14)


class ConsentStatus(Enum):
    """Lifecycle state of a consent relative to its expiry date."""

    VALID = "valid"
    EXPIRING = "expiring"
    EXPIRED = "expired"


@dataclass(frozen=True)
class Consent:
    """An authorized Enable Banking session and the accounts it unlocks."""

    session_id: str
    account_uids: tuple[str, ...]
    valid_until: datetime
    aspsp_name: str
    aspsp_country: str
    created_at: datetime

    def status(
        self,
        now: datetime,
        expiring_within: timedelta = _DEFAULT_EXPIRING_WITHIN,
    ) -> ConsentStatus:
        """Return the status at now.

        EXPIRED once the expiry is reached, EXPIRING within expiring_within
        of it, VALID otherwise.
        """
        remaining = self.valid_until - now
        if remaining <= timedelta(0):
            return ConsentStatus.EXPIRED
        if remaining <= expiring_within:
            return ConsentStatus.EXPIRING
        return ConsentStatus.VALID

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "session_id": self.session_id,
            "account_uids": list(self.account_uids),
            "valid_until": self.valid_until.isoformat(),
            "aspsp_name": self.aspsp_name,
            "aspsp_country": self.aspsp_country,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Consent":
        """Rebuild a consent from its serialized form."""
        return cls(
            session_id=data["session_id"],
            account_uids=tuple(data["account_uids"]),
            valid_until=_parse_datetime(data["valid_until"]),
            aspsp_name=data["aspsp_name"],
            aspsp_country=data["aspsp_country"],
            created_at=_parse_datetime(data["created_at"]),
        )


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime as an aware UTC value (naive input assumed UTC)."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
