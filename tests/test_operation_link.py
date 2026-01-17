"""Tests for OperationLink data model and repository operations."""

# pylint: disable=redefined-outer-name,protected-access

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from budget_forecaster.account.sqlite_repository import (
    CURRENT_SCHEMA_VERSION,
    SqliteRepository,
)
from budget_forecaster.operation_range.operation_link import LinkType, OperationLink


@pytest.fixture
def temp_db_path() -> Path:
    """Fixture that provides a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return Path(f.name)


class TestOperationLinkRepository:
    """Tests for OperationLink CRUD operations in SqliteRepository."""

    def test_get_link_for_operation_not_found(self, temp_db_path: Path) -> None:
        """Test getting a link for an operation that has no link."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        link = repository.get_link_for_operation(999)
        assert link is None

        repository.close()

    def test_create_and_get_link(self, temp_db_path: Path) -> None:
        """Test creating and retrieving a link."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        link = OperationLink(
            operation_unique_id=100,
            linked_type=LinkType.PLANNED_OPERATION,
            linked_id=1,
            iteration_date=datetime(2024, 1, 15),
            is_manual=False,
            notes=None,
        )
        repository.create_link(link)

        retrieved = repository.get_link_for_operation(100)
        assert retrieved is not None
        assert retrieved.operation_unique_id == 100
        assert retrieved.linked_type == LinkType.PLANNED_OPERATION
        assert retrieved.linked_id == 1
        assert retrieved.iteration_date == datetime(2024, 1, 15)
        assert retrieved.is_manual is False
        assert retrieved.notes is None

        repository.close()

    def test_create_link_with_notes(self, temp_db_path: Path) -> None:
        """Test creating a manual link with notes."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        link = OperationLink(
            operation_unique_id=200,
            linked_type=LinkType.BUDGET,
            linked_id=5,
            iteration_date=datetime(2024, 3, 1),
            is_manual=True,
            notes="Linked manually due to different description",
        )
        repository.create_link(link)

        retrieved = repository.get_link_for_operation(200)
        assert retrieved is not None
        assert retrieved.is_manual is True
        assert retrieved.notes == "Linked manually due to different description"

        repository.close()

    def test_create_link_duplicate_raises_error(self, temp_db_path: Path) -> None:
        """Test that creating a duplicate link raises IntegrityError."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        link1 = OperationLink(
            operation_unique_id=300,
            linked_type=LinkType.PLANNED_OPERATION,
            linked_id=1,
            iteration_date=datetime(2024, 1, 1),
        )
        repository.create_link(link1)

        # Try to create another link for the same operation
        link2 = OperationLink(
            operation_unique_id=300,
            linked_type=LinkType.BUDGET,
            linked_id=2,
            iteration_date=datetime(2024, 2, 1),
        )
        with pytest.raises(sqlite3.IntegrityError):
            repository.create_link(link2)

        repository.close()

    def test_delete_link(self, temp_db_path: Path) -> None:
        """Test deleting a link."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        link = OperationLink(
            operation_unique_id=400,
            linked_type=LinkType.PLANNED_OPERATION,
            linked_id=1,
            iteration_date=datetime(2024, 1, 1),
        )
        repository.create_link(link)

        # Verify it exists
        assert repository.get_link_for_operation(400) is not None

        # Delete and verify
        repository.delete_link(400)
        assert repository.get_link_for_operation(400) is None

        repository.close()

    def test_delete_link_nonexistent(self, temp_db_path: Path) -> None:
        """Test that deleting a non-existent link doesn't raise error."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        # Should not raise
        repository.delete_link(999)

        repository.close()

    def test_get_links_for_planned_operation(self, temp_db_path: Path) -> None:
        """Test getting all links for a planned operation."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        # Create links for different planned operations
        links = [
            OperationLink(
                operation_unique_id=501,
                linked_type=LinkType.PLANNED_OPERATION,
                linked_id=10,
                iteration_date=datetime(2024, 1, 15),
            ),
            OperationLink(
                operation_unique_id=502,
                linked_type=LinkType.PLANNED_OPERATION,
                linked_id=10,
                iteration_date=datetime(2024, 2, 15),
            ),
            OperationLink(
                operation_unique_id=503,
                linked_type=LinkType.PLANNED_OPERATION,
                linked_id=20,  # Different planned op
                iteration_date=datetime(2024, 1, 20),
            ),
            OperationLink(
                operation_unique_id=504,
                linked_type=LinkType.BUDGET,  # Budget, not planned op
                linked_id=10,
                iteration_date=datetime(2024, 1, 1),
            ),
        ]
        for link in links:
            repository.create_link(link)

        # Get links for planned operation 10
        result = repository.get_links_for_planned_operation(10)
        assert len(result) == 2
        assert result[0].operation_unique_id == 501
        assert result[1].operation_unique_id == 502

        # Get links for planned operation 20
        result = repository.get_links_for_planned_operation(20)
        assert len(result) == 1
        assert result[0].operation_unique_id == 503

        # Get links for non-existent planned operation
        result = repository.get_links_for_planned_operation(999)
        assert len(result) == 0

        repository.close()

    def test_get_links_for_budget(self, temp_db_path: Path) -> None:
        """Test getting all links for a budget."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        links = [
            OperationLink(
                operation_unique_id=601,
                linked_type=LinkType.BUDGET,
                linked_id=5,
                iteration_date=datetime(2024, 1, 1),
            ),
            OperationLink(
                operation_unique_id=602,
                linked_type=LinkType.BUDGET,
                linked_id=5,
                iteration_date=datetime(2024, 2, 1),
            ),
            OperationLink(
                operation_unique_id=603,
                linked_type=LinkType.PLANNED_OPERATION,  # Not a budget
                linked_id=5,
                iteration_date=datetime(2024, 1, 15),
            ),
        ]
        for link in links:
            repository.create_link(link)

        result = repository.get_links_for_budget(5)
        assert len(result) == 2
        assert result[0].operation_unique_id == 601
        assert result[1].operation_unique_id == 602

        repository.close()

    def test_delete_automatic_links_for_target(self, temp_db_path: Path) -> None:
        """Test deleting automatic links while preserving manual links."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        # Create mix of automatic and manual links for same target
        links = [
            OperationLink(
                operation_unique_id=701,
                linked_type=LinkType.PLANNED_OPERATION,
                linked_id=15,
                iteration_date=datetime(2024, 1, 1),
                is_manual=False,  # Automatic
            ),
            OperationLink(
                operation_unique_id=702,
                linked_type=LinkType.PLANNED_OPERATION,
                linked_id=15,
                iteration_date=datetime(2024, 2, 1),
                is_manual=True,  # Manual - should be preserved
            ),
            OperationLink(
                operation_unique_id=703,
                linked_type=LinkType.PLANNED_OPERATION,
                linked_id=15,
                iteration_date=datetime(2024, 3, 1),
                is_manual=False,  # Automatic
            ),
            OperationLink(
                operation_unique_id=704,
                linked_type=LinkType.PLANNED_OPERATION,
                linked_id=16,  # Different target
                iteration_date=datetime(2024, 1, 1),
                is_manual=False,
            ),
        ]
        for link in links:
            repository.create_link(link)

        # Delete automatic links for planned operation 15
        repository.delete_automatic_links_for_target(LinkType.PLANNED_OPERATION, 15)

        # Manual link should still exist
        assert repository.get_link_for_operation(702) is not None

        # Automatic links should be deleted
        assert repository.get_link_for_operation(701) is None
        assert repository.get_link_for_operation(703) is None

        # Link for different target should still exist
        assert repository.get_link_for_operation(704) is not None

        repository.close()

    def test_delete_automatic_links_for_budget(self, temp_db_path: Path) -> None:
        """Test deleting automatic links for a budget target."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        links = [
            OperationLink(
                operation_unique_id=801,
                linked_type=LinkType.BUDGET,
                linked_id=25,
                iteration_date=datetime(2024, 1, 1),
                is_manual=False,
            ),
            OperationLink(
                operation_unique_id=802,
                linked_type=LinkType.BUDGET,
                linked_id=25,
                iteration_date=datetime(2024, 2, 1),
                is_manual=True,
            ),
        ]
        for link in links:
            repository.create_link(link)

        repository.delete_automatic_links_for_target(LinkType.BUDGET, 25)

        # Automatic link deleted
        assert repository.get_link_for_operation(801) is None
        # Manual link preserved
        assert repository.get_link_for_operation(802) is not None

        repository.close()


class TestOperationLinkSchemaMigration:
    """Tests for schema migration v3."""

    def test_migration_v3_creates_table(self, temp_db_path: Path) -> None:
        """Test that migration v3 creates the operation_links table."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        assert repository._get_schema_version() == CURRENT_SCHEMA_VERSION

        # Verify table exists
        conn = repository._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='operation_links'"
        )
        assert cursor.fetchone() is not None

        repository.close()

    def test_migration_v3_creates_indexes(self, temp_db_path: Path) -> None:
        """Test that migration v3 creates the required indexes."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        conn = repository._get_connection()

        # Check for operation index
        cursor = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_operation_links_operation'"
        )
        assert cursor.fetchone() is not None

        # Check for target index
        cursor = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_operation_links_target'"
        )
        assert cursor.fetchone() is not None

        repository.close()

    def test_migration_v3_unique_constraint(self, temp_db_path: Path) -> None:
        """Test that the UNIQUE constraint on operation_unique_id is enforced."""
        repository = SqliteRepository(temp_db_path)
        repository.initialize()

        conn = repository._get_connection()

        # Insert first link
        conn.execute(
            """INSERT INTO operation_links
               (operation_unique_id, linked_type, linked_id, iteration_date, is_manual)
               VALUES (?, ?, ?, ?, ?)""",
            (999, "planned_operation", 1, "2024-01-01", False),
        )
        conn.commit()

        # Try to insert duplicate - should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO operation_links
                   (operation_unique_id, linked_type, linked_id, iteration_date, is_manual)
                   VALUES (?, ?, ?, ?, ?)""",
                (999, "budget", 2, "2024-02-01", False),
            )

        repository.close()
