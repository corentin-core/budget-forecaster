"""Swile enrollment and token lifecycle.

Wraps the client and token store: enroll a refresh token (validated by one
refresh), mint an access token for a sync (re-storing the rotated refresh
token), and report whether an enrollment exists. Holds no UI concern.
"""

import logging

from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import SwileClient
from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)

logger = logging.getLogger(__name__)


class NotEnrolledError(RuntimeError):
    """Raised when a sync needs a refresh token but none is stored."""


class SwileConsentService:
    """Enroll, persist and refresh the Swile OAuth2 token."""

    def __init__(self, client: SwileClient, store: SwileTokenStore) -> None:
        self._client = client
        self._store = store

    def is_enrolled(self) -> bool:
        """Return whether a refresh token is stored."""
        return self._store.load() is not None

    def enroll(self, refresh_token: str) -> None:
        """Validate a refresh token with one refresh, then store the rotated token.

        A bad token surfaces as the client's HTTP error, leaving nothing stored.
        """
        bundle = self._client.refresh(refresh_token)
        self._store.save(bundle.refresh_token)
        logger.info("Stored Swile refresh token")

    def authenticate(self) -> str:
        """Return a fresh access token, re-storing the rotated refresh token."""
        if (refresh_token := self._store.load()) is None:
            raise NotEnrolledError("No Swile refresh token stored; enroll first.")
        bundle = self._client.refresh(refresh_token)
        self._store.save(bundle.refresh_token)
        return bundle.access_token

    def clear(self) -> None:
        """Forget the stored token."""
        self._store.clear()
