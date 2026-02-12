"""Tests for the BackupService and BackupConfig."""

import os
import time
from pathlib import Path

import pytest

from budget_forecaster.infrastructure.backup import BackupService
from budget_forecaster.infrastructure.config import BackupConfig, Config


@pytest.fixture(name="temp_db")
def temp_db_fixture(tmp_path: Path) -> Path:
    """Create a temporary database file."""
    db_path = tmp_path / "test.db"
    db_path.write_text("test database content")
    return db_path


@pytest.fixture(name="backup_dir")
def backup_dir_fixture(tmp_path: Path) -> Path:
    """Create a temporary backup directory."""
    backup_path = tmp_path / "backups"
    backup_path.mkdir()
    return backup_path


@pytest.fixture(name="service")
def service_fixture(temp_db: Path, backup_dir: Path) -> BackupService:
    """Create a BackupService with test configuration."""
    return BackupService(
        database_path=temp_db,
        backup_directory=backup_dir,
        max_backups=3,
    )


class TestBackupServiceInit:
    """Tests for BackupService initialization."""

    def test_default_backup_directory(self, temp_db: Path) -> None:
        """Backup directory defaults to database directory."""
        service = BackupService(database_path=temp_db)
        assert service.backup_directory == temp_db.parent

    def test_custom_backup_directory(self, temp_db: Path, backup_dir: Path) -> None:
        """Custom backup directory is used when provided."""
        service = BackupService(
            database_path=temp_db,
            backup_directory=backup_dir,
        )
        assert service.backup_directory == backup_dir

    def test_default_max_backups(self, temp_db: Path) -> None:
        """Default max_backups is 5."""
        service = BackupService(database_path=temp_db)
        assert service.max_backups == 5


