"""Tests for OperationLinkService."""

# pylint: disable=redefined-outer-name,protected-access,too-few-public-methods

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.account.sqlite_repository import SqliteRepository
from budget_forecaster.amount import Amount
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import LinkType, OperationLink
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
from budget_forecaster.types import Category


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


class TestLoadLinksForMatcher:
    """Tests for load_links_for_matcher method."""

    def test_returns_empty_dict_when_no_links(
        self, link_service: OperationLinkService
    ) -> None:
        """Test that an empty dict is returned when no links exist."""
        result = link_service.load_links_for_matcher(LinkType.PLANNED_OPERATION, 1)
        assert result == {}

    def test_returns_links_for_planned_operation(
        self, link_service: OperationLinkService, repository: SqliteRepository
    ) -> None:
        """Test loading links for a planned operation."""
        # Create some links
        link1 = OperationLink(
            operation_unique_id=100,
            linked_type=LinkType.PLANNED_OPERATION,
            linked_id=1,
            iteration_date=datetime(2024, 1, 1),
            is_manual=False,
        )
        link2 = OperationLink(
            operation_unique_id=200,
            linked_type=LinkType.PLANNED_OPERATION,
            linked_id=1,
            iteration_date=datetime(2024, 2, 1),
            is_manual=True,
        )
        repository.create_link(link1)
        repository.create_link(link2)

        result = link_service.load_links_for_matcher(LinkType.PLANNED_OPERATION, 1)

        assert len(result) == 2
        assert result[100] == datetime(2024, 1, 1)
        assert result[200] == datetime(2024, 2, 1)

    def test_returns_links_for_budget(
        self, link_service: OperationLinkService, repository: SqliteRepository
    ) -> None:
        """Test loading links for a budget."""
        link = OperationLink(
            operation_unique_id=300,
            linked_type=LinkType.BUDGET,
            linked_id=5,
            iteration_date=datetime(2024, 1, 1),
        )
        repository.create_link(link)

        result = link_service.load_links_for_matcher(LinkType.BUDGET, 5)

        assert len(result) == 1
        assert result[300] == datetime(2024, 1, 1)


class TestCreateMatcherWithLinks:
    """Tests for create_matcher_with_links method."""

    def test_creates_matcher_with_loaded_links(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
        monthly_rent_range: OperationRange,
    ) -> None:
        """Test that the created matcher has links loaded."""
        # Create a link
        link = OperationLink(
            operation_unique_id=100,
            linked_type=LinkType.PLANNED_OPERATION,
            linked_id=1,
            iteration_date=datetime(2024, 1, 1),
        )
        repository.create_link(link)

        matcher = link_service.create_matcher_with_links(
            monthly_rent_range,
            LinkType.PLANNED_OPERATION,
            linked_id=1,
        )

        assert 100 in matcher.operation_links
        assert matcher.operation_links[100] == datetime(2024, 1, 1)


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
            linked_type=LinkType.BUDGET,
            linked_id=99,
            iteration_date=datetime(2024, 1, 1),
            is_manual=True,
        )
        repository.create_link(existing_link)

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


