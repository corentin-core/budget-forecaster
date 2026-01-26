"""Tests for OperationLinkService."""

# pylint: disable=redefined-outer-name,protected-access,too-few-public-methods,import-outside-toplevel

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.account.sqlite_repository import SqliteRepository
from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import OperationLink
from budget_forecaster.operation_range.operation_matcher import OperationMatcher
from budget_forecaster.operation_range.operation_range import OperationRange
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.services.operation_link_service import OperationLinkService
from budget_forecaster.time_range import (
    DailyTimeRange,
    PeriodicDailyTimeRange,
    PeriodicTimeRange,
    TimeRange,
)
from budget_forecaster.types import Category, LinkType

if TYPE_CHECKING:
    from budget_forecaster.account.persistent_account import PersistentAccount
    from budget_forecaster.services.application_service import ApplicationService


@pytest.fixture
def temp_db_path() -> Path:
    """Fixture that provides a temporary database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return Path(f.name)


@pytest.fixture
def repository(temp_db_path: Path) -> SqliteRepository:
    """Fixture that provides an initialized repository."""
    repo = SqliteRepository(temp_db_path)
    repo.initialize()
    return repo


@pytest.fixture
def link_service(repository: SqliteRepository) -> OperationLinkService:
    """Fixture that provides an OperationLinkService."""
    return OperationLinkService(repository)


@pytest.fixture
def monthly_rent_range() -> OperationRange:
    """Create a periodic monthly operation range for rent."""
    base_range = TimeRange(datetime(2024, 1, 1), relativedelta(months=1))
    periodic = PeriodicTimeRange(base_range, relativedelta(months=1))
    return OperationRange(
        description="Rent",
        amount=Amount(-800.0, "EUR"),  # Negative for expense
        category=Category.RENT,
        time_range=periodic,
    )


@pytest.fixture
def monthly_rent_matcher(monthly_rent_range: OperationRange) -> OperationMatcher:
    """Create a matcher for monthly rent."""
    return OperationMatcher(
        operation_range=monthly_rent_range,
        approximation_date_range=timedelta(days=5),
        approximation_amount_ratio=0.05,
    )


@pytest.fixture
def monthly_rent_planned_op() -> PlannedOperation:
    """Create a planned operation for monthly rent."""
    planned_op = PlannedOperation(
        record_id=1,
        description="Rent",
        amount=Amount(-800.0, "EUR"),
        category=Category.RENT,
        time_range=PeriodicDailyTimeRange(
            datetime(2024, 1, 1), relativedelta(months=1)
        ),
    )
    return planned_op.set_matcher_params(
        approximation_date_range=timedelta(days=5),
        approximation_amount_ratio=0.05,
    )


@pytest.fixture
def sample_operations() -> tuple[HistoricOperation, ...]:
    """Create sample historic operations."""
    return (
        HistoricOperation(
            unique_id=1,
            description="RENT TRANSFER",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date=datetime(2024, 1, 3),  # Close to Jan 1 rent
        ),
        HistoricOperation(
            unique_id=2,
            description="RENT TRANSFER",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date=datetime(2024, 2, 2),  # Close to Feb 1 rent
        ),
        HistoricOperation(
            unique_id=3,
            description="GROCERIES CARREFOUR",
            amount=Amount(-50.0, "EUR"),
            category=Category.GROCERIES,
            date=datetime(2024, 1, 15),
        ),
        HistoricOperation(
            unique_id=4,
            description="ELECTRICITY EDF",
            amount=Amount(-90.0, "EUR"),
            category=Category.ELECTRICITY,
            date=datetime(2024, 1, 20),
        ),
    )


class TestLoadLinksForTarget:
    """Tests for load_links_for_target method."""

    def test_returns_empty_tuple_when_no_links(
        self,
        link_service: OperationLinkService,
        monthly_rent_planned_op: PlannedOperation,
    ) -> None:
        """Test that an empty tuple is returned when no links exist."""
        result = link_service.load_links_for_target(monthly_rent_planned_op)
        assert result == ()

    def test_returns_links_for_planned_operation(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
        monthly_rent_planned_op: PlannedOperation,
    ) -> None:
        """Test loading links for a planned operation."""
        # Create some links
        link1 = OperationLink(
            operation_unique_id=100,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=datetime(2024, 1, 1),
            is_manual=False,
        )
        link2 = OperationLink(
            operation_unique_id=200,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=datetime(2024, 2, 1),
            is_manual=True,
        )
        repository.upsert_link(link1)
        repository.upsert_link(link2)

        result = link_service.load_links_for_target(monthly_rent_planned_op)

        assert len(result) == 2
        assert result[0].operation_unique_id == 100
        assert result[1].operation_unique_id == 200

    def test_returns_links_for_budget(
        self, link_service: OperationLinkService, repository: SqliteRepository
    ) -> None:
        """Test loading links for a budget."""
        budget = Budget(
            record_id=5,
            description="Housing Budget",
            amount=Amount(-1000.0, "EUR"),
            category=Category.RENT,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2024, 1, 1), relativedelta(months=1)),
                relativedelta(months=1),
            ),
        )
        link = OperationLink(
            operation_unique_id=300,
            target_type=LinkType.BUDGET,
            target_id=5,
            iteration_date=datetime(2024, 1, 1),
        )
        repository.upsert_link(link)

        result = link_service.load_links_for_target(budget)

        assert len(result) == 1
        assert result[0].operation_unique_id == 300


class TestCreateHeuristicLinks:
    """Tests for create_heuristic_links method."""

    def test_creates_links_for_matching_operations(
        self,
        link_service: OperationLinkService,
        monthly_rent_matcher: OperationMatcher,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that heuristic links are created for matching operations."""
        matchers = {(LinkType.PLANNED_OPERATION, 1): monthly_rent_matcher}

        created_links = link_service.create_heuristic_links(sample_operations, matchers)

        # Should create links for the two rent operations
        assert len(created_links) == 2
        linked_op_ids = {link.operation_unique_id for link in created_links}
        assert 1 in linked_op_ids
        assert 2 in linked_op_ids

    def test_skips_already_linked_operations(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
        monthly_rent_matcher: OperationMatcher,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that already linked operations are skipped."""
        # Pre-create a link for operation 1
        existing_link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.BUDGET,
            target_id=99,
            iteration_date=datetime(2024, 1, 1),
            is_manual=True,
        )
        repository.upsert_link(existing_link)

        matchers = {(LinkType.PLANNED_OPERATION, 1): monthly_rent_matcher}
        created_links = link_service.create_heuristic_links(sample_operations, matchers)

        # Should only create link for operation 2 (operation 1 is already linked)
        assert len(created_links) == 1
        assert created_links[0].operation_unique_id == 2

    def test_created_links_are_not_manual(
        self,
        link_service: OperationLinkService,
        monthly_rent_matcher: OperationMatcher,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that created links are marked as non-manual (heuristic)."""
        matchers = {(LinkType.PLANNED_OPERATION, 1): monthly_rent_matcher}

        created_links = link_service.create_heuristic_links(sample_operations, matchers)

        for link in created_links:
            assert link.is_manual is False

    def test_links_persisted_to_repository(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
        monthly_rent_matcher: OperationMatcher,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that created links are persisted to the repository."""
        matchers = {(LinkType.PLANNED_OPERATION, 1): monthly_rent_matcher}

        link_service.create_heuristic_links(sample_operations, matchers)

        # Verify links are in the repository
        link1 = repository.get_link_for_operation(1)
        link2 = repository.get_link_for_operation(2)

        assert link1 is not None
        assert link2 is not None

    def test_returns_empty_when_no_matches(
        self,
        link_service: OperationLinkService,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that no links are created when nothing matches."""
        # Matcher for a different category
        different_range = OperationRange(
            description="Salary",
            amount=Amount(3000.0, "EUR"),
            category=Category.SALARY,
            time_range=DailyTimeRange(datetime(2024, 1, 1)),
        )
        different_matcher = OperationMatcher(operation_range=different_range)
        matchers = {(LinkType.PLANNED_OPERATION, 99): different_matcher}

        created_links = link_service.create_heuristic_links(sample_operations, matchers)

        assert len(created_links) == 0


class TestDeleteLinksForTarget:
    """Tests for delete_links_for_target and delete_automatic_links_for_target."""

    def test_delete_automatic_links_for_target(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
    ) -> None:
        """Test that automatic links for the target are deleted."""
        # Create an automatic link
        auto_link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=datetime(2024, 1, 1),
            is_manual=False,
        )
        repository.upsert_link(auto_link)

        # Delete automatic links
        link_service.delete_automatic_links_for_target(LinkType.PLANNED_OPERATION, 1)

        # Verify link was deleted
        link = repository.get_link_for_operation(1)
        assert link is None

    def test_delete_automatic_links_preserves_manual(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
    ) -> None:
        """Test that manual links are preserved when deleting automatic links."""
        # Create a manual link
        manual_link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=datetime(2024, 1, 15),
            is_manual=True,
            notes="Manually linked",
        )
        repository.upsert_link(manual_link)

        # Delete automatic links
        link_service.delete_automatic_links_for_target(LinkType.PLANNED_OPERATION, 1)

        # Manual link should still exist
        link = repository.get_link_for_operation(1)
        assert link is not None
        assert link.is_manual is True
        assert link.iteration_date == datetime(2024, 1, 15)
        assert link.notes == "Manually linked"

    def test_delete_links_for_target_deletes_all(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
    ) -> None:
        """Test that delete_links_for_target deletes ALL links including manual."""
        # Create both manual and automatic links
        manual_link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=datetime(2024, 1, 15),
            is_manual=True,
        )
        auto_link = OperationLink(
            operation_unique_id=2,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=datetime(2024, 2, 1),
            is_manual=False,
        )
        repository.upsert_link(manual_link)
        repository.upsert_link(auto_link)

        # Delete ALL links for target
        link_service.delete_links_for_target(LinkType.PLANNED_OPERATION, 1)

        # Both links should be deleted
        assert repository.get_link_for_operation(1) is None
        assert repository.get_link_for_operation(2) is None


