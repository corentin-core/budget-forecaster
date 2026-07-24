"""Bank enrollment routes: picker, redirect to the bank, and the fail-closed
OAuth callback."""

from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from requests import RequestException

from budget_forecaster.web.enrollment import PENDING_COOKIE


def _connect(app: FastAPI, service: Mock, *, aspsp_name: str | None = None) -> None:
    """Wire a consent-service double and a configured Enable Banking section."""
    app.state.consent_service = service
    app.state.config.enable_banking = SimpleNamespace(
        aspsp_country="FR", aspsp_name=aspsp_name
    )


def _service(**attrs: object) -> Mock:
    service = Mock()
    service.current_consent.return_value = None
    service.list_banks.return_value = ({"name": "BNP Paribas"}, {"name": "Boursorama"})
    service.start_enrollment.return_value = "https://bank.example/authorize?x=1"
    for name, value in attrs.items():
        setattr(service, name, value)
    return service


class TestLinkPage:
    """GET /settings/bank/link adapts to whether a bank is already known."""

    def test_lists_banks_to_pick(self, client: TestClient, app: FastAPI) -> None:
        """With no consent, the page lists the banks to choose from."""
        _connect(app, _service())
        html = client.get("/settings/bank/link").text
        assert "BNP Paribas" in html
        assert "Boursorama" in html
        assert "Continuer" in html

    def test_renew_mode_skips_picker(self, client: TestClient, app: FastAPI) -> None:
        """An existing consent shows the renewal page, not the picker."""
        service = _service()
        service.current_consent.return_value = SimpleNamespace(
            aspsp_name="BNP Paribas", aspsp_country="FR"
        )
        _connect(app, service)
        html = client.get("/settings/bank/link").text
        assert "Renouveler la connexion bancaire" in html
        assert "Boursorama" not in html
        service.list_banks.assert_not_called()

    def test_redirects_when_not_configured(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Without Enable Banking, the page redirects back to Réglages."""
        app.state.consent_service = None
        response = client.get("/settings/bank/link", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/settings"


class TestStartLink:
    """POST /settings/bank/link validates the bank before opening authorization."""

    def test_valid_bank_redirects_to_bank(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A known bank opens an authorization and stashes the pending cookie."""
        service = _service()
        _connect(app, service)
        response = client.post(
            "/settings/bank/link",
            data={"aspsp_name": "BNP Paribas"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "https://bank.example/authorize?x=1"
        assert PENDING_COOKIE in response.cookies
        service.start_enrollment.assert_called_once()

    def test_unknown_bank_is_rejected(self, client: TestClient, app: FastAPI) -> None:
        """An unlisted bank name is refused without opening an authorization."""
        service = _service()
        _connect(app, service)
        response = client.post(
            "/settings/bank/link",
            data={"aspsp_name": "Not A Bank"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/settings/bank/link"
        service.start_enrollment.assert_not_called()


class TestRenew:
    """POST /settings/bank/renew re-authorizes the currently linked bank."""

    def test_redirects_to_bank_for_current_consent(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """Renew reuses the linked bank and redirects to it."""
        service = _service()
        service.current_consent.return_value = SimpleNamespace(
            aspsp_name="BNP Paribas", aspsp_country="FR"
        )
        _connect(app, service)
        response = client.post("/settings/bank/renew", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "https://bank.example/authorize?x=1"
        service.start_enrollment.assert_called_once()
        assert service.start_enrollment.call_args.args == ("BNP Paribas", "FR")
        assert service.start_enrollment.call_args.kwargs["state"]

    def test_noop_without_consent(self, client: TestClient, app: FastAPI) -> None:
        """Renew with nothing linked redirects back without acting."""
        service = _service()
        _connect(app, service)
        response = client.post("/settings/bank/renew", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/settings"
        service.start_enrollment.assert_not_called()


class TestCallback:
    """GET /settings/bank/callback fails closed and only completes on a match."""

    def _set_pending(self, client: TestClient, app: FastAPI, state: str) -> None:
        token = app.state.pending_serializer.dumps([state, "BNP Paribas", "FR"])
        client.cookies.set(PENDING_COOKIE, token)

    def test_completes_on_matching_state(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A matching state completes enrollment and flashes success."""
        service = _service()
        _connect(app, service)
        self._set_pending(client, app, "match-state")
        response = client.get(
            "/settings/bank/callback",
            params={"code": "auth-code", "state": "match-state"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        service.complete_enrollment.assert_called_once_with(
            "auth-code", "BNP Paribas", "FR"
        )
        assert "Banque liée" in client.get("/settings").text

    def test_state_mismatch_does_not_complete(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A mismatched state is rejected and flashes an error."""
        service = _service()
        _connect(app, service)
        self._set_pending(client, app, "real-state")
        client.get(
            "/settings/bank/callback",
            params={"code": "auth-code", "state": "wrong-state"},
            follow_redirects=False,
        )
        service.complete_enrollment.assert_not_called()
        assert "Échec de la liaison" in client.get("/settings").text

    def test_missing_pending_does_not_complete(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A callback with no pending cookie never completes."""
        service = _service()
        _connect(app, service)
        client.get(
            "/settings/bank/callback",
            params={"code": "auth-code", "state": "any"},
            follow_redirects=False,
        )
        service.complete_enrollment.assert_not_called()

    def test_bank_error_is_cancelled(self, client: TestClient, app: FastAPI) -> None:
        """An error from the bank flashes cancelled, not a failure."""
        service = _service()
        _connect(app, service)
        self._set_pending(client, app, "s")
        client.get(
            "/settings/bank/callback",
            params={"error": "access_denied"},
            follow_redirects=False,
        )
        service.complete_enrollment.assert_not_called()
        assert "Liaison annulée" in client.get("/settings").text

    def test_completion_failure_flashes_error(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A matching state but a failing exchange flashes an error, not a 500."""
        service = _service()
        service.complete_enrollment.side_effect = RequestException("boom")
        _connect(app, service)
        self._set_pending(client, app, "s")
        response = client.get(
            "/settings/bank/callback",
            params={"code": "auth-code", "state": "s"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "Échec de la liaison" in client.get("/settings").text


class TestApiErrors:
    """A transient Enable Banking API error degrades gracefully, never 500s."""

    def test_start_link_flashes_error_on_api_failure(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A bank-list failure during enrollment flashes an error."""
        service = _service()
        service.list_banks.side_effect = RequestException("boom")
        _connect(app, service)
        response = client.post(
            "/settings/bank/link",
            data={"aspsp_name": "BNP Paribas"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/settings"
        service.start_enrollment.assert_not_called()
        assert "Échec de la liaison" in client.get("/settings").text

    def test_link_page_shows_empty_state_on_api_failure(
        self, client: TestClient, app: FastAPI
    ) -> None:
        """A bank-list failure renders the empty state instead of crashing."""
        service = _service()
        service.list_banks.side_effect = RequestException("boom")
        _connect(app, service)
        html = client.get("/settings/bank/link").text
        assert "Aucune banque disponible" in html
