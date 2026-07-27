"""HTTP client for the unofficial Swile web API.

Refreshes an access token from a refresh token, then reads operations and
wallets. The access token lives 30 min; each refresh returns a new refresh
token (soft rotation: the previous one stays valid). Auth uses the public web
client_id and API key from constants.
"""

import logging
from typing import Any, NamedTuple

import requests

from budget_forecaster.infrastructure.bank_sources.swile_oauth import constants

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30


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
        """Fetch the operations payload (same shape as the export operations.json)."""
        return self._get(constants.OPERATIONS_URL, access_token)

    def get_wallets(self, access_token: str) -> dict[str, Any]:
        """Fetch the wallets payload (same shape as the export wallets.json)."""
        return self._get(constants.WALLETS_URL, access_token)

    def _get(self, url: str, access_token: str) -> dict[str, Any]:
        """Send an authenticated GET and return the parsed JSON body."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-API-Key": constants.X_API_KEY,
        }
        response = self._session.get(url, headers=headers, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
