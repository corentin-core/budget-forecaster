"""Shared-password authentication: password hashing, signed session cookie,
middleware and the login/logout routes.

The tailnet is the primary trust boundary; this password is defense-in-depth.
"""

import base64
import binascii
import hashlib
import hmac
import os

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.middleware.base import RequestResponseEndpoint

SESSION_COOKIE = "budget_session"
_SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
_SESSION_SALT = "budget-web-session"
_SESSION_VALUE = "authenticated"

_PBKDF2_ALGO = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 480_000

_PUBLIC_PATHS = frozenset({"/login", "/health"})
_STATIC_PREFIX = "/static/"


def hash_password(
    password: str, *, salt: bytes | None = None, iterations: int = _PBKDF2_ITERATIONS
) -> str:
    """Return a self-describing PBKDF2 hash: algo$iterations$salt$digest."""
    salt = os.urandom(16) if salt is None else salt
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return (
        f"{_PBKDF2_ALGO}${iterations}"
        f"${base64.b64encode(salt).decode()}"
        f"${base64.b64encode(digest).decode()}"
    )


def verify_password(password: str, encoded: str) -> bool:
    """Check a password against a hash produced by hash_password.

    Any malformed hash string is rejected rather than raising.
    """
    try:
        algo, iterations, salt_b64, digest_b64 = encoded.split("$")
        if algo != _PBKDF2_ALGO:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    except (ValueError, binascii.Error):
        return False
    return hmac.compare_digest(digest, expected)


def make_serializer(secret_key: str) -> URLSafeTimedSerializer:
    """Build the signer for session cookies."""
    return URLSafeTimedSerializer(secret_key, salt=_SESSION_SALT)


def issue_session(serializer: URLSafeTimedSerializer) -> str:
    """Return a fresh signed session token."""
    return serializer.dumps(_SESSION_VALUE)


def is_valid_session(serializer: URLSafeTimedSerializer, token: str) -> bool:
    """Check a session token's signature and age."""
    try:
        value = serializer.loads(token, max_age=_SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return value == _SESSION_VALUE


def _is_public(path: str) -> bool:
    """Public paths need no session: login, health, and the static mount.

    Exact matches (not prefixes) so a future /login-history stays protected.
    """
    return path in _PUBLIC_PATHS or path.startswith(_STATIC_PREFIX)


async def require_session(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Redirect unauthenticated requests to /login, except for public paths."""
    if _is_public(request.url.path):
        return await call_next(request)
    serializer: URLSafeTimedSerializer = request.app.state.serializer
    token = request.cookies.get(SESSION_COOKIE)
    if token and is_valid_session(serializer, token):
        return await call_next(request)
    return RedirectResponse(url="/login", status_code=303)


router = APIRouter()


def _render_login(request: Request, *, error: bool, status_code: int = 200) -> Response:
    """Render the standalone login page.

    Bypasses render_template: the login shell has no nav or banners, and this
    page is pre-auth, so it must not touch the account database.
    """
    return request.app.state.templates.TemplateResponse(
        request, "login.html", {"error": error}, status_code=status_code
    )


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, error: bool = False) -> Response:
    """Render the login form."""
    return _render_login(request, error=error)


@router.post("/login")
def login_submit(request: Request, password: str = Form("")) -> Response:
    """Verify the shared password and start a session on success."""
    password_hash: str = request.app.state.web_secrets.password_hash
    if not verify_password(password, password_hash):
        return _render_login(request, error=True, status_code=401)
    token = issue_session(request.app.state.serializer)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.app.state.web_secrets.secure_cookies,
    )
    return response


@router.get("/logout")
def logout() -> Response:
    """Clear the session and return to the login form."""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response
