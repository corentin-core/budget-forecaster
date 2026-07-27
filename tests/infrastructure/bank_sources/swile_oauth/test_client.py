"""The Swile client refreshes tokens and reads operations/wallets."""

import logging
from unittest.mock import MagicMock

import pytest

from budget_forecaster.infrastructure.bank_sources.swile_oauth import constants
from budget_forecaster.infrastructure.bank_sources.swile_oauth.client import (
    _MAX_PAGES,
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


def test_get_operations_sends_auth_headers_and_pagination_params() -> None:
    """get_operations authenticates and asks for a page via before/per."""
    session = MagicMock()
    session.get.return_value = _response({"items": [{"name": "a"}], "has_more": False})

    payload = SwileClient(session).get_operations("acc-token")

    assert payload == {"items": [{"name": "a"}]}
    call = session.get.call_args
    assert call.args[0] == constants.OPERATIONS_URL
    headers = call.kwargs["headers"]
    assert headers["Authorization"] == "Bearer acc-token"
    assert headers["X-API-Key"] == constants.X_API_KEY
    assert headers["X-Lunchr-Platform"] == "web"
    assert call.kwargs["params"]["per"] == 100


def test_get_operations_follows_the_cursor_across_pages() -> None:
    """Pagination follows next_cursor and concatenates items until has_more is false."""
    session = MagicMock()
    session.get.side_effect = [
        _response({"items": [{"name": "a"}], "has_more": True, "next_cursor": "c2"}),
        _response({"items": [{"name": "b"}], "has_more": False, "next_cursor": None}),
    ]

    payload = SwileClient(session).get_operations("acc-token")

    assert payload == {"items": [{"name": "a"}, {"name": "b"}]}
    assert session.get.call_args_list[1].kwargs["params"]["before"] == "c2"


def test_get_operations_stops_on_missing_cursor() -> None:
    """A has_more page without a next_cursor ends pagination instead of crashing."""
    session = MagicMock()
    session.get.side_effect = [
        _response({"items": [{"name": "a"}], "has_more": True, "next_cursor": None}),
    ]

    payload = SwileClient(session).get_operations("acc-token")

    assert payload == {"items": [{"name": "a"}]}
    assert session.get.call_count == 1


def test_get_operations_stops_at_the_page_cap_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Pagination stops at the safety cap and warns instead of looping forever."""
    session = MagicMock()
    session.get.side_effect = [
        _response({"items": [{"name": str(i)}], "has_more": True, "next_cursor": "c"})
        for i in range(_MAX_PAGES + 5)
    ]

    with caplog.at_level(logging.WARNING):
        payload = SwileClient(session).get_operations("acc-token")

    assert len(payload["items"]) == _MAX_PAGES
    assert session.get.call_count == _MAX_PAGES
    assert "page cap" in caplog.text


def test_get_wallets_sends_the_api_version_header() -> None:
    """get_wallets hits the wallets endpoint with the X-API-Version header."""
    session = MagicMock()
    session.get.return_value = _response({"wallets": []})

    payload = SwileClient(session).get_wallets("acc-token")

    assert payload == {"wallets": []}
    call = session.get.call_args
    assert call.args[0] == constants.WALLETS_URL
    assert call.kwargs["headers"]["X-API-Version"] == "0"
