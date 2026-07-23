"""Consent banner: shown when expiring/expired, silent otherwise."""

from datetime import datetime
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    ConsentStatus,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentState,
)
from budget_forecaster.web.alerts import consent_alert


def _consent_stub(state: ConsentState) -> Mock:
    """A consent-service double whose state() returns the given state."""
    stub = Mock()
    stub.state.return_value = state
    return stub


class TestConsentAlert:
    """consent_alert maps live consent state to a banner or nothing."""

    def test_no_alert_when_service_missing(self) -> None:
        """No service (Enable Banking off) yields no alert."""
        assert consent_alert(None) is None

    def test_no_alert_when_valid(self) -> None:
        """A valid consent yields no alert."""
        stub = _consent_stub(ConsentState(ConsentStatus.VALID, datetime(2027, 1, 1)))
        assert consent_alert(stub) is None

    def test_alert_when_expiring(self) -> None:
        """An expiring consent yields an alert with its expiry date."""
        stub = _consent_stub(
            ConsentState(ConsentStatus.EXPIRING, datetime(2026, 7, 28))
        )
        alert = consent_alert(stub)
        assert alert is not None
        assert alert.status is ConsentStatus.EXPIRING
        assert alert.valid_until == datetime(2026, 7, 28).date()

    def test_alert_when_expired(self) -> None:
        """An expired consent with no expiry yields an alert."""
        stub = _consent_stub(ConsentState(ConsentStatus.EXPIRED, None))
        alert = consent_alert(stub)
        assert alert is not None
        assert alert.status is ConsentStatus.EXPIRED
        assert alert.valid_until is None


class TestBannerRendering:
    """The base layout renders the banner only for a real alert."""

    def test_banner_rendered_when_expiring(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """An expiring consent renders the banner on the page."""
        app.state.consent_service = _consent_stub(
            ConsentState(ConsentStatus.EXPIRING, datetime(2026, 7, 28))
        )
        html = client.get("/").text
        assert 'class="banner' in html
        assert "Connexion bancaire" in html

    def test_no_banner_when_not_configured(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """No consent service renders no banner."""
        app.state.consent_service = None
        html = client.get("/").text
        assert 'class="banner' not in html