class TestRecalculateLinksForTarget:
    """Tests for recalculate_links_for_target method."""

    def test_deletes_automatic_links_for_target(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
        monthly_rent_matcher: OperationMatcher,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that automatic links for the target are deleted."""
        # Create an automatic link
        auto_link = OperationLink(
            operation_unique_id=1,
            linked_type=LinkType.PLANNED_OPERATION,
            linked_id=1,
            iteration_date=datetime(2024, 1, 1),
            is_manual=False,
        )
        repository.create_link(auto_link)

        # Recalculate (should delete the old automatic link)
        link_service.recalculate_links_for_target(
            LinkType.PLANNED_OPERATION, 1, sample_operations, monthly_rent_matcher
        )

        # Verify a new link was created (iteration date might be different)
        link = repository.get_link_for_operation(1)
        assert link is not None

    def test_preserves_manual_links(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
        monthly_rent_matcher: OperationMatcher,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that manual links are preserved during recalculation."""
        # Create a manual link
        manual_link = OperationLink(
            operation_unique_id=1,
            linked_type=LinkType.PLANNED_OPERATION,
            linked_id=1,
            iteration_date=datetime(2024, 1, 15),  # Manually linked to different date
            is_manual=True,
            notes="Manually linked",
        )
        repository.create_link(manual_link)

        # Recalculate
        link_service.recalculate_links_for_target(
            LinkType.PLANNED_OPERATION, 1, sample_operations, monthly_rent_matcher
        )

        # Manual link should still exist with same values
        link = repository.get_link_for_operation(1)
        assert link is not None
        assert link.is_manual is True
        assert link.iteration_date == datetime(2024, 1, 15)
        assert link.notes == "Manually linked"

    def test_creates_new_links_after_deletion(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
        monthly_rent_matcher: OperationMatcher,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that new heuristic links are created after deletion."""
        new_links = link_service.recalculate_links_for_target(
            LinkType.PLANNED_OPERATION, 1, sample_operations, monthly_rent_matcher
        )

        # Should create links for matching operations
        assert len(new_links) == 2


class TestFindClosestIteration:
    """Tests for _find_closest_iteration method."""

    def test_finds_current_iteration(
        self, link_service: OperationLinkService, monthly_rent_range: OperationRange
    ) -> None:
        """Test finding iteration when operation is within current iteration."""
        operation = HistoricOperation(
            unique_id=1,
            description="RENT",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date=datetime(2024, 1, 15),  # Mid-January
        )

        result = link_service._find_closest_iteration(operation, monthly_rent_range)

        assert result == datetime(2024, 1, 1)

    def test_finds_closest_iteration_when_between(
        self, link_service: OperationLinkService
    ) -> None:
        """Test finding closest iteration when operation date is between iterations."""
        # Daily operation on the 1st of each month
        time_range = PeriodicDailyTimeRange(
            datetime(2024, 1, 1), relativedelta(months=1)
        )
        operation_range = OperationRange(
            description="Monthly Payment",
            amount=Amount(100.0, "EUR"),
            category=Category.OTHER,
            time_range=time_range,
        )

        # Operation on Jan 5 - closer to Jan 1 (4 days) than Feb 1 (27 days)
        operation = HistoricOperation(
            unique_id=1,
            description="Payment",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            date=datetime(2024, 1, 5),
        )

        result = link_service._find_closest_iteration(operation, operation_range)

        assert result == datetime(2024, 1, 1)


# Integration tests for ForecastService triggers


class TestForecastServiceLinkIntegration:
    """Integration tests for automatic link recalculation in ForecastService."""

    @pytest.fixture
    def populated_repository(
        self,
        repository: SqliteRepository,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> SqliteRepository:
        """Create a repository with an account and operations."""
        from budget_forecaster.account.account import Account

        # Create account with operations
        account = Account(
            name="Test Account",
            balance=1000.0,
            currency="EUR",
            balance_date=datetime(2024, 1, 1),
            operations=sample_operations,
        )
        repository.upsert_account(account)
        return repository

    def test_add_planned_operation_creates_links(
        self, populated_repository: SqliteRepository
    ) -> None:
        """Test that adding a planned operation creates heuristic links."""
        from budget_forecaster.services.forecast_service import ForecastService

        # Get the account
        accounts = populated_repository.get_all_accounts()
        assert len(accounts) == 1
        account = accounts[0]

        # Create ForecastService with injected OperationLinkService
        operation_link_service = OperationLinkService(populated_repository)
        service = ForecastService(account, populated_repository, operation_link_service)

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

        op_id = service.add_planned_operation(planned_op)

        # Check that links were created
        links = populated_repository.get_links_for_planned_operation(op_id)
        assert len(links) == 2  # Two rent operations

    def test_update_planned_operation_recalculates_links(
        self, populated_repository: SqliteRepository
    ) -> None:
        """Test that updating a planned operation recalculates links."""
        from budget_forecaster.services.forecast_service import ForecastService

        accounts = populated_repository.get_all_accounts()
        account = accounts[0]
        operation_link_service = OperationLinkService(populated_repository)
        service = ForecastService(account, populated_repository, operation_link_service)

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
        op_id = service.add_planned_operation(planned_op)

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
        service.update_planned_operation(updated_op)

        # Old links should be deleted, new ones should be created based on new criteria
        links = populated_repository.get_links_for_planned_operation(op_id)
        # With the new amount (1500), it shouldn't match the 800 operations
        assert len(links) == 0

    def test_add_budget_creates_links(
        self, populated_repository: SqliteRepository
    ) -> None:
        """Test that adding a budget creates heuristic links."""
        from budget_forecaster.services.forecast_service import ForecastService

        accounts = populated_repository.get_all_accounts()
        account = accounts[0]
        operation_link_service = OperationLinkService(populated_repository)
        service = ForecastService(account, populated_repository, operation_link_service)

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

        budget_id = service.add_budget(budget)

        # Check that a link was created for the groceries operation
        links = populated_repository.get_links_for_budget(budget_id)
        assert len(links) == 1
        assert links[0].operation_unique_id == 3  # The groceries operation


class TestManualLinkProtection:
    """Tests to ensure manual links are never overwritten by automatic processes."""

    def test_manual_link_preserved_after_recalculation(
        self,
        link_service: OperationLinkService,
        repository: SqliteRepository,
        monthly_rent_matcher: OperationMatcher,
        sample_operations: tuple[HistoricOperation, ...],
    ) -> None:
        """Test that manual links survive multiple recalculations."""
        # Create a manual link with custom iteration date and notes
        manual_link = OperationLink(
            operation_unique_id=1,
            linked_type=LinkType.PLANNED_OPERATION,
            linked_id=1,
            iteration_date=datetime(2024, 3, 1),  # Future date, not matching heuristic
            is_manual=True,
            notes="User manually linked this",
        )
        repository.create_link(manual_link)

        # Perform multiple recalculations
        for _ in range(3):
            link_service.recalculate_links_for_target(
                LinkType.PLANNED_OPERATION, 1, sample_operations, monthly_rent_matcher
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

        # Recalculate should replace the heuristic link
        link_service.recalculate_links_for_target(
            LinkType.PLANNED_OPERATION, 1, sample_operations, monthly_rent_matcher
        )

        # Link should still exist (recreated)
        final_link = repository.get_link_for_operation(1)
        assert final_link is not None
        assert final_link.is_manual is False
