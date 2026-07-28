"""Backup service for automatic database backups."""

import logging
import os
import shutil
import sqlite3
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Callable, NamedTuple

from budget_forecaster.exceptions import BackupError
from budget_forecaster.infrastructure.db_lock import database_lock

logger = logging.getLogger(__name__)


class BackupKind(StrEnum):
    """Why a backup exists, which drives its tag and rotation counter."""

    AUTOMATIC = "automatic"  # taken at startup
    MANUAL = "manual"  # created on demand from the app
    SAFETY = "safety"  # taken just before a restore, to undo it


# Filename marker per kind; automatic backups carry none.
_MARKERS: dict[BackupKind, str] = {
    BackupKind.MANUAL: "manual",
    BackupKind.SAFETY: "prerestore",
}


class BackupInfo(NamedTuple):
    """A backup file surfaced to the UI."""

    path: Path
    timestamp: datetime
    size_bytes: int
    kind: BackupKind

    @property
    def is_safety_copy(self) -> bool:
        """Whether this is a pre-restore safety snapshot."""
        return self.kind is BackupKind.SAFETY


class BackupService:
    """Service for creating, rotating and restoring database backups."""

    TIMESTAMP_FORMAT = "%Y-%m-%d_%H%M%S"
    # Filenames carry microseconds so two backups in the same second never
    # collide (a rapid restore then undo would otherwise overwrite its own
    # safety snapshot). Parsing accepts the second-only form for older files.
    _FILENAME_TIMESTAMP_FORMAT = "%Y-%m-%d_%H%M%S_%f"

    def __init__(
        self,
        database_path: Path,
        backup_directory: Path | None = None,
        max_backups: int = 5,
        max_manual_backups: int = 5,
        max_safety_backups: int = 3,
    ) -> None:
        """Initialize the backup service.

        Args:
            database_path: Path to the SQLite database file.
            backup_directory: Directory for backups (default: same as database).
            max_backups: Maximum number of automatic backups to keep.
            max_manual_backups: Maximum number of on-demand backups to keep.
            max_safety_backups: Maximum number of pre-restore snapshots to keep.
        """
        self._database_path = database_path
        self._backup_directory = backup_directory or database_path.parent
        self._db_stem = database_path.stem
        self._caps = {
            BackupKind.AUTOMATIC: max_backups,
            BackupKind.MANUAL: max_manual_backups,
            # Always keep at least the snapshot a restore just took.
            BackupKind.SAFETY: max(1, max_safety_backups),
        }

    @property
    def backup_directory(self) -> Path:
        """Return the backup directory path."""
        return self._backup_directory

    @property
    def max_backups(self) -> int:
        """Return the maximum number of automatic backups to keep."""
        return self._caps[BackupKind.AUTOMATIC]

    def _get_backup_pattern(self) -> str:
        """Get the glob pattern for backup files."""
        return f"{self._db_stem}_*.db"

    def _classify(self, path: Path) -> BackupKind:
        """Determine a backup file's kind from its filename marker."""
        suffix = path.stem.removeprefix(f"{self._db_stem}_")
        for kind, marker in _MARKERS.items():
            if suffix.startswith(f"{marker}_"):
                return kind
        return BackupKind.AUTOMATIC

    def _parse_timestamp(self, path: Path) -> datetime:
        """Read the timestamp from a backup filename, falling back to mtime."""
        suffix = path.stem.removeprefix(f"{self._db_stem}_")
        for marker in _MARKERS.values():
            suffix = suffix.removeprefix(f"{marker}_")
        for fmt in (self._FILENAME_TIMESTAMP_FORMAT, self.TIMESTAMP_FORMAT):
            try:
                return datetime.strptime(suffix, fmt)
            except ValueError:
                continue
        return datetime.fromtimestamp(path.stat().st_mtime)

    def create_backup(self, kind: BackupKind = BackupKind.AUTOMATIC) -> Path:
        """Create a backup of the database.

        Args:
            kind: What the backup is for; drives its filename marker and which
                rotation counter it falls under.

        Returns:
            Path to the created backup file.

        Raises:
            BackupError: If the database doesn't exist or the copy fails.
        """
        if not self._database_path.exists():
            raise BackupError(f"Database file does not exist: {self._database_path}")

        try:
            self._backup_directory.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime(self._FILENAME_TIMESTAMP_FORMAT)
            marker = f"{_MARKERS[kind]}_" if kind in _MARKERS else ""
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

        Each kind rotates on its own counter, so a restore's safety snapshot
        never evicts an automatic or manual backup the user still wants.

        Returns:
            List of deleted backup file paths.
        """
        deleted: list[Path] = []
        for kind, cap in self._caps.items():
            deleted += self._rotate(self._backups_of_kind(kind), cap)
        return deleted

    def _rotate(self, backups: tuple[Path, ...], keep: int) -> tuple[Path, ...]:
        """Delete all but the newest keep backups (input sorted oldest first)."""
        deleted: list[Path] = []
        for backup in backups[:-keep] if keep else backups:
            try:
                backup.unlink()
                deleted.append(backup)
                logger.info("Deleted old backup: %s", backup)
            except OSError as e:
                logger.error("Failed to delete backup %s: %s", backup, e)
        return tuple(deleted)

    def get_existing_backups(self) -> list[Path]:
        """Get all backup files, sorted oldest first."""
        backups = list(self._backup_directory.glob(self._get_backup_pattern()))
        return sorted(backups, key=lambda p: p.stat().st_mtime)

    def _backups_of_kind(self, kind: BackupKind) -> tuple[Path, ...]:
        """Backups of one kind only, sorted oldest first."""
        return tuple(
            p for p in self.get_existing_backups() if self._classify(p) == kind
        )

    def get_backups(self) -> tuple[BackupInfo, ...]:
        """List all backups, newest first, with metadata for the UI."""
        infos = [
            BackupInfo(
                path=p,
                timestamp=self._parse_timestamp(p),
                size_bytes=p.stat().st_size,
                kind=self._classify(p),
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

    def is_safety_copy(self, filename: str) -> bool:
        """Whether a named backup is a pre-restore safety snapshot.

        Raises:
            BackupError: If the name is not a valid backup in this directory.
        """
        return self._classify(self.resolve_backup(filename)) is BackupKind.SAFETY

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

    def restore_backup(
        self,
        filename: str,
        migrate: Callable[[Path], None],
        *,
        blocking: bool = True,
        take_snapshot: bool = True,
    ) -> Path | None:
        """Restore a backup over the live database.

        Migrates a scratch copy of the chosen backup to the current schema, then
        atomically swaps it into place. Held under the cross-process database
        lock so a concurrent sync cannot write into the file being replaced. The
        caller must close its own connection before and reload after.

        Args:
            filename: Name of the backup to restore (validated).
            migrate: Callback that upgrades the given scratch file to the current
                schema; must raise on failure so no swap happens.
            blocking: When False, raise DatabaseBusyError instead of waiting if a
                sync process holds the lock.
            take_snapshot: When True, take a pre-restore safety snapshot first.
                Set False for an undo, which restores an existing snapshot and
                should not spawn another.

        Returns:
            Path to the pre-restore safety snapshot, or None when take_snapshot
            is False.

        Raises:
            BackupError: On an invalid source, a cross-device backup directory,
                a failed migration, or a failed file operation.
            DatabaseBusyError: When blocking is False and the lock is held.
        """
        source = self.resolve_backup(filename)
        self._require_same_filesystem()

        with database_lock(self._database_path, blocking=blocking):
            snapshot = self.create_backup(BackupKind.SAFETY) if take_snapshot else None
            scratch = self._backup_directory / f".restore-{self._db_stem}.tmp"
            try:
                shutil.copy2(source, scratch)
                migrate(scratch)
                os.replace(scratch, self._database_path)
            except (OSError, sqlite3.Error) as e:
                raise BackupError(f"Failed to restore backup: {filename!r}") from e
            finally:
                scratch.unlink(missing_ok=True)
            self._remove_stale_sidecars()
            if take_snapshot:
                self._rotate(
                    self._backups_of_kind(BackupKind.SAFETY),
                    self._caps[BackupKind.SAFETY],
                )
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
