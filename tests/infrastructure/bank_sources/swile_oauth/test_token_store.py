"""The token store persists an encrypted token with owner-only perms."""

import stat
from pathlib import Path

from budget_forecaster.infrastructure.bank_sources.swile_oauth.token_store import (
    SwileTokenStore,
)

_SECRET = "web-secret-key"
_TOKEN = "opaque-refresh-token"


def _store(tmp_path: Path) -> SwileTokenStore:
    return SwileTokenStore(tmp_path / "token.json", _SECRET)


def test_load_returns_none_when_absent(tmp_path: Path) -> None:
    """Loading before any save returns None."""
    assert _store(tmp_path).load() is None


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    """A saved token is read back unchanged."""
    store = _store(tmp_path)
    store.save(_TOKEN)
    assert store.load() == _TOKEN


def test_saved_file_is_encrypted_and_owner_only(tmp_path: Path) -> None:
    """The file hides the plaintext token and is 0600."""
    store = _store(tmp_path)
    store.save(_TOKEN)
    content = store.path.read_text(encoding="utf-8")
    assert _TOKEN not in content
    assert stat.S_IMODE(store.path.stat().st_mode) == stat.S_IRUSR | stat.S_IWUSR


def test_clear_removes_the_token(tmp_path: Path) -> None:
    """Clearing leaves nothing to load."""
    store = _store(tmp_path)
    store.save(_TOKEN)
    store.clear()
    assert store.load() is None
