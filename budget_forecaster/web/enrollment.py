"""Signed cookies bridging the bank OAuth round-trip.

Enrolling a bank sends the user to the bank and back through a callback. Two
short-lived signed cookies carry state across that redirect, both apart from
the session cookie:

- the pending-enrollment cookie holds which bank is being linked plus a random
  state; the callback checks the returned state against it (CSRF guard) before
  completing.
- the flash cookie carries a one-shot outcome (linked / cancelled / error) so
  the Réglages page can show it once without a query parameter that would
  replay on refresh or back.
"""

from enum import Enum
from typing import NamedTuple

from fastapi import Request
from fastapi.responses import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

PENDING_COOKIE = "budget_enroll"
FLASH_COOKIE = "budget_flash"

_PENDING_SALT = "budget-web-enroll"
_FLASH_SALT = "budget-web-flash"
# The user authenticates at the bank in between; give them time, but not so
# long that a stale pending state lingers.
_PENDING_MAX_AGE = 60 * 15
_FLASH_MAX_AGE = 60


class Flash(str, Enum):
    """Outcome of an enrollment round-trip, shown once on return."""

    LINKED = "linked"
    CANCELLED = "cancelled"
    ERROR = "error"
    SWILE_LINKED = "swile-linked"
    SWILE_ERROR = "swile-error"


class PendingEnrollment(NamedTuple):
    """The bank being linked and the state to match on the callback."""

    state: str
    aspsp_name: str
    country: str


def make_pending_serializer(secret_key: str) -> URLSafeTimedSerializer:
    """Build the signer for the pending-enrollment cookie."""
    return URLSafeTimedSerializer(secret_key, salt=_PENDING_SALT)


def make_flash_serializer(secret_key: str) -> URLSafeTimedSerializer:
    """Build the signer for the flash cookie."""
    return URLSafeTimedSerializer(secret_key, salt=_FLASH_SALT)


def set_pending(
    response: Response,
    serializer: URLSafeTimedSerializer,
    pending: PendingEnrollment,
    *,
    secure: bool,
) -> None:
    """Store the pending enrollment in a signed cookie on the response."""
    token = serializer.dumps(list(pending))
    response.set_cookie(
        PENDING_COOKIE,
        token,
        max_age=_PENDING_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def read_pending(
    request: Request, serializer: URLSafeTimedSerializer
) -> PendingEnrollment | None:
    """Return the pending enrollment, or None when absent, expired or tampered."""
    if not (token := request.cookies.get(PENDING_COOKIE)):
        return None
    try:
        state, aspsp_name, country = serializer.loads(token, max_age=_PENDING_MAX_AGE)
    except (BadSignature, SignatureExpired, ValueError):
        return None
    return PendingEnrollment(state, aspsp_name, country)


def clear_pending(response: Response) -> None:
    """Delete the pending-enrollment cookie (call on every callback exit)."""
    response.delete_cookie(PENDING_COOKIE)


def set_flash(
    response: Response,
    serializer: URLSafeTimedSerializer,
    flash: Flash,
    *,
    secure: bool,
) -> None:
    """Store a one-shot outcome in a signed cookie on the response."""
    response.set_cookie(
        FLASH_COOKIE,
        serializer.dumps(flash.value),
        max_age=_FLASH_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def read_flash(request: Request, serializer: URLSafeTimedSerializer) -> Flash | None:
    """Return the flash outcome, or None when absent, expired or tampered."""
    if not (token := request.cookies.get(FLASH_COOKIE)):
        return None
    try:
        value = serializer.loads(token, max_age=_FLASH_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return Flash(value)
    except ValueError:
        return None


def clear_flash(response: Response) -> None:
    """Delete the flash cookie once its outcome has been rendered."""
    response.delete_cookie(FLASH_COOKIE)
