"""Backup service for automatic database backups."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupService:
    """Service for creating and rotating database backups."""

    TIMESTAMP_FORMAT = "%Y-%m-%d_%H%M%S"

    def __init__(
        self,
        database_path: Path,
        backup_directory: Path | None = None,
        max_backups: int = 5,
    ) -> None:
        """Initialize the backup service.

        Args:
            database_path: Path to the SQLite database file.
            backup_directory: Directory for backups (default: same as database).
            max_backups: Maximum number of backups to keep.
        """
        self._database_path = database_path
        self._backup_directory = backup_directory or database_path.parent
        self._max_backups = max_backups
        self._db_stem = database_path.stem

    def _get_backup_pattern(self) -> str:
        """Get the glob pattern for backup files."""
        return f"{self._db_stem}_*.db"

    def create_backup(self) -> Path | None:
        """Create a backup of the database.

        Returns:
            Path to the created backup file, or None if database doesn't exist.
        """
        if not self._database_path.exists():
            logger.info(
                "Database file does not exist, skipping backup: %s",
                self._database_path,
            )
            return None

        try:
            # Create backup directory if needed
            self._backup_directory.mkdir(parents=True, exist_ok=True)

            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime(self.TIMESTAMP_FORMAT)
            backup_filename = f"{self._db_stem}_{timestamp}.db"
            backup_path = self._backup_directory / backup_filename

            # Copy the database file
            shutil.copy2(self._database_path, backup_path)
            logger.info("Database backup created: %s", backup_path)

            return backup_path

        except OSError as e:
            logger.error("Failed to create backup: %s", e)
            return None

    def rotate_backups(self) -> list[Path]:
        """Delete old backups exceeding max_backups.

        Returns:
            List of deleted backup file paths.
        """
        deleted: list[Path] = []

        try:
            backups = self.get_existing_backups()

            if len(backups) <= self._max_backups:
                return deleted

            # Delete oldest backups (list is sorted oldest first)
            to_delete = backups[: -self._max_backups]

            for backup in to_delete:
                try:
                    backup.unlink()
                    deleted.append(backup)
                    logger.info("Deleted old backup: %s", backup)
                except OSError as e:
                    logger.error("Failed to delete backup %s: %s", backup, e)

        except OSError as e:
            logger.error("Failed to rotate backups: %s", e)

        return deleted

    def get_existing_backups(self) -> list[Path]:
        """Get list of existing backup files sorted by modification time.

        Returns:
            List of backup file paths, sorted oldest first.
        """
        pattern = self._get_backup_pattern()
        backups = list(self._backup_directory.glob(pattern))
        return sorted(backups, key=lambda p: p.stat().st_mtime)
