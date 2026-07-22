"""Persistence for the Enable Banking consent.

The consent lives outside the repository, under the XDG state directory, in a
file readable only by the user. A single consent is stored at a time.
"""

import json
import os
import stat
from pathlib import Path

from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    Consent,
)

_STATE_SUBDIR = Path("budget-forecaster") / "enable_banking"
_CONSENT_FILENAME = "consent.json"
_OWNER_READ_WRITE = stat.S_IRUSR | stat.S_IWUSR


class ConsentStore:
    """Load and persist the current consent as JSON on disk."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @classmethod
    def default(cls) -> "ConsentStore":
        """Store under $XDG_STATE_HOME (fallback ~/.local/state)."""
        return cls(_state_dir() / _STATE_SUBDIR / _CONSENT_FILENAME)

    @property
    def path(self) -> Path:
        """Path of the consent file on disk."""
        return self._path

    def load(self) -> Consent | None:
        """Return the stored consent, or None if none has been saved."""
        if not self._path.exists():
            return None
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return Consent.from_dict(data)

    def save(self, consent: Consent) -> None:
        """Persist the consent, creating the directory and restricting perms."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(consent.to_dict(), indent=2), encoding="utf-8")
        os.chmod(self._path, _OWNER_READ_WRITE)

    def clear(self) -> None:
        """Remove the stored consent if present."""
        self._path.unlink(missing_ok=True)


def _state_dir() -> Path:
    """Resolve the XDG state base directory."""
    if xdg_state := os.environ.get("XDG_STATE_HOME"):
        return Path(xdg_state)
    return Path.home() / ".local" / "state"
