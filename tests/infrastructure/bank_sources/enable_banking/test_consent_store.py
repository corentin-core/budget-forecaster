"""Tests for the Enable Banking consent store."""

import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest

from budget_forecaster.infrastructure.bank_sources.enable_banking.consent import (
    Consent,
)
from budget_forecaster.infrastructure.bank_sources.enable_banking.consent_store import (
    ConsentStore,
)


def _consent() -> Consent:
    """Build a sample consent."""
    return Consent(
        session_id="s1",
        account_uids=("acc-1",),
        valid_until=datetime(2026, 12, 31, tzinfo=timezone.utc),
        aspsp_name="BNP",
        aspsp_country="FR",
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )


def test_load_returns_none_when_absent(tmp_path: Path) -> None:
    """Loading with no stored file returns None."""
    store = ConsentStore(tmp_path / "consent.json")

    assert store.load() is None


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    """A saved consent reloads identically."""
    store = ConsentStore(tmp_path / "nested" / "consent.json")
    consent = _consent()

    store.save(consent)

    assert store.load() == consent


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    """Saving creates missing parent directories."""
    store = ConsentStore(tmp_path / "a" / "b" / "consent.json")

    store.save(_consent())

    assert store.path.exists()


def test_save_restricts_permissions_to_owner(tmp_path: Path) -> None:
    """The stored file is readable and writable only by its owner."""
    store = ConsentStore(tmp_path / "consent.json")

    store.save(_consent())

    mode = stat.S_IMODE(store.path.stat().st_mode)
    assert mode == stat.S_IRUSR | stat.S_IWUSR


def test_clear_removes_stored_consent(tmp_path: Path) -> None:
    """Clearing deletes the file and load returns None afterwards."""
    store = ConsentStore(tmp_path / "consent.json")
    store.save(_consent())

    store.clear()

    assert store.load() is None


def test_clear_is_a_noop_when_absent(tmp_path: Path) -> None:
    """Clearing with no stored file does not raise."""
    store = ConsentStore(tmp_path / "consent.json")

    store.clear()


def test_default_uses_xdg_state_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default store lives under $XDG_STATE_HOME when set."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    store = ConsentStore.default()

    assert store.path == (
        tmp_path / "budget-forecaster" / "enable_banking" / "consent.json"
    )


def test_default_falls_back_to_local_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without $XDG_STATE_HOME the default store lives under ~/.local/state."""
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    store = ConsentStore.default()

    assert store.path == (
        tmp_path
        / ".local"
        / "state"
        / "budget-forecaster"
        / "enable_banking"
        / "consent.json"
    )
