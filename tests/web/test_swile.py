"""Swile enrollment and sync routes over the real app with a faked client."""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.core.types import SyncRun, SyncRunStatus, SyncSource
from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import TokenBundle
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)

_OPERATIONS = {
    "items": [
        {
            "name": "Restaurant",
            "transactions": [
                {
                    "status": "CAPTURED",
                    "payment_method": "Wallets::MealVoucherWallet",
                    "date": "2026-07-24T13:00:00.000+02:00",
                    "amount": {"value": -1400, "currency": {"iso_3": "EUR"}},
                }
            ],
        }
    ]
}
_WALLETS = {"wallets": [{"type": "meal_voucher", "balance": {"value": 50.0}}]}


def _fake_client() -> MagicMock:
    """A Swile client double returning a rotated token and canned payloads."""
    client = MagicMock()
    client.refresh.return_value = TokenBundle("acc", "rotated-rt", 1800)
    client.get_operations.return_value = _OPERATIONS
    client.get_wallets.return_value = _WALLETS
    return client


def _latest_swile_run(app: FastAPI) -> SyncRun | None:
    """Read the latest Swile run via a fresh connection (the app's is bound to
    its serving thread)."""
    with SqliteRepository(app.state.config.database_path) as repo:
        runs = repo.get_recent_sync_runs(1, source=SyncSource.SWILE)
    return runs[0] if runs else None


class TestEnroll:
    """Pasting a token stores it, syncs, and reports the outcome."""

    def test_enroll_stores_token_and_syncs(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A valid token is stored (rotated) and a Swile sync runs."""
        app.state.swile_client = _fake_client()
        response = client.post(
            "/settings/swile/enroll",
            data={"refresh_token": "pasted-rt"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "Swile connecté et synchronisé." in response.text
        assert app.state.swile_token_store.load() == "rotated-rt"
        run = _latest_swile_run(app)
        assert run is not None and run.status is SyncRunStatus.OK

    def test_blank_token_flashes_error_and_stores_nothing(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A blank field is rejected without touching the store."""
        app.state.swile_client = _fake_client()
        response = client.post(
            "/settings/swile/enroll",
            data={"refresh_token": "   "},
            follow_redirects=True,
        )
        assert "Échec de la connexion Swile" in response.text
        assert app.state.swile_token_store.load() is None

    def test_rejected_token_flashes_error_and_stores_nothing(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A token the refresh endpoint rejects stores nothing."""
        failing = _fake_client()
        failing.refresh.side_effect = RuntimeError("invalid_grant")
        app.state.swile_client = failing
        response = client.post(
            "/settings/swile/enroll",
            data={"refresh_token": "bad-rt"},
            follow_redirects=True,
        )
        assert "Échec de la connexion Swile" in response.text
        assert app.state.swile_token_store.load() is None

    def test_valid_token_but_failed_first_sync_flashes_error(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """The token validates and is stored, but a failing first sync flashes error."""
        client_double = _fake_client()
        client_double.get_operations.side_effect = RuntimeError("operations down")
        app.state.swile_client = client_double
        response = client.post(
            "/settings/swile/enroll",
            data={"refresh_token": "good-rt"},
            follow_redirects=True,
        )
        assert "Échec de la connexion Swile" in response.text
        assert app.state.swile_token_store.load() == "rotated-rt"
        run = _latest_swile_run(app)
        assert run is not None and run.status is SyncRunStatus.FAILED


class TestSync:
    """The Sync Swile button records a run for an enrolled account."""

    def test_sync_records_ok_run(self, client: TestClient, app: FastAPI) -> None:
        """A sync with a stored token records an OK Swile run."""
        app.state.swile_client = _fake_client()
        app.state.swile_token_store.save("stored-rt")
        response = client.post("/settings/swile/sync", follow_redirects=True)
        assert response.status_code == 200
        run = _latest_swile_run(app)
        assert run is not None and run.status is SyncRunStatus.OK

    def test_sync_without_enrollment_records_failed_run(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Syncing with no stored token records a FAILED run, not an error page."""
        app.state.swile_client = _fake_client()
        response = client.post("/settings/swile/sync", follow_redirects=True)
        assert response.status_code == 200
        run = _latest_swile_run(app)
        assert run is not None and run.status is SyncRunStatus.FAILED

    def test_history_shows_swile_run_without_enable_banking(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A Swile run surfaces in the sync history even with no bank configured."""
        app.state.swile_client = _fake_client()
        app.state.swile_token_store.save("stored-rt")
        client.post("/settings/swile/sync")
        assert 'class="sync-runs"' in client.get("/settings").text


class TestSettingsCard:
    """The Swile card reflects the enrollment state."""

    def test_shows_not_connected_before_enrollment(self, client: TestClient) -> None:
        """Without a token the card invites enrollment."""
        assert "Pas encore connecté." in client.get("/settings").text

    def test_shows_connected_after_enrollment(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """After enrolling, the card shows the connected state."""
        app.state.swile_client = _fake_client()
        client.post("/settings/swile/enroll", data={"refresh_token": "rt"})
        assert "Connecté" in client.get("/settings").text

    def test_card_offers_draggable_bookmarklet(self, client: TestClient) -> None:
        """The card exposes the enroll bookmarklet as a draggable link."""
        html = client.get("/settings").text
        assert 'class="bookmarklet"' in html
        assert "javascript:" in html


class TestStartupSync:
    """The web app syncs Swile at startup when a token is enrolled."""

    def test_startup_syncs_when_enrolled(self, app: FastAPI) -> None:
        """Booting with a stored token records an OK Swile run."""
        app.state.swile_client = _fake_client()
        app.state.swile_token_store.save("stored-rt")
        with TestClient(app):
            pass
        run = _latest_swile_run(app)
        assert run is not None and run.status is SyncRunStatus.OK

    def test_startup_survives_failed_refresh(self, app: FastAPI) -> None:
        """A failing refresh at startup records a FAILED run but boots cleanly."""
        failing = _fake_client()
        failing.refresh.side_effect = RuntimeError("token revoked")
        app.state.swile_client = failing
        app.state.swile_token_store.save("stored-rt")
        with TestClient(app) as booted:
            assert booted.get("/health").status_code == 200
        run = _latest_swile_run(app)
        assert run is not None and run.status is SyncRunStatus.FAILED

    def test_no_startup_sync_without_enrollment(self, app: FastAPI) -> None:
        """Booting without a token records no Swile run."""
        app.state.swile_client = _fake_client()
        with TestClient(app):
            pass
        assert _latest_swile_run(app) is None
