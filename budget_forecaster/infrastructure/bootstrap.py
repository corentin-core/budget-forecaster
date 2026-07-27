"""Shared database bootstrap for the web app and CLI entry points.

Backs up the database, runs migrations, and seeds the aggregated account name
on an empty database. Both entry points open the repository the same way.
"""

import logging

from budget_forecaster.exceptions import BackupError
from budget_forecaster.infrastructure.backup import BackupService
from budget_forecaster.infrastructure.config import Config
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)

logger = logging.getLogger(__name__)


def open_repository(config: Config) -> SqliteRepository:
    """Back up, migrate and return the repository ready to use."""
    if config.backup.enabled:
        backup_service = BackupService(
            database_path=config.database_path,
            backup_directory=config.backup.directory,
            max_backups=config.backup.max_backups,
        )
        try:
            backup_path = backup_service.create_backup()
            logger.info("Database backup created: %s", backup_path)
        except BackupError:
            logger.exception("Backup failed")
        backup_service.rotate_backups()

    repository = SqliteRepository(config.database_path)
    repository.initialize()

    if repository.get_aggregated_account_name() is None:
        logger.info("Empty database detected, initializing aggregated account")
        repository.set_aggregated_account_name(config.account.name)

    return repository