class TestCreateBackup:
    """Tests for backup creation."""

    def test_creates_backup_file(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """Backup file is created with correct naming pattern."""
        backup_path = service.create_backup()

        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.parent == backup_dir
        assert backup_path.suffix == ".db"
        assert "test_" in backup_path.name

    def test_backup_contains_original_content(
        self, service: BackupService, temp_db: Path
    ) -> None:
        """Backup file contains the original database content."""
        backup_path = service.create_backup()

        assert backup_path is not None
        assert backup_path.read_text() == temp_db.read_text()

    def test_returns_none_when_db_missing(
        self, tmp_path: Path, backup_dir: Path
    ) -> None:
        """Returns None when database file doesn't exist."""
        missing_db = tmp_path / "missing.db"
        service = BackupService(
            database_path=missing_db,
            backup_directory=backup_dir,
        )

        result = service.create_backup()

        assert result is None

    def test_creates_backup_directory_if_missing(
        self, temp_db: Path, tmp_path: Path
    ) -> None:
        """Creates backup directory if it doesn't exist."""
        new_backup_dir = tmp_path / "new_backups"
        service = BackupService(
            database_path=temp_db,
            backup_directory=new_backup_dir,
        )

        backup_path = service.create_backup()

        assert new_backup_dir.exists()
        assert backup_path is not None
        assert backup_path.parent == new_backup_dir

    def test_multiple_backups_have_different_names(
        self, service: BackupService
    ) -> None:
        """Multiple backups have unique timestamp-based names."""
        backup1 = service.create_backup()
        time.sleep(1.1)  # Ensure different timestamp
        backup2 = service.create_backup()

        assert backup1 is not None
        assert backup2 is not None
        assert backup1.name != backup2.name


class TestRotateBackups:
    """Tests for backup rotation."""

    def test_no_deletion_when_under_limit(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """No backups deleted when count is under max_backups."""
        # Create 2 backups manually (service would use same timestamp)
        (backup_dir / "test_2025-01-17_100000.db").write_text("1")
        (backup_dir / "test_2025-01-17_100001.db").write_text("2")

        deleted = service.rotate_backups()

        assert len(deleted) == 0
        assert len(service.get_existing_backups()) == 2

    def test_deletes_oldest_when_over_limit(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """Oldest backups are deleted when count exceeds max_backups."""

        # Create 5 backups (max is 3) with explicit mtimes
        backups = []
        base_time = time.time()
        for i in range(5):
            backup = backup_dir / f"test_2025-01-17_10000{i}.db"
            backup.write_text(f"backup {i}")
            # Set explicit mtime: oldest first
            os.utime(backup, (base_time + i, base_time + i))
            backups.append(backup)

        deleted = service.rotate_backups()

        assert len(deleted) == 2
        assert len(service.get_existing_backups()) == 3
        # Oldest backups should be deleted
        assert backups[0] in deleted
        assert backups[1] in deleted

    def test_keeps_newest_backups(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """Newest backups are kept after rotation."""

        # Create 5 backups with explicit mtimes
        base_time = time.time()
        for i in range(5):
            backup = backup_dir / f"test_2025-01-17_10000{i}.db"
            backup.write_text(f"backup {i}")
            # Set explicit mtime: oldest first
            os.utime(backup, (base_time + i, base_time + i))

        service.rotate_backups()

        remaining = service.get_existing_backups()
        remaining_names = [b.name for b in remaining]

        # Should keep the 3 newest (2, 3, 4)
        assert "test_2025-01-17_100002.db" in remaining_names
        assert "test_2025-01-17_100003.db" in remaining_names
        assert "test_2025-01-17_100004.db" in remaining_names


class TestGetExistingBackups:
    """Tests for listing existing backups."""

    def test_returns_empty_list_when_no_backups(self, service: BackupService) -> None:
        """Returns empty list when no backups exist."""
        backups = service.get_existing_backups()
        assert backups == []

    def test_returns_only_matching_pattern(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """Returns only files matching the backup pattern."""
        # Create backup files
        (backup_dir / "test_2025-01-17_100000.db").write_text("backup")
        (backup_dir / "test_2025-01-17_100001.db").write_text("backup")
        # Create non-matching files
        (backup_dir / "other_2025-01-17_100000.db").write_text("other")
        (backup_dir / "test_backup.txt").write_text("text")

        backups = service.get_existing_backups()

        assert len(backups) == 2
        assert all("test_" in b.name for b in backups)

    def test_sorted_by_modification_time(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """Backups are sorted oldest first by modification time."""

        # Create backups with explicit mtimes
        backup1 = backup_dir / "test_2025-01-17_100000.db"
        backup2 = backup_dir / "test_2025-01-17_100001.db"
        backup3 = backup_dir / "test_2025-01-17_100002.db"

        base_time = time.time()
        backup1.write_text("1")
        os.utime(backup1, (base_time, base_time))
        backup2.write_text("2")
        os.utime(backup2, (base_time + 1, base_time + 1))
        backup3.write_text("3")
        os.utime(backup3, (base_time + 2, base_time + 2))

        backups = service.get_existing_backups()

        assert backups[0] == backup1  # Oldest first
        assert backups[-1] == backup3  # Newest last


class TestBackupErrorHandling:
    """Tests for error handling in backup operations."""

    def test_create_backup_returns_none_on_copy_error(
        self, temp_db: Path, tmp_path: Path
    ) -> None:
        """create_backup returns None when the copy fails (e.g. read-only dir)."""
        # Use a non-writable directory to trigger OSError
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o444)

        service = BackupService(
            database_path=temp_db,
            backup_directory=read_only_dir / "subdir",
        )

        try:
            result = service.create_backup()

            assert result is None
        finally:
            read_only_dir.chmod(0o755)

    def test_rotate_backups_continues_on_individual_delete_failure(
        self, temp_db: Path, backup_dir: Path
    ) -> None:
        """rotate_backups continues when a single file fails to delete."""
        base_time = 1000000000.0
        for i in range(5):
            backup = backup_dir / f"test_2025-01-17_10000{i}.db"
            backup.write_text(f"backup {i}")
            os.utime(backup, (base_time + i, base_time + i))

        # Make the oldest backup non-deletable
        oldest = backup_dir / "test_2025-01-17_100000.db"
        oldest.chmod(0o444)
        backup_dir.chmod(0o555)

        service = BackupService(
            database_path=temp_db,
            backup_directory=backup_dir,
            max_backups=3,
        )

        try:
            deleted = service.rotate_backups()

            # Should have attempted both deletions; some may fail
            # The important thing is that it doesn't crash
            assert isinstance(deleted, list)
        finally:
            backup_dir.chmod(0o755)
            oldest.chmod(0o644)


class TestBackupConfigParsing:
    """Tests for BackupConfig parsing from YAML."""

    def test_default_backup_config_when_section_absent(self, tmp_path: Path) -> None:
        """BackupConfig uses defaults when backup section is absent from YAML."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
database_path: test.db
account_name: Test Account
account_currency: EUR
"""
        )

        config = Config()
        config.parse(config_file)

        assert config.backup == BackupConfig()
        assert config.backup.enabled is True
        assert config.backup.max_backups == 5
        assert config.backup.directory is None

    def test_parses_full_backup_config(self, tmp_path: Path) -> None:
        """BackupConfig is parsed correctly when all fields are specified."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
database_path: test.db
account_name: Test Account
account_currency: EUR
backup:
  enabled: false
  max_backups: 10
  directory: /custom/backup/path
"""
        )

        config = Config()
        config.parse(config_file)

        assert config.backup.enabled is False
        assert config.backup.max_backups == 10
        assert config.backup.directory == Path("/custom/backup/path")

    def test_parses_partial_backup_config(self, tmp_path: Path) -> None:
        """BackupConfig uses defaults for unspecified fields."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
database_path: test.db
account_name: Test Account
account_currency: EUR
backup:
  max_backups: 3
"""
        )

        config = Config()
        config.parse(config_file)

        # Specified field
        assert config.backup.max_backups == 3
        # Default fields
        assert config.backup.enabled is True
        assert config.backup.directory is None

    def test_parses_backup_disabled(self, tmp_path: Path) -> None:
        """BackupConfig correctly parses enabled: false."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
database_path: test.db
account_name: Test Account
account_currency: EUR
backup:
  enabled: false
"""
        )

        config = Config()
        config.parse(config_file)

        assert config.backup.enabled is False
        # Other fields use defaults
        assert config.backup.max_backups == 5
        assert config.backup.directory is None
