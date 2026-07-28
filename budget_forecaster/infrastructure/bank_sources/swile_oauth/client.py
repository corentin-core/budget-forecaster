"""HTTP client for the unofficial Swile web API.

Refreshes an access token from a refresh token, then reads operations and
wallets. The access token lives 30 min; each refresh returns a new refresh
token (soft rotation: the previous one stays valid). Auth uses the public web
client_id and API key from constants. Headers and pagination mirror the export
bookmarklet.
"""

import logging
from datetime import datetime, timezone
from typing import Any, NamedTuple

import requests

from budget_forecaster.infrastructure.bank_sources.swile_oauth import constants

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30
_ITEMS_PER_PAGE = 100
_MAX_PAGES = 50  # ~5000 operations safety cap, as in the bookmarklet


class TokenBundle(NamedTuple):
    """Tokens returned by a refresh call."""

    access_token: str
    refresh_token: str
    expires_in: int


class SwileClient:
    """Client talking to the Swile web endpoints for a single user."""

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def refresh(self, refresh_token: str) -> TokenBundle:
        """Exchange a refresh token for a fresh access token and rotated token."""
        body = {
            "grant_type": "refresh_token",
            "client_id": constants.CLIENT_ID,
            "refresh_token": refresh_token,
        }
        response = self._session.post(
            constants.TOKEN_URL, json=body, timeout=_REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        return TokenBundle(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data["expires_in"],
        )

    def get_operations(self, access_token: str) -> dict[str, Any]:
        """Fetch all operations, following the cursor pagination.

        Returns an operations.json-shaped payload (an items list), the same
        shape the parser reads from a downloaded export.
        """
        items: list[dict[str, Any]] = []
        cursor: str | None = datetime.now(timezone.utc).isoformat()
        for _ in range(_MAX_PAGES):
            page = self._get(
                constants.OPERATIONS_URL,
                access_token,
                params={"before": cursor, "per": _ITEMS_PER_PAGE},
            )
            items.extend(page.get("items", []))
            if not page.get("has_more"):
                break
            if not (cursor := page.get("next_cursor")):
                break
        else:
            logger.warning(
                "Swile operations hit the %d-page cap; older operations skipped",
                _MAX_PAGES,
            )
        return {"items": items}

    def get_wallets(self, access_token: str) -> dict[str, Any]:
        """Fetch the wallets payload (same shape as the export wallets.json)."""
        return self._get(
            constants.WALLETS_URL, access_token, extra_headers={"X-API-Version": "0"}
        )

    def _get(
        self,
        url: str,
        access_token: str,
        *,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send an authenticated GET and return the parsed JSON body."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-API-Key": constants.X_API_KEY,
            "X-Lunchr-Platform": "web",
            "Content-Type": "application/json",
            # Swile returns operation names in the caller's language; without
            # this the API defaults to English and won't dedup against French
            # file imports.
            "Accept-Language": "fr-FR",
        }
        if extra_headers:
            headers.update(extra_headers)
        response = self._session.get(
            url, headers=headers, params=params, timeout=_REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
