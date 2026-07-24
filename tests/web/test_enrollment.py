"""Signed enrollment cookies: round-trips, tamper and cross-cookie rejection."""

import itsdangerous.timed
import pytest
from starlette.requests import Request

from budget_forecaster.web.enrollment import (
    Flash,
    PendingEnrollment,
    make_flash_serializer,
    make_pending_serializer,
    read_flash,
    read_pending,
)

_SECRET = "unit-test-secret"


def _request_with_cookie(name: str, value: str) -> Request:
    """A bare GET request carrying a single cookie."""
    header = f"{name}={value}".encode()
    return Request({"type": "http", "headers": [(b"cookie", header)]})


class TestPendingCookie:
    """The pending-enrollment cookie survives a round-trip but not tampering."""

    def test_round_trip(self) -> None:
        """A signed pending cookie decodes back to the same value."""
        serializer = make_pending_serializer(_SECRET)
        pending = PendingEnrollment("state-abc", "BNP Paribas", "FR")
        request = _request_with_cookie("budget_enroll", serializer.dumps(list(pending)))
        assert read_pending(request, serializer) == pending

    def test_missing_cookie_is_none(self) -> None:
        """No cookie reads as no pending enrollment."""
        serializer = make_pending_serializer(_SECRET)
        assert (
            read_pending(Request({"type": "http", "headers": []}), serializer) is None
        )

    def test_tampered_token_is_rejected(self) -> None:
        """A modified token fails the signature check."""
        serializer = make_pending_serializer(_SECRET)
        token = serializer.dumps(["state", "BNP", "FR"])
        request = _request_with_cookie("budget_enroll", token + "x")
        assert read_pending(request, serializer) is None

    def test_other_secret_is_rejected(self) -> None:
        """A token signed with a different secret is rejected."""
        token = make_pending_serializer("attacker").dumps(["state", "BNP", "FR"])
        request = _request_with_cookie("budget_enroll", token)
        assert read_pending(request, make_pending_serializer(_SECRET)) is None

    def test_expired_cookie_is_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A cookie older than its max age decodes to None."""
        serializer = make_pending_serializer(_SECRET)
        monkeypatch.setattr(itsdangerous.timed.time, "time", lambda: 1000.0)
        token = serializer.dumps(["state", "BNP", "FR"])
        monkeypatch.undo()  # read back at the real (much later) time
        request = _request_with_cookie("budget_enroll", token)
        assert read_pending(request, serializer) is None


class TestFlashCookie:
    """The flash cookie decodes to a known outcome or nothing."""

    @pytest.mark.parametrize("flash", list(Flash), ids=lambda f: f.value)
    def test_round_trip(self, flash: Flash) -> None:
        """Each outcome round-trips through the flash cookie."""
        serializer = make_flash_serializer(_SECRET)
        request = _request_with_cookie("budget_flash", serializer.dumps(flash.value))
        assert read_flash(request, serializer) == flash

    def test_unknown_value_is_none(self) -> None:
        """An unrecognized flash value decodes to None."""
        serializer = make_flash_serializer(_SECRET)
        request = _request_with_cookie("budget_flash", serializer.dumps("bogus"))
        assert read_flash(request, serializer) is None

    def test_flash_salt_differs_from_pending(self) -> None:
        """A pending token must not read as a flash (distinct salts)."""
        token = make_pending_serializer(_SECRET).dumps("linked")
        request = _request_with_cookie("budget_flash", token)
        assert read_flash(request, make_flash_serializer(_SECRET)) is None