# Integration tests for ApplicationService link orchestration


class TestApplicationServiceLinkIntegration:
    """Integration tests for automatic link creation/recalculation in ApplicationService."""

    @pytest.fixture
    def populated_persistent_account(
        self,
        repository: SqliteRepository,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> PersistentAccount:
        """Create a persistent account with operations."""
        from budget_forecaster.account.account import Account
        from budget_forecaster.account.persistent_account import PersistentAccount

        # Create account with operations
        account = Account(
            name="Test Account",
            balance=1000.0,
            currency="EUR",
            balance_date=datetime(2024, 1, 1),
            operations=sample_operations,
        )
        repository.set_aggregated_account_name("Test Account")
        repository.upsert_account(account)

        persistent = PersistentAccount(repository)
        persistent.load()
        return persistent

    @pytest.fixture
    def app_service(
        self, populated_persistent_account: PersistentAccount
    ) -> ApplicationService:
        """Create ApplicationService with all dependencies."""
        from budget_forecaster.services.application_service import ApplicationService
        from budget_forecaster.services.forecast_service import ForecastService
        from budget_forecaster.services.import_service import ImportService
        from budget_forecaster.services.operation_service import OperationService

        repository = populated_persistent_account.repository
        account = populated_persistent_account.account

        operation_service = OperationService(populated_persistent_account)
        operation_link_service = OperationLinkService(repository)
        import_service = ImportService(populated_persistent_account, Path("/tmp/inbox"))
        forecast_service = ForecastService(account, repository)

        return ApplicationService(
            persistent_account=populated_persistent_account,
            import_service=import_service,
            operation_service=operation_service,
            forecast_service=forecast_service,
            operation_link_service=operation_link_service,
        )

    def test_add_planned_operation_creates_links(
        self, app_service: ApplicationService, repository: SqliteRepository
    ) -> None:
        """Test that adding a planned operation creates heuristic links."""
        # Create a planned operation that matches rent operations
        planned_op = PlannedOperation(
            record_id=None,
            description="Rent",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            time_range=PeriodicDailyTimeRange(
                datetime(2024, 1, 1), relativedelta(months=1)
            ),
        )

        new_op = app_service.add_planned_operation(planned_op)
        assert new_op.id is not None

        # Check that links were created
        links = repository.get_links_for_planned_operation(new_op.id)
        assert len(links) == 2  # Two rent operations

    def test_update_planned_operation_recalculates_links(
        self, app_service: ApplicationService, repository: SqliteRepository
    ) -> None:
        """Test that updating a planned operation recalculates links."""
        # Add initial planned operation
        planned_op = PlannedOperation(
            record_id=None,
            description="Rent",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            time_range=PeriodicDailyTimeRange(
                datetime(2024, 1, 1), relativedelta(months=1)
            ),
        )
        new_op = app_service.add_planned_operation(planned_op)
        assert new_op.id is not None
        op_id = new_op.id

        # Update with different amount (no matches expected)
        updated_op = PlannedOperation(
            record_id=op_id,
            description="Rent Updated",
            amount=Amount(-1500.0, "EUR"),  # Different amount
            category=Category.RENT,
            time_range=PeriodicDailyTimeRange(
                datetime(2024, 1, 1), relativedelta(months=1)
            ),
        )
        app_service.update_planned_operation(updated_op)

        # Old links should be deleted, new ones should be created based on new criteria
        links = repository.get_links_for_planned_operation(op_id)
        # With the new amount (1500), it shouldn't match the 800 operations
        assert len(links) == 0

    def test_add_budget_creates_links(
        self, app_service: ApplicationService, repository: SqliteRepository
    ) -> None:
        """Test that adding a budget creates heuristic links."""
        # Create a budget that matches groceries
        budget = Budget(
            record_id=None,
            description="Groceries Budget",
            amount=Amount(-50.0, "EUR"),
            category=Category.GROCERIES,
            time_range=PeriodicTimeRange(
                TimeRange(datetime(2024, 1, 1), relativedelta(months=1)),
                relativedelta(months=1),
            ),
        )

        new_budget = app_service.add_budget(budget)
        assert new_budget.id is not None

        # Check that a link was created for the groceries operation
        links = repository.get_links_for_budget(new_budget.id)
        assert len(links) == 1
        assert links[0].operation_unique_id == 3  # The groceries operation


class TestManualLinkProtection:
    """Tests to ensure manual links are never overwritten by automatic processes."""

    def test_manual_link_preserved_after_delete_automatic(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
        monthly_rent_matcher: OperationMatcher,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that manual links survive delete_automatic_links_for_target."""
        # Create a manual link with custom iteration date and notes
        manual_link = OperationLink(
            operation_unique_id=1,
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
            iteration_date=datetime(2024, 3, 1),  # Future date, not matching heuristic
            is_manual=True,
            notes="User manually linked this",
        )
        repository.upsert_link(manual_link)

        # Delete automatic links multiple times
        for _ in range(3):
            link_service.delete_automatic_links_for_target(
                LinkType.PLANNED_OPERATION, 1
            )
            # Create new heuristic links (simulating recalculation)
            link_service.create_heuristic_links(
                sample_operations,
                {(LinkType.PLANNED_OPERATION, 1): monthly_rent_matcher},
            )

        # Manual link should still exist with original values
        link = repository.get_link_for_operation(1)
        assert link is not None
        assert link.is_manual is True
        assert link.iteration_date == datetime(2024, 3, 1)
        assert link.notes == "User manually linked this"

    def test_heuristic_link_can_be_replaced(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
        monthly_rent_matcher: OperationMatcher,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that heuristic links can be replaced during recalculation."""
        # First create heuristic links
        link_service.create_heuristic_links(
            sample_operations,
            {(LinkType.PLANNED_OPERATION, 1): monthly_rent_matcher},
        )

        initial_link = repository.get_link_for_operation(1)
        assert initial_link is not None
        assert initial_link.is_manual is False

        # Delete and recreate (simulating recalculation)
        link_service.delete_automatic_links_for_target(LinkType.PLANNED_OPERATION, 1)
        link_service.create_heuristic_links(
            sample_operations,
            {(LinkType.PLANNED_OPERATION, 1): monthly_rent_matcher},
        )

        # Link should still exist (recreated)
        final_link = repository.get_link_for_operation(1)
        assert final_link is not None
        assert final_link.is_manual is False
