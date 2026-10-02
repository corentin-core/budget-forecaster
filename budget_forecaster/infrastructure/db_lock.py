"""Cross-process advisory locks on the database file.

Two locks, each in its own file next to the database:

- The database lock guards the file itself. A restore swaps the file, so it must
  not run while another process holds the database open, and vice versa.
- The writer lock makes the web app the only process that writes. Every write
  starts from the accounts held in memory, so a second writer would save over
  changes it never loaded. The web app holds it for its lifetime; the sync
  command takes it too and refuses to run while the web app is up.
"""

import fcntl
import logging
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Iterator

from budget_forecaster.exceptions import DatabaseBusyError

logger = logging.getLogger(__name__)


def _lock_path(database_path: Path, suffix: str) -> Path:
    """Return the lock file path sitting next to the database."""
    return database_path.with_name(f"{database_path.name}.{suffix}")


@contextmanager
def _exclusive_lock(path: Path, *, blocking: bool) -> Iterator[None]:
    """Hold an exclusive advisory lock on path for the block's duration.

    Released on block exit and on process death. When blocking is False and the
    lock is already held, raises DatabaseBusyError instead of waiting.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
    with open(path, "w", encoding="utf-8") as handle:
        logger.debug("Acquiring lock: %s", path)
        try:
            fcntl.flock(handle, flags)
        except BlockingIOError as e:
            raise DatabaseBusyError("Database is busy") from e
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
            logger.debug("Released lock: %s", path)


def database_lock(
    database_path: Path, *, blocking: bool = True
) -> AbstractContextManager[None]:
    """Hold the lock that keeps the database file from being swapped."""
    return _exclusive_lock(_lock_path(database_path, "lock"), blocking=blocking)


def writer_lock(
    database_path: Path, *, blocking: bool = True
) -> AbstractContextManager[None]:
    """Hold the lock that makes the holder the only process writing the database."""
    return _exclusive_lock(_lock_path(database_path, "writer.lock"), blocking=blocking)
