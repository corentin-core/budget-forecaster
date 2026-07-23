"""Auth gating: the shared password protects every page but the public ones."""

import pytest
from fastapi.testclient import TestClient

from budget_forecaster.web.auth import hash_password, verify_password
from tests.web.conftest import PASSWORD

PROTECTED_PATHS = ["/", "/mois", "/operations", "/tendances", "/reglages"]
PUBLIC_PATHS = ["/health", "/login", "/static/app.css"]


class TestGating:
    """Session cookie required for private pages, not for public ones."""

    @pytest.mark.parametrize("path", PROTECTED_PATHS)
    def test_protected_paths_redirect_when_anonymous(
        self, anon_client: TestClient, path: str
    ) -> None:
        """An anonymous request to a private page redirects to /login."""
        response = anon_client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    @pytest.mark.parametrize("path", PUBLIC_PATHS)
    def test_public_paths_need_no_session(
        self, anon_client: TestClient, path: str
    ) -> None:
        """Health, login and static assets are reachable without a session."""
        assert anon_client.get(path).status_code == 200


class TestLogin:
    """Password check, session issuance and logout."""

    def test_wrong_password_is_rejected(self, anon_client: TestClient) -> None:
        """A wrong password returns 401 and sets no session cookie."""
        response = anon_client.post("/login", data={"password": "nope"})
        assert response.status_code == 401
        assert "budget_session" not in response.headers.get("set-cookie", "")

    def test_valid_password_grants_access(self, client: TestClient) -> None:
        """A logged-in client reaches a private page."""
        assert client.get("/", follow_redirects=False).status_code == 200

    def test_logout_clears_the_session(self, client: TestClient) -> None:
        """After logout the client is anonymous again."""
        client.get("/logout", follow_redirects=False)
        assert client.get("/", follow_redirects=False).status_code == 303


class TestPasswordHashing:
    """PBKDF2 hash round-trip and malformed-hash handling."""

    def test_hash_roundtrip(self) -> None:
        """A hash verifies its own password and rejects another."""
        encoded = hash_password(PASSWORD)
        assert verify_password(PASSWORD, encoded)
        assert not verify_password("other", encoded)

    def test_rejects_malformed_hash(self) -> None:
        """A malformed hash string fails verification without raising."""
        assert not verify_password("x", "not-a-valid-hash")
