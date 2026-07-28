"""One-shot signed cookie for backup outcomes shown once on the settings page.

Carries a restore's undo target (the pre-restore snapshot name) or an error
message across the POST-redirect-GET, so a refresh does not replay it.
"""

from typing import NamedTuple

from fastapi import Request
from fastapi.responses import Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

BACKUP_FLASH_COOKIE = "budget_backup_flash"
_MAX_AGE = 60


class BackupFlash(NamedTuple):
    """A backup outcome: kind is 'restored' or 'error'; detail is its payload.

    For 'restored', detail is the pre-restore snapshot filename to undo to.
    For 'error', detail is a user-facing message.
    """

    kind: str
    detail: str


def set_backup_flash(
    response: Response,
    serializer: URLSafeTimedSerializer,
    flash: BackupFlash,
    *,
    secure: bool,
) -> None:
    """Store a backup outcome in a signed cookie on the response."""
    response.set_cookie(
        BACKUP_FLASH_COOKIE,
        serializer.dumps(list(flash)),
        max_age=_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def read_backup_flash(
    request: Request, serializer: URLSafeTimedSerializer
) -> BackupFlash | None:
    """Return the backup outcome, or None when absent, expired or tampered."""
    if not (token := request.cookies.get(BACKUP_FLASH_COOKIE)):
        return None
    try:
        kind, detail = serializer.loads(token, max_age=_MAX_AGE)
    except (BadSignature, SignatureExpired, ValueError):
        return None
    return BackupFlash(kind, detail)


def clear_backup_flash(response: Response) -> None:
    """Delete the backup flash cookie once its outcome has been rendered."""
    response.delete_cookie(BACKUP_FLASH_COOKIE)
