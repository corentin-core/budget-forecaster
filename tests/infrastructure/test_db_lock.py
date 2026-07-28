"""Tests for the cross-process database lock."""

import fcntl
from pathlib import Path

from budget_forecaster.infrastructure.db_lock import database_lock


def _try_lock(path: Path) -> bool:
    """Attempt a non-blocking exclusive lock via a separate open file description.

    flock locks bind to the open file description, so a distinct open of the same
    file conflicts with the held lock even from the same process.
    """
    with open(path, "w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle, fcntl.LOCK_UN)
            return True
        except BlockingIOError:
            return False


class TestDatabaseLock:
    """Tests for mutual exclusion on the lock file."""

    def test_excludes_others_while_held(self, tmp_path: Path) -> None:
        """A second acquirer cannot take the lock while the block holds it."""
        db_path = tmp_path / "budget.db"
        lock_path = tmp_path / "budget.db.lock"
        with database_lock(db_path):
            assert _try_lock(lock_path) is False

    def test_released_after_block(self, tmp_path: Path) -> None:
        """The lock is free again once the block exits."""
        db_path = tmp_path / "budget.db"
        lock_path = tmp_path / "budget.db.lock"
        with database_lock(db_path):
            pass
        assert _try_lock(lock_path) is True

    def test_creates_missing_parent(self, tmp_path: Path) -> None:
        """The lock directory is created if absent."""
        db_path = tmp_path / "nested" / "budget.db"
        with database_lock(db_path):
            pass
        assert (tmp_path / "nested" / "budget.db.lock").exists()
