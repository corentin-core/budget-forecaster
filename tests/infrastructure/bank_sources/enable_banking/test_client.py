"""Tests for the Enable Banking HTTP client."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from budget_forecaster.infrastructure.bank_sources.enable_banking.client import (
    EnableBankingClient,
)

_APPLICATION_ID = "app-1234"
_REDIRECT_URL = "https://localhost:8080/callback"


@pytest.fixture(name="rsa_key")
def rsa_key_fixture() -> rsa.RSAPrivateKey:
    """Generate an RSA private key for signing test tokens."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(name="key_path")
def key_path_fixture(tmp_path: Path, rsa_key: rsa.RSAPrivateKey) -> Path:
    """Write the private key to disk and return its path."""
    key_path = tmp_path / "private_key.pem"
    key_path.write_bytes(
        rsa_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return key_path


def _response(payload: dict) -> MagicMock:
    """Build a mock HTTP response returning the given JSON payload."""
    response = MagicMock()
    response.json.return_value = payload
    return response


def _client(key_path: Path, session: MagicMock) -> EnableBankingClient:
    """Build a client backed by the written key and a mock session."""
    return EnableBankingClient(
        application_id=_APPLICATION_ID,
        private_key_path=key_path,
        redirect_url=_REDIRECT_URL,
        session=session,
    )


def test_jwt_carries_kid_and_claims(rsa_key: rsa.RSAPrivateKey, key_path: Path) -> None:
    """The token header carries the application id and valid claims."""
    client = _client(key_path, MagicMock())

    token = client._build_jwt()  # pylint: disable=protected-access

    assert jwt.get_unverified_header(token)["kid"] == _APPLICATION_ID
    public_key = rsa_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    claims = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience="api.enablebanking.com",
    )
    assert claims["iss"] == "enablebanking.com"
    assert claims["exp"] > claims["iat"]


class TestEndpoints:
    """Tests for the API endpoint calls."""

    def test_list_aspsps(self, key_path: Path) -> None:
        """Lists ASPSPs for a country with an authenticated GET."""
        session = MagicMock()
        session.request.return_value = _response(
            {"aspsps": [{"name": "BNP", "country": "FR"}]}
        )
        client = _client(key_path, session)

        aspsps = client.list_aspsps(country="FR")

        assert aspsps == [{"name": "BNP", "country": "FR"}]
        call = session.request.call_args
        assert call.args[0] == "GET"
        assert call.args[1].endswith("/aspsps")
        assert call.kwargs["params"] == {"country": "FR"}
        assert call.kwargs["headers"]["Authorization"].startswith("Bearer ")

    def test_start_authorization_returns_redirect_url(self, key_path: Path) -> None:
        """Posts the authorization request and returns the bank redirect URL."""
        session = MagicMock()
        session.request.return_value = _response(
            {"url": "https://bank.example/consent"}
        )
        client = _client(key_path, session)

        url = client.start_authorization(
            aspsp_name="BNP",
            country="FR",
            valid_until="2026-10-19T00:00:00Z",
            state="state-1",
        )

        assert url == "https://bank.example/consent"
        body = session.request.call_args.kwargs["json"]
        assert body["aspsp"] == {"name": "BNP", "country": "FR"}
        assert body["redirect_url"] == _REDIRECT_URL
        assert body["access"] == {"valid_until": "2026-10-19T00:00:00Z"}

    def test_create_session(self, key_path: Path) -> None:
        """Exchanges the authorization code and returns the session payload."""
        session = MagicMock()
        session.request.return_value = _response(
            {"session_id": "s1", "accounts": [{"uid": "acc-1"}]}
        )
        client = _client(key_path, session)

        result = client.create_session(code="auth-code")

        assert result == {"session_id": "s1", "accounts": [{"uid": "acc-1"}]}
        assert session.request.call_args.kwargs["json"] == {"code": "auth-code"}

    def test_get_transactions_follows_pagination(self, key_path: Path) -> None:
        """Follows the continuation key across pages and concatenates results."""
        session = MagicMock()
        session.request.side_effect = [
            _response(
                {"transactions": [{"entry_reference": "a"}], "continuation_key": "k1"}
            ),
            _response({"transactions": [{"entry_reference": "b"}]}),
        ]
        client = _client(key_path, session)

        transactions = client.get_transactions("acc-1", date_from=date(2026, 1, 1))

        assert transactions == [{"entry_reference": "a"}, {"entry_reference": "b"}]
        first, second = session.request.call_args_list
        assert first.kwargs["params"] == {"date_from": "2026-01-01"}
        assert second.kwargs["params"] == {
            "date_from": "2026-01-01",
            "continuation_key": "k1",
        }

    def test_get_balances(self, key_path: Path) -> None:
        """Reads the balances of an account."""
        session = MagicMock()
        session.request.return_value = _response(
            {"balances": [{"balance_type": "CLBD"}]}
        )
        client = _client(key_path, session)

        balances = client.get_balances("acc-1")

        assert balances == [{"balance_type": "CLBD"}]
        assert session.request.call_args.args[1].endswith("/accounts/acc-1/balances")
