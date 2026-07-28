"""Tests for the BackupService and BackupConfig."""

import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pytest

from budget_forecaster.exceptions import BackupError
from budget_forecaster.infrastructure.backup import BackupInfo, BackupService
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

        assert backup_path.exists()
        assert backup_path.parent == backup_dir
        assert backup_path.suffix == ".db"
        assert "test_" in backup_path.name

    def test_backup_contains_original_content(
        self, service: BackupService, temp_db: Path
    ) -> None:
        """Backup file contains the original database content."""
        backup_path = service.create_backup()

        assert backup_path.read_text() == temp_db.read_text()

    def test_raises_when_db_missing(self, tmp_path: Path, backup_dir: Path) -> None:
        """Raises BackupError when database file doesn't exist."""
        missing_db = tmp_path / "missing.db"
        service = BackupService(
            database_path=missing_db,
            backup_directory=backup_dir,
        )

        with pytest.raises(BackupError, match="does not exist"):
            service.create_backup()

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
        assert backup_path.parent == new_backup_dir

    def test_multiple_backups_have_different_names(
        self, service: BackupService
    ) -> None:
        """Multiple backups have unique timestamp-based names."""
        backup1 = service.create_backup()
        time.sleep(1.1)  # Ensure different timestamp
        backup2 = service.create_backup()

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

    def test_create_backup_raises_on_copy_error(
        self, temp_db: Path, tmp_path: Path
    ) -> None:
        """create_backup raises BackupError when the copy fails."""
        # Use a non-writable directory to trigger OSError
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        read_only_dir.chmod(0o444)

        service = BackupService(
            database_path=temp_db,
            backup_directory=read_only_dir / "subdir",
        )

        try:
            with pytest.raises(BackupError, match="Failed to create backup"):
                service.create_backup()
        finally:
            read_only_dir.chmod(0o755)

    def test_rotate_backups_continues_on_individual_delete_failure(
        self, temp_db: Path, backup_dir: Path
    ) -> None:
        """rotate_backups deletes the rest when one entry cannot be removed."""
        base_time = 1000000000.0
        # The oldest entry is a directory: unlinking it fails, so rotation must
        # still delete the other over-limit backup.
        oldest = backup_dir / "test_2025-01-17_100000.db"
        oldest.mkdir()
        os.utime(oldest, (base_time, base_time))
        for i in range(1, 5):
            backup = backup_dir / f"test_2025-01-17_10000{i}.db"
            backup.write_text(f"backup {i}")
            os.utime(backup, (base_time + i, base_time + i))

        service = BackupService(
            database_path=temp_db,
            backup_directory=backup_dir,
            max_backups=3,
        )

        deleted = service.rotate_backups()

        remaining = service.get_existing_backups()
        assert oldest in remaining  # directory deletion failed, still present
        assert deleted == [backup_dir / "test_2025-01-17_100001.db"]


class TestSafetyBackups:
    """Tests for pre-restore safety snapshots and their independent rotation."""

    def test_safety_backup_uses_marker_name(self, service: BackupService) -> None:
        """A safety backup is named with the prerestore marker."""
        path = service.create_backup(safety=True)
        assert path.stem.startswith("test_prerestore_")

    def test_safety_and_automatic_rotate_independently(
        self, temp_db: Path, backup_dir: Path
    ) -> None:
        """Safety snapshots rotate on their own counter, never evicting backups."""
        service = BackupService(
            database_path=temp_db,
            backup_directory=backup_dir,
            max_backups=3,
            max_safety_backups=2,
        )
        base_time = 1_000_000_000.0
        for i in range(4):
            auto = backup_dir / f"test_2025-01-17_10000{i}.db"
            auto.write_text(f"auto {i}")
            os.utime(auto, (base_time + i, base_time + i))
            safety = backup_dir / f"test_prerestore_2025-01-17_10000{i}.db"
            safety.write_text(f"safety {i}")
            os.utime(safety, (base_time + i, base_time + i))

        deleted = service.rotate_backups()

        remaining = {p.name for p in service.get_existing_backups()}
        # 3 newest automatic kept, 2 newest safety kept
        assert len([n for n in remaining if "prerestore" in n]) == 2
        assert len([n for n in remaining if "prerestore" not in n]) == 3
        assert len(deleted) == 3


