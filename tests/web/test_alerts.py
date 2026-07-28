"""Banners: consent state and last-sync failure; shown only when relevant."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.core.types import SyncRun, SyncRunStatus, SyncSource
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    ConsentStatus,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentState,
)
from budget_forecaster.web.alerts import (
    consent_alert,
    swile_reconnect_alert,
    sync_failure_alert,
)


def _repo_with_runs(*runs: SyncRun) -> Mock:
    """A repository double whose get_recent_sync_runs returns the given runs."""
    repo = Mock()
    repo.get_recent_sync_runs.return_value = tuple(runs)
    return repo


def _run(status: SyncRunStatus, **kwargs: object) -> SyncRun:
    return SyncRun(datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc), status, **kwargs)


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


def _consent_service(
    created_at: datetime, status: ConsentStatus = ConsentStatus.VALID
) -> Mock:
    """A consent-service double whose stored consent was granted at created_at."""
    consent = Mock(created_at=created_at)
    consent.status.return_value = status
    service = Mock()
    service.current_consent.return_value = consent
    return service


# Reference failure time used across the supersession tests.
_FAILED_AT = datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc)


class TestSyncFailureAlert:
    """sync_failure_alert surfaces the latest failure, unless a newer consent
    supersedes it."""

    def test_none_when_no_runs(self) -> None:
        """No recorded run yields no alert."""
        assert sync_failure_alert(_repo_with_runs(), None) is None

    def test_none_when_latest_ok(self) -> None:
        """A successful latest run yields no alert."""
        assert sync_failure_alert(_repo_with_runs(_run(SyncRunStatus.OK)), None) is None

    def test_alert_when_latest_failed_and_no_consent_service(self) -> None:
        """A failed latest run with Enable Banking off still alerts."""
        run = _run(SyncRunStatus.FAILED, error="NoConsentError: expired")
        alert = sync_failure_alert(_repo_with_runs(run), None)
        assert alert is not None
        assert alert.error == "NoConsentError: expired"

    def test_alert_when_no_stored_consent(self) -> None:
        """A configured service with no stored consent still alerts."""
        service = Mock()
        service.current_consent.return_value = None
        run = _run(SyncRunStatus.FAILED, error="boom")
        assert sync_failure_alert(_repo_with_runs(run), service) is not None

    def test_stale_failure_hidden_when_consent_is_newer(self) -> None:
        """A failure predating the current consent is stale: re-authorized since."""
        run = SyncRun(_FAILED_AT, SyncRunStatus.FAILED, error="NoConsentError")
        consent = _consent_service(_FAILED_AT + timedelta(days=1))
        assert sync_failure_alert(_repo_with_runs(run), consent) is None

    def test_failure_under_current_consent_still_shows(self) -> None:
        """A failure after the consent was granted (e.g. API down) still alerts."""
        run = SyncRun(_FAILED_AT, SyncRunStatus.FAILED, error="HTTPError: 503")
        consent = _consent_service(_FAILED_AT - timedelta(days=1))
        assert sync_failure_alert(_repo_with_runs(run), consent) is not None

    def test_hidden_when_consent_expired(self) -> None:
        """An expired consent already raises its own banner: no double alert."""
        run = SyncRun(_FAILED_AT, SyncRunStatus.FAILED, error="NoConsentError")
        consent = _consent_service(
            _FAILED_AT - timedelta(days=1), status=ConsentStatus.EXPIRED
        )
        assert sync_failure_alert(_repo_with_runs(run), consent) is None

    def test_queries_only_enable_banking_runs(self) -> None:
        """The banner filters the repository by the Enable Banking source."""
        repo = _repo_with_runs()
        sync_failure_alert(repo, None)
        repo.get_recent_sync_runs.assert_called_once_with(
            1, source=SyncSource.ENABLE_BANKING
        )


class TestSyncFailureBanner:
    """The failed-sync banner renders across pages when the last run failed."""

    def test_banner_rendered_when_last_sync_failed(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A failed last run renders the banner."""
        app.state.repository = _repo_with_runs(
            _run(SyncRunStatus.FAILED, error="NoConsentError: expired")
        )
        html = client.get("/").text
        assert "banner-failed" in html
        assert "Dernière synchronisation en échec" in html

    def test_no_banner_when_last_sync_ok(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A successful last run renders no failed-sync banner."""
        app.state.repository = _repo_with_runs(_run(SyncRunStatus.OK))
        assert "banner-failed" not in client.get("/").text


class TestSwileReconnectAlert:
    """swile_reconnect_alert surfaces the last failed Swile sync."""

    def test_alert_when_last_swile_run_failed(self) -> None:
        """A failed latest Swile run yields a reconnect alert."""
        run = _run(
            SyncRunStatus.FAILED, error="HTTPError: 401", source=SyncSource.SWILE
        )
        alert = swile_reconnect_alert(_repo_with_runs(run))
        assert alert is not None
        assert alert.error == "HTTPError: 401"

    def test_no_alert_when_last_swile_run_ok(self) -> None:
        """A successful latest Swile run yields no alert."""
        run = _run(SyncRunStatus.OK, source=SyncSource.SWILE)
        assert swile_reconnect_alert(_repo_with_runs(run)) is None

    def test_no_alert_without_any_swile_run(self) -> None:
        """No Swile run at all yields no alert."""
        assert swile_reconnect_alert(_repo_with_runs()) is None

    def test_queries_only_swile_runs(self) -> None:
        """The alert filters the repository by the Swile source."""
        repo = _repo_with_runs()
        swile_reconnect_alert(repo)
        repo.get_recent_sync_runs.assert_called_once_with(1, source=SyncSource.SWILE)
