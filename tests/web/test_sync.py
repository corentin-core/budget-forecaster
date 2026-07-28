"""Réglages sync history and the "Sync now" action."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from budget_forecaster.core.types import SyncRun, SyncRunStatus
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    ConsentStatus,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_service import (
    ConsentState,
)
from budget_forecaster.web.routes import settings as settings_route


def _repo_with_runs(*runs: SyncRun) -> Mock:
    """A repository double returning the given runs, newest first."""
    repo = Mock()
    repo.get_recent_sync_runs.return_value = tuple(runs)
    return repo


def _connected_service() -> Mock:
    """A consent-service double: a stored, valid consent (the source is connected)."""
    service = Mock()
    service.state.return_value = ConsentState(
        ConsentStatus.VALID, datetime(2027, 1, 1, tzinfo=timezone.utc)
    )
    service.current_consent.return_value = Mock(
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc)
    )
    return service


class TestSyncHistory:
    """The settings page lists recent syncs when a connection is configured."""

    def test_shows_empty_history(self, client: TestClient, app: FastAPI) -> None:
        """A configured connection with no run shows an empty history, not nothing."""
        app.state.consent_service = _connected_service()
        html = client.get("/settings").text
        assert "Synchronisations récentes" in html
        assert "Aucune synchronisation" in html

    def test_history_hidden_when_not_configured(self, client: TestClient) -> None:
        """No bank connection: the sync history section is not shown at all."""
        html = client.get("/settings").text
        assert "Synchronisations récentes" not in html

    def test_lists_recorded_runs(self, client: TestClient, app: FastAPI) -> None:
        """A success shows its balance; a failure shows a translated message,
        never the raw exception text."""
        app.state.consent_service = _connected_service()
        app.state.repository = _repo_with_runs(
            SyncRun(
                datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc),
                SyncRunStatus.OK,
                new_count=3,
                duplicate_count=41,
                balance=4812.55,
            ),
            SyncRun(
                datetime(2026, 7, 21, 6, 0, tzinfo=timezone.utc),
                SyncRunStatus.FAILED,
                error="NoConsentError: expired",
            ),
        )
        html = client.get("/settings").text
        assert "Solde" in html
        assert "Consentement expiré ou absent" in html
        assert "NoConsentError" not in html


class TestSyncNow:
    """POST /settings/sync runs the all-sources orchestrator, refreshing on success."""

    def test_noop_when_nothing_connected(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """No connected source: the button redirects without reloading anything."""
        app.state.consent_service = None
        reloaded: list[str] = []
        app.state.app_service.reload_account = lambda: reloaded.append("reload")
        response = client.post("/settings/sync", follow_redirects=False)
        assert response.status_code == 303
        assert not reloaded

    def test_runs_and_refreshes_on_success(
        self, client: TestClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A successful sync reloads the account, then refreshes the forecast."""
        steps: list[str] = []

        def fake_sync_all(*_args: object, **_kwargs: object) -> tuple[SyncRun, ...]:
            steps.append("sync")
            return (
                SyncRun(
                    datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc),
                    SyncRunStatus.OK,
                    new_count=0,
                    duplicate_count=0,
                    balance=0.0,
                ),
            )

        monkeypatch.setattr(settings_route, "sync_all_sources", fake_sync_all)
        monkeypatch.setattr(
            app.state.app_service, "reload_account", lambda: steps.append("reload")
        )
        monkeypatch.setattr(
            settings_route, "refresh_forecast", lambda _app: steps.append("refresh")
        )

        response = client.post("/settings/sync", follow_redirects=False)

        assert response.status_code == 303
        assert steps == ["sync", "reload", "refresh"]

    def test_no_refresh_when_all_failed(
        self, client: TestClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When every source fails, the account is not reloaded (tolerates empty DB)."""
        steps: list[str] = []

        def fake_sync_all(*_args: object, **_kwargs: object) -> tuple[SyncRun, ...]:
            return (
                SyncRun(
                    datetime(2026, 7, 23, 6, 0, tzinfo=timezone.utc),
                    SyncRunStatus.FAILED,
                    error="boom",
                ),
            )

        monkeypatch.setattr(settings_route, "sync_all_sources", fake_sync_all)
        monkeypatch.setattr(
            app.state.app_service, "reload_account", lambda: steps.append("reload")
        )

        response = client.post("/settings/sync", follow_redirects=False)

        assert response.status_code == 303
        assert not steps
