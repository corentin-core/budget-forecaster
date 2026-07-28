"""Backup service for automatic database backups."""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, NamedTuple

from budget_forecaster.exceptions import BackupError
from budget_forecaster.infrastructure.db_lock import database_lock

logger = logging.getLogger(__name__)

_SAFETY_MARKER = "prerestore"


class BackupInfo(NamedTuple):
    """A backup file surfaced to the UI."""

    path: Path
    timestamp: datetime
    size_bytes: int
    is_safety_copy: bool


class BackupService:
    """Service for creating, rotating and restoring database backups."""

    TIMESTAMP_FORMAT = "%Y-%m-%d_%H%M%S"

    def __init__(
        self,
        database_path: Path,
        backup_directory: Path | None = None,
        max_backups: int = 5,
        max_safety_backups: int = 3,
    ) -> None:
        """Initialize the backup service.

        Args:
            database_path: Path to the SQLite database file.
            backup_directory: Directory for backups (default: same as database).
            max_backups: Maximum number of automatic backups to keep.
            max_safety_backups: Maximum number of pre-restore snapshots to keep.
        """
        self._database_path = database_path
        self._backup_directory = backup_directory or database_path.parent
        self._max_backups = max_backups
        self._max_safety_backups = max_safety_backups
        self._db_stem = database_path.stem

    @property
    def backup_directory(self) -> Path:
        """Return the backup directory path."""
        return self._backup_directory

    @property
    def max_backups(self) -> int:
        """Return the maximum number of automatic backups to keep."""
        return self._max_backups

    def _get_backup_pattern(self) -> str:
        """Get the glob pattern for backup files."""
        return f"{self._db_stem}_*.db"

    def _is_safety_copy(self, path: Path) -> bool:
        """Whether a backup file is a pre-restore safety snapshot."""
        return path.stem.startswith(f"{self._db_stem}_{_SAFETY_MARKER}_")

    def _parse_timestamp(self, path: Path) -> datetime:
        """Read the timestamp from a backup filename, falling back to mtime."""
        suffix = path.stem.removeprefix(f"{self._db_stem}_")
        suffix = suffix.removeprefix(f"{_SAFETY_MARKER}_")
        try:
            return datetime.strptime(suffix, self.TIMESTAMP_FORMAT)
        except ValueError:
            return datetime.fromtimestamp(path.stat().st_mtime)

    def create_backup(self, safety: bool = False) -> Path:
        """Create a backup of the database.

        Args:
            safety: When True, name it as a pre-restore snapshot rotated on its
                own counter rather than mixed with automatic backups.

        Returns:
            Path to the created backup file.

        Raises:
            BackupError: If the database doesn't exist or the copy fails.
        """
        if not self._database_path.exists():
            raise BackupError(f"Database file does not exist: {self._database_path}")

        try:
            self._backup_directory.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime(self.TIMESTAMP_FORMAT)
            marker = f"{_SAFETY_MARKER}_" if safety else ""
            backup_path = (
                self._backup_directory / f"{self._db_stem}_{marker}{timestamp}.db"
            )
            shutil.copy2(self._database_path, backup_path)
            logger.info("Database backup created: %s", backup_path)
            return backup_path
        except OSError as e:
            raise BackupError("Failed to create backup") from e

    def rotate_backups(self) -> list[Path]:
        """Delete backups exceeding the per-kind caps.

        Automatic and pre-restore snapshots rotate independently, so a restore's
        safety snapshot never evicts an automatic backup the user still wants.

        Returns:
            List of deleted backup file paths.
        """
        deleted: list[Path] = []
        deleted += self._rotate(self._automatic_backups(), self._max_backups)
        deleted += self._rotate(self._safety_backups(), self._max_safety_backups)
        return deleted

    def _rotate(self, backups: list[Path], keep: int) -> list[Path]:
        """Delete all but the newest keep backups (input sorted oldest first)."""
        deleted: list[Path] = []
        for backup in backups[:-keep] if keep else backups:
            try:
                backup.unlink()
                deleted.append(backup)
                logger.info("Deleted old backup: %s", backup)
            except OSError as e:
                logger.error("Failed to delete backup %s: %s", backup, e)
        return deleted

    def get_existing_backups(self) -> list[Path]:
        """Get all backup files (automatic and safety), sorted oldest first."""
        backups = list(self._backup_directory.glob(self._get_backup_pattern()))
        return sorted(backups, key=lambda p: p.stat().st_mtime)

    def _automatic_backups(self) -> list[Path]:
        """Automatic backups only, sorted oldest first."""
        return [p for p in self.get_existing_backups() if not self._is_safety_copy(p)]

    def _safety_backups(self) -> list[Path]:
        """Pre-restore snapshots only, sorted oldest first."""
        return [p for p in self.get_existing_backups() if self._is_safety_copy(p)]

    def get_backups(self) -> tuple[BackupInfo, ...]:
        """List all backups, newest first, with metadata for the UI."""
        infos = [
            BackupInfo(
                path=p,
                timestamp=self._parse_timestamp(p),
                size_bytes=p.stat().st_size,
                is_safety_copy=self._is_safety_copy(p),
            )
            for p in self.get_existing_backups()
        ]
        return tuple(sorted(infos, key=lambda i: i.timestamp, reverse=True))

    def resolve_backup(self, filename: str) -> Path:
        """Resolve a bare filename to a backup path, rejecting anything else.

        Guards against path traversal: the name must have no directory part and
        must resolve to an existing file inside the backup directory that matches
        the backup naming pattern.

        Raises:
            BackupError: If the name is not a valid backup in this directory.
        """
        if filename != Path(filename).name:
            raise BackupError(f"Invalid backup name: {filename!r}")
        if (path := self._backup_directory / filename) not in set(
            self.get_existing_backups()
        ):
            raise BackupError(f"Unknown backup: {filename!r}")
        return path

    def delete_backup(self, filename: str) -> None:
        """Delete a single backup by filename.

        Raises:
            BackupError: If the name is not a valid backup or the delete fails.
        """
        path = self.resolve_backup(filename)
        try:
            path.unlink()
            logger.info("Deleted backup: %s", path)
        except OSError as e:
            raise BackupError(f"Failed to delete backup: {filename!r}") from e

    def restore_backup(self, filename: str, migrate: Callable[[Path], None]) -> Path:
        """Restore a backup over the live database.

        Takes a pre-restore safety snapshot, migrates a scratch copy of the
        chosen backup to the current schema, then atomically swaps it into place.
        Held under the cross-process database lock so a concurrent sync cannot
        write into the file being replaced. The caller must close its own
        connection before and reload after.

        Args:
            filename: Name of the backup to restore (validated).
            migrate: Callback that upgrades the given scratch file to the current
                schema; must raise on failure so no swap happens.

        Returns:
            Path to the pre-restore safety snapshot (restore it to undo).

        Raises:
            BackupError: On an invalid source, a cross-device backup directory,
                a failed migration, or a failed file operation.
        """
        source = self.resolve_backup(filename)
        self._require_same_filesystem()

        with database_lock(self._database_path):
            snapshot = self.create_backup(safety=True)
            scratch = self._backup_directory / f".restore-{self._db_stem}.tmp"
            try:
                shutil.copy2(source, scratch)
                migrate(scratch)
                os.replace(scratch, self._database_path)
            except OSError as e:
                raise BackupError(f"Failed to restore backup: {filename!r}") from e
            finally:
                scratch.unlink(missing_ok=True)
            self._remove_stale_sidecars()
            self._rotate(self._safety_backups(), self._max_safety_backups)
        return snapshot

    def _require_same_filesystem(self) -> None:
        """Ensure backup dir and database share a filesystem (for os.replace)."""
        if (
            self._backup_directory.stat().st_dev
            != self._database_path.parent.stat().st_dev
        ):
            raise BackupError(
                "Backup directory and database must be on the same filesystem"
            )

    def _remove_stale_sidecars(self) -> None:
        """Remove leftover WAL sidecars of the live DB (defensive; mode is delete)."""
        for suffix in ("-wal", "-shm"):
            self._database_path.with_name(self._database_path.name + suffix).unlink(
                missing_ok=True
            )
