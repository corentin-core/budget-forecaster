"""Persistence for the Swile refresh token.

Mirrors the Enable Banking consent store: a single token under the XDG state
directory, in a 0600 file. Unlike that store, the token is a live credential,
so it is encrypted at rest with the web secret key.
"""

import json
import os
import stat
from pathlib import Path

from budget_forecaster.infrastructure.bank_sources.swile_oauth.crypto import (
    decrypt,
    encrypt,
)

_STATE_SUBDIR = Path("budget-forecaster") / "swile_oauth"
_TOKEN_FILENAME = "token.json"
_OWNER_READ_WRITE = stat.S_IRUSR | stat.S_IWUSR


class SwileTokenStore:
    """Load and persist the encrypted Swile refresh token on disk."""

    def __init__(self, path: Path, secret_key: str) -> None:
        self._path = path
        self._secret_key = secret_key

    @classmethod
    def default(cls, secret_key: str) -> "SwileTokenStore":
        """Store under $XDG_STATE_HOME (fallback ~/.local/state)."""
        return cls(_state_dir() / _STATE_SUBDIR / _TOKEN_FILENAME, secret_key)

    @property
    def path(self) -> Path:
        """Path of the token file on disk."""
        return self._path

    def load(self) -> str | None:
        """Return the stored refresh token, or None if none has been saved."""
        if not self._path.exists():
            return None
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return decrypt(data["refresh_token"], self._secret_key)

    def save(self, refresh_token: str) -> None:
        """Persist the refresh token encrypted, restricting perms to the owner."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"refresh_token": encrypt(refresh_token, self._secret_key)}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.chmod(self._path, _OWNER_READ_WRITE)

    def clear(self) -> None:
        """Remove the stored token if present."""
        self._path.unlink(missing_ok=True)


def _state_dir() -> Path:
    """Resolve the XDG state base directory."""
    if xdg_state := os.environ.get("XDG_STATE_HOME"):
        return Path(xdg_state)
    return Path.home() / ".local" / "state"
