"""The Swile client refreshes tokens and reads operations/wallets."""

from unittest.mock import MagicMock

from budget_forecaster.infrastructure.bank_sources.swile_oauth import constants
from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import (
    SwileClient,
    TokenBundle,
)


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    return response


def test_refresh_posts_grant_and_returns_bundle() -> None:
    """Refresh posts the grant body and returns the token bundle."""
    session = MagicMock()
    session.post.return_value = _response(
        {"access_token": "acc", "refresh_token": "new-rt", "expires_in": 1800}
    )

    bundle = SwileClient(session).refresh("old-rt")

    assert bundle == TokenBundle("acc", "new-rt", 1800)
    call = session.post.call_args
    assert call.args[0] == constants.TOKEN_URL
    assert call.kwargs["json"] == {
        "grant_type": "refresh_token",
        "client_id": constants.CLIENT_ID,
        "refresh_token": "old-rt",
    }


def test_get_operations_sends_bearer_and_api_key() -> None:
    """get_operations authenticates with the bearer token and API key."""
    session = MagicMock()
    session.get.return_value = _response({"items": []})

    payload = SwileClient(session).get_operations("acc-token")

    assert payload == {"items": []}
    call = session.get.call_args
    assert call.args[0] == constants.OPERATIONS_URL
    assert call.kwargs["headers"]["Authorization"] == "Bearer acc-token"
    assert call.kwargs["headers"]["X-API-Key"] == constants.X_API_KEY


def test_get_wallets_hits_the_wallets_endpoint() -> None:
    """get_wallets calls the wallets endpoint."""
    session = MagicMock()
    session.get.return_value = _response({"wallets": []})

    payload = SwileClient(session).get_wallets("acc-token")

    assert payload == {"wallets": []}
    assert session.get.call_args.args[0] == constants.WALLETS_URL
