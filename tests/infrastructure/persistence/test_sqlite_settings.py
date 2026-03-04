"""Tests for SQLite settings table (V6 migration)."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.infrastructure.persistence.sqlite_repository import (
    SqliteRepository,
)


@pytest.fixture(name="temp_db_path")
def temp_db_path_fixture(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture(name="repository")
def repository_fixture(temp_db_path: Path) -> Iterator[RepositoryInterface]:
    """Create an initialized repository."""
    with SqliteRepository(temp_db_path) as repo:
        yield repo


class TestSettingsTable:
    """Tests for the settings key-value table."""

    def test_get_default_margin_threshold(
        self, repository: RepositoryInterface
    ) -> None:
        """The margin_threshold default is '0' after migration."""
        assert repository.get_setting("margin_threshold") == "0"

    def test_get_nonexistent_key_returns_none(
        self, repository: RepositoryInterface
    ) -> None:
        """Getting a nonexistent key returns None."""
        assert repository.get_setting("nonexistent") is None

    def test_set_and_get_setting(self, repository: RepositoryInterface) -> None:
        """Set a setting value and retrieve it."""
        repository.set_setting("margin_threshold", "500")
        assert repository.get_setting("margin_threshold") == "500"

    def test_set_overwrites_existing(self, repository: RepositoryInterface) -> None:
        """Setting a key that already exists overwrites the value."""
        repository.set_setting("margin_threshold", "100")
        repository.set_setting("margin_threshold", "200")
        assert repository.get_setting("margin_threshold") == "200"

    def test_set_new_key(self, repository: RepositoryInterface) -> None:
        """Setting a new key inserts it."""
        repository.set_setting("custom_key", "custom_value")
        assert repository.get_setting("custom_key") == "custom_value"


class TestV6Migration:
    """Tests for V5 -> V6 migration."""

    def test_migration_creates_settings_table(self, temp_db_path: Path) -> None:
        """V6 migration creates the settings table with default values."""
        with SqliteRepository(temp_db_path) as repo:
            # After initialization, the settings table should exist
            # and have the default margin_threshold
            assert repo.get_setting("margin_threshold") == "0"

    def test_migration_idempotent(self, temp_db_path: Path) -> None:
        """Re-initializing an already-migrated DB does not fail."""
        with SqliteRepository(temp_db_path) as repo:
            repo.set_setting("margin_threshold", "500")

        # Re-open: should not re-run migration, value should persist
        with SqliteRepository(temp_db_path) as repo:
            assert repo.get_setting("margin_threshold") == "500"