class TestGetBackups:
    """Tests for the UI-facing backup listing."""

    def test_lists_newest_first_with_metadata(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """get_backups returns metadata sorted newest first."""
        auto = backup_dir / "test_2025-01-17_100000.db"
        auto.write_text("auto")
        safety = backup_dir / "test_prerestore_2025-01-18_100000.db"
        safety.write_text("safety")

        backups = service.get_backups()

        assert [b.path for b in backups] == [safety, auto]
        assert backups[0] == BackupInfo(
            path=safety,
            timestamp=datetime(2025, 1, 18, 10, 0, 0),
            size_bytes=safety.stat().st_size,
            is_safety_copy=True,
        )
        assert backups[1].is_safety_copy is False

    def test_timestamp_falls_back_to_mtime(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """An unparseable name falls back to the file mtime."""
        odd = backup_dir / "test_manual.db"
        odd.write_text("x")
        os.utime(odd, (1_000_000_000.0, 1_000_000_000.0))

        (info,) = service.get_backups()

        assert info.timestamp == datetime.fromtimestamp(1_000_000_000.0)


class TestResolveBackup:
    """Tests for filename validation."""

    def test_resolves_existing_backup(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """A valid backup name resolves to its path."""
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("x")
        assert service.resolve_backup("test_2025-01-17_100000.db") == backup

    @pytest.mark.parametrize(
        "name",
        ["../test.db", "sub/test.db", "missing.db"],
        ids=["parent", "subdir", "unknown"],
    )
    def test_rejects_invalid_names(self, service: BackupService, name: str) -> None:
        """Path traversal and unknown names are rejected."""
        with pytest.raises(BackupError):
            service.resolve_backup(name)


class TestDeleteBackup:
    """Tests for deleting a single backup."""

    def test_deletes_named_backup(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """The named backup is removed."""
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("x")

        service.delete_backup("test_2025-01-17_100000.db")

        assert not backup.exists()

    def test_delete_allows_last_backup(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """Deleting the only remaining backup is allowed."""
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("x")

        service.delete_backup(backup.name)

        assert service.get_existing_backups() == []

    def test_rejects_unknown_backup(self, service: BackupService) -> None:
        """Deleting an unknown name raises."""
        with pytest.raises(BackupError):
            service.delete_backup("nope.db")


class TestRestoreBackup:
    """Tests for restoring a backup over the live database."""

    def test_swaps_file_and_returns_snapshot(
        self, service: BackupService, temp_db: Path, backup_dir: Path
    ) -> None:
        """The database is replaced by the backup and a safety snapshot returned."""
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("restored content")

        snapshot = service.restore_backup(backup.name, migrate=lambda _: None)

        assert temp_db.read_text() == "restored content"
        assert snapshot is not None
        assert snapshot.stem.startswith("test_prerestore_")
        assert snapshot.read_text() == "test database content"

    def test_undo_skips_snapshot(
        self, service: BackupService, temp_db: Path, backup_dir: Path
    ) -> None:
        """An undo restores without taking a new safety snapshot."""
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("restored content")

        snapshot = service.restore_backup(
            backup.name, migrate=lambda _: None, take_snapshot=False
        )

        assert snapshot is None
        assert temp_db.read_text() == "restored content"
        assert not any(b.is_safety_copy for b in service.get_backups())

    def test_migrate_receives_scratch_copy(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """The migrate callback runs on a scratch copy before the swap."""
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("restored content")
        seen: dict[str, str] = {}

        def migrate(scratch: Path) -> None:
            seen["content"] = scratch.read_text()

        service.restore_backup(backup.name, migrate=migrate)

        assert seen["content"] == "restored content"

    def test_cleans_scratch_on_success(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """No scratch file is left behind after a restore."""
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("restored content")

        service.restore_backup(backup.name, migrate=lambda _: None)

        assert not (backup_dir / ".restore-test.tmp").exists()

    def test_failed_migration_leaves_db_untouched(
        self, service: BackupService, temp_db: Path, backup_dir: Path
    ) -> None:
        """A migration failure aborts before the swap; the live DB is unchanged."""
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("restored content")

        def failing(_: Path) -> None:
            raise BackupError("migration failed")

        with pytest.raises(BackupError):
            service.restore_backup(backup.name, migrate=failing)

        assert temp_db.read_text() == "test database content"
        assert not (backup_dir / ".restore-test.tmp").exists()

    def test_wraps_non_backup_migration_error(
        self, service: BackupService, backup_dir: Path
    ) -> None:
        """A migration error that is not a BackupError is wrapped as one."""
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("restored content")

        def failing(_: Path) -> None:
            raise sqlite3.OperationalError("no such column")

        with pytest.raises(BackupError):
            service.restore_backup(backup.name, migrate=failing)

    def test_safety_snapshots_stay_bounded_across_restores(
        self, temp_db: Path, backup_dir: Path
    ) -> None:
        """Repeated restores never grow the safety-snapshot pool past its cap."""
        service = BackupService(
            database_path=temp_db,
            backup_directory=backup_dir,
            max_safety_backups=2,
        )
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("restored content")

        for _ in range(5):
            service.restore_backup(backup.name, migrate=lambda _: None)

        safety = [b for b in service.get_backups() if b.is_safety_copy]
        assert len(safety) == 2

    def test_rejects_cross_device_backup_directory(
        self,
        service: BackupService,
        backup_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A backup directory on another filesystem is refused before any swap."""
        backup = backup_dir / "test_2025-01-17_100000.db"
        backup.write_text("restored content")

        real_stat = Path.stat

        def fake_stat(self: Path, *args: object, **kwargs: object) -> os.stat_result:
            result = real_stat(self, *args, **kwargs)
            if self == backup_dir:
                fields = list(result)
                fields[2] = result.st_dev + 1  # st_dev is index 2
                return os.stat_result(fields)
            return result

        monkeypatch.setattr(Path, "stat", fake_stat)

        with pytest.raises(BackupError, match="same filesystem"):
            service.restore_backup(backup.name, migrate=lambda _: None)


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
