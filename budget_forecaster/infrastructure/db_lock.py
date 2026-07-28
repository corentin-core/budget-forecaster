"""Cross-process advisory lock on the database file.

The web app and the sync command are separate processes on the same SQLite file.
A restore swaps the file, so it must not run while the sync holds the database
open, and vice versa. An in-process connection close does not guard against a
second process; both paths take this lock.
"""

import fcntl
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from budget_forecaster.exceptions import DatabaseBusyError

logger = logging.getLogger(__name__)


def _lock_path(database_path: Path) -> Path:
    """Return the lock file path sitting next to the database."""
    return database_path.with_name(f"{database_path.name}.lock")


@contextmanager
def database_lock(database_path: Path, *, blocking: bool = True) -> Iterator[None]:
    """Hold an exclusive advisory lock on the database for the block's duration.

    Released on block exit and on process death. When blocking is False and the
    lock is already held, raises DatabaseBusyError instead of waiting.
    """
    path = _lock_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
    with open(path, "w", encoding="utf-8") as handle:
        logger.debug("Acquiring database lock: %s", path)
        try:
            fcntl.flock(handle, flags)
        except BlockingIOError as e:
            raise DatabaseBusyError("Database is busy") from e
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
            logger.debug("Released database lock: %s", path)
