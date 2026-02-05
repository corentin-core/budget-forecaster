"""Tests for the ApplicationService."""

# pylint: disable=redefined-outer-name,protected-access,too-few-public-methods
# pylint: disable=too-many-lines

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import (
    DateRange,
    RecurringDateRange,
    RecurringDay,
    SingleDay,
)
from budget_forecaster.core.types import Category, ImportStats, LinkType
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.import_service import ImportResult, ImportService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.operation.operation_matcher import OperationMatcher
from budget_forecaster.services.operation.operation_service import OperationService


@pytest.fixture
def mock_persistent_account() -> MagicMock:
    """Create a mock persistent account."""
    mock = MagicMock()
    mock.account.operations = ()
    return mock


@pytest.fixture
def mock_import_service() -> MagicMock:
    """Create a mock import service."""
    return MagicMock(spec=ImportService)


@pytest.fixture
def mock_operation_service() -> MagicMock:
    """Create a mock operation service."""
    return MagicMock(spec=OperationService)


@pytest.fixture
def mock_forecast_service() -> MagicMock:
    """Create a mock forecast service."""
    mock = MagicMock(spec=ForecastService)
    mock.get_all_planned_operations.return_value = []
    mock.get_all_budgets.return_value = []
    return mock


@pytest.fixture
def mock_operation_link_service() -> MagicMock:
    """Create a mock operation link service."""
    return MagicMock(spec=OperationLinkService)


@pytest.fixture
def app_service(
    mock_persistent_account: MagicMock,
    mock_import_service: MagicMock,
    mock_operation_service: MagicMock,
    mock_forecast_service: MagicMock,
    mock_operation_link_service: MagicMock,
) -> ApplicationService:
    """Create an ApplicationService with mock dependencies."""
    return ApplicationService(
        persistent_account=mock_persistent_account,
        import_service=mock_import_service,
        operation_service=mock_operation_service,
        forecast_service=mock_forecast_service,
        operation_link_service=mock_operation_link_service,
    )


class TestMatcherCache:
    """Tests for matcher cache management."""

    def test_builds_matchers_lazily(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
    ) -> None:
        """Matchers are built lazily on first access."""
        # Setup planned operation with matcher
        planned_op = MagicMock()
        planned_op.id = 1
        planned_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.get_all_planned_operations.return_value = [planned_op]

        # Setup budget with matcher
        budget = MagicMock()
        budget.id = 2
        budget.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.get_all_budgets.return_value = [budget]

        # Access matchers
        matchers = app_service._get_matchers()

        assert len(matchers) == 2
        assert (LinkType.PLANNED_OPERATION, 1) in matchers
        assert (LinkType.BUDGET, 2) in matchers

    def test_caches_matchers(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
    ) -> None:
        """Matchers are cached after first build."""
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        # Access twice
        app_service._get_matchers()
        app_service._get_matchers()

        # Should only be called once each
        assert mock_forecast_service.get_all_planned_operations.call_count == 1
        assert mock_forecast_service.get_all_budgets.call_count == 1


class TestImportFile:
    """Tests for import_file method."""

    def test_delegates_to_import_service(
        self,
        app_service: ApplicationService,
        mock_import_service: MagicMock,
    ) -> None:
        """import_file delegates to ImportService."""
        mock_result = ImportResult(
            path=Path("/test.xlsx"),
            success=False,
            stats=None,
            error_message="Test error",
        )
        mock_import_service.import_file.return_value = mock_result

        result = app_service.import_file(Path("/test.xlsx"))

        assert result is mock_result
        mock_import_service.import_file.assert_called_once_with(
            Path("/test.xlsx"), False
        )

    def test_creates_heuristic_links_on_success(
        self,
        app_service: ApplicationService,
        mock_import_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_persistent_account: MagicMock,
        mock_forecast_service: MagicMock,
    ) -> None:
        """import_file creates heuristic links when import succeeds."""
        # Setup successful import
        mock_result = ImportResult(
            path=Path("/test.xlsx"),
            success=True,
            stats=ImportStats(total_in_file=5, new_operations=5, duplicates_skipped=0),
        )
        mock_import_service.import_file.return_value = mock_result

        # Setup operations
        operations = (MagicMock(),)
        mock_persistent_account.account.operations = operations

        # Setup matchers
        planned_op = MagicMock()
        planned_op.id = 1
        planned_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.get_all_planned_operations.return_value = [planned_op]
        mock_forecast_service.get_all_budgets.return_value = []

        app_service.import_file(Path("/test.xlsx"))

        mock_operation_link_service.create_heuristic_links.assert_called_once()

    def test_no_links_created_on_failure(
        self,
        app_service: ApplicationService,
        mock_import_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """import_file does not create links when import fails."""
        mock_result = ImportResult(
            path=Path("/test.xlsx"),
            success=False,
            stats=None,
            error_message="Failed",
        )
        mock_import_service.import_file.return_value = mock_result

        app_service.import_file(Path("/test.xlsx"))

        mock_operation_link_service.create_heuristic_links.assert_not_called()


class TestCategorizeOperations:
    """Tests for categorize_operations method."""

    def test_returns_empty_for_nonexistent_operation(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
    ) -> None:
        """categorize_operations returns empty tuple if operation not found."""
        mock_operation_service.get_operation_by_id.return_value = None

        results = app_service.categorize_operations((999,), Category.GROCERIES)

        assert results == ()

    def test_delegates_to_operation_service(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
    ) -> None:
        """categorize_operations delegates to OperationService."""
        mock_operation = MagicMock()
        mock_operation.category = Category.OTHER
        mock_operation_service.get_operation_by_id.return_value = mock_operation

        updated_op = MagicMock()
        mock_operation_service.categorize_operation.return_value = updated_op

        results = app_service.categorize_operations((1,), Category.GROCERIES)

        assert len(results) == 1
        assert results[0].operation is updated_op
        mock_operation_service.categorize_operation.assert_called_once_with(
            1, Category.GROCERIES
        )

    def test_creates_link_when_category_changes(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_forecast_service: MagicMock,
    ) -> None:
        """categorize_operations creates link when category changes."""
        # Setup operation with different category
        mock_operation = MagicMock()
        mock_operation.category = Category.OTHER
        mock_operation_service.get_operation_by_id.return_value = mock_operation

        updated_op = MagicMock()
        updated_op.unique_id = 1
        mock_operation_service.categorize_operation.return_value = updated_op

        # No existing link
        mock_operation_link_service.get_link_for_operation.return_value = None

        # Setup matchers
        planned_op = MagicMock()
        planned_op.id = 1
        planned_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.get_all_planned_operations.return_value = [planned_op]
        mock_forecast_service.get_all_budgets.return_value = []

        # Setup link creation
        new_link = MagicMock(spec=OperationLink)
        new_link.operation_unique_id = 1
        mock_operation_link_service.create_heuristic_links.return_value = [new_link]

        results = app_service.categorize_operations((1,), Category.GROCERIES)

        assert len(results) == 1
        assert results[0].category_changed is True
        assert results[0].new_link is new_link

    def test_deletes_heuristic_link_before_recalculating(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_forecast_service: MagicMock,
    ) -> None:
        """categorize_operations deletes existing heuristic link when category changes."""
        # Setup operation with different category
        mock_operation = MagicMock()
        mock_operation.category = Category.OTHER
        mock_operation_service.get_operation_by_id.return_value = mock_operation

        updated_op = MagicMock()
        updated_op.unique_id = 1
        mock_operation_service.categorize_operation.return_value = updated_op

        # Existing heuristic link
        existing_link = MagicMock(spec=OperationLink)
        existing_link.is_manual = False
        mock_operation_link_service.get_link_for_operation.return_value = existing_link

        # Setup matchers
        planned_op = MagicMock()
        planned_op.id = 1
        planned_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.get_all_planned_operations.return_value = [planned_op]
        mock_forecast_service.get_all_budgets.return_value = []

        # Setup link creation
        new_link = MagicMock(spec=OperationLink)
        new_link.operation_unique_id = 1
        mock_operation_link_service.create_heuristic_links.return_value = [new_link]

        results = app_service.categorize_operations((1,), Category.GROCERIES)

        # Should delete existing heuristic link
        mock_operation_link_service.delete_link.assert_called_once_with(1)
        assert len(results) == 1
        assert results[0].new_link is new_link

    def test_preserves_manual_links(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_forecast_service: MagicMock,
    ) -> None:
        """categorize_operations preserves manual links when category changes."""
        # Setup operation with different category
        mock_operation = MagicMock()
        mock_operation.category = Category.OTHER
        mock_operation_service.get_operation_by_id.return_value = mock_operation

        updated_op = MagicMock()
        updated_op.unique_id = 1
        mock_operation_service.categorize_operation.return_value = updated_op

        # Existing manual link
        existing_link = MagicMock(spec=OperationLink)
        existing_link.is_manual = True
        mock_operation_link_service.get_link_for_operation.return_value = existing_link

        # Setup matchers
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        results = app_service.categorize_operations((1,), Category.GROCERIES)

        # Should NOT delete manual link
        mock_operation_link_service.delete_link.assert_not_called()
        assert len(results) == 1
        assert results[0].category_changed is True

    def test_no_link_recalculation_when_category_unchanged(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """categorize_operations skips link recalculation when category unchanged."""
        # Setup operation with same category as target
        mock_operation = MagicMock()
        mock_operation.category = Category.GROCERIES  # Same as target
        mock_operation_service.get_operation_by_id.return_value = mock_operation

        updated_op = MagicMock()
        mock_operation_service.categorize_operation.return_value = updated_op

        results = app_service.categorize_operations((1,), Category.GROCERIES)

        # Should NOT check for existing link (no recalculation)
        mock_operation_link_service.get_link_for_operation.assert_not_called()
        assert len(results) == 1
        assert results[0].category_changed is False
        assert results[0].new_link is None


class TestPlannedOperationCrud:
    """Tests for planned operation CRUD methods."""

    def test_add_planned_operation(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_persistent_account: MagicMock,
    ) -> None:
        """add_planned_operation adds operation and creates links."""
        # Create input operation
        input_op = PlannedOperation(
            record_id=None,
            description="Test",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            date_range=SingleDay(date(2025, 1, 15)),
        )

        # Setup return value with ID
        returned_op = MagicMock()
        returned_op.id = 1
        returned_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.add_planned_operation.return_value = returned_op
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        result = app_service.add_planned_operation(input_op)

        assert result is returned_op
        mock_forecast_service.add_planned_operation.assert_called_once_with(input_op)
        mock_operation_link_service.create_heuristic_links.assert_called_once()

    def test_update_planned_operation_requires_id(
        self,
        app_service: ApplicationService,
    ) -> None:
        """update_planned_operation raises error for None ID."""
        op = PlannedOperation(
            record_id=None,
            description="Test",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            date_range=SingleDay(date(2025, 1, 15)),
        )

        with pytest.raises(ValueError, match="valid ID"):
            app_service.update_planned_operation(op)

    def test_update_planned_operation_recalculates_links(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_persistent_account: MagicMock,
    ) -> None:
        """update_planned_operation deletes old links and creates new ones."""
        op = PlannedOperation(
            record_id=1,
            description="Test",
            amount=Amount(100.0, "EUR"),
            category=Category.SALARY,
            date_range=SingleDay(date(2025, 1, 15)),
        )

        returned_op = MagicMock()
        returned_op.id = 1
        returned_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.update_planned_operation.return_value = returned_op
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        app_service.update_planned_operation(op)

        mock_operation_link_service.delete_automatic_links_for_target.assert_called_once_with(
            LinkType.PLANNED_OPERATION, 1
        )
        mock_operation_link_service.create_heuristic_links.assert_called_once()

    def test_delete_planned_operation_deletes_all_links(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """delete_planned_operation deletes ALL links for target."""
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        app_service.delete_planned_operation(1)

        mock_operation_link_service.delete_links_for_target.assert_called_once_with(
            LinkType.PLANNED_OPERATION, 1
        )
        mock_forecast_service.delete_planned_operation.assert_called_once_with(1)


class TestBudgetCrud:
    """Tests for budget CRUD methods."""

    def test_add_budget(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_persistent_account: MagicMock,
    ) -> None:
        """add_budget adds budget and creates links."""
        input_budget = Budget(
            record_id=None,
            description="Test",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=DateRange(date(2025, 1, 1), relativedelta(months=1)),
        )

        returned_budget = MagicMock()
        returned_budget.id = 1
        returned_budget.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.add_budget.return_value = returned_budget
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        result = app_service.add_budget(input_budget)

        assert result is returned_budget
        mock_forecast_service.add_budget.assert_called_once_with(input_budget)
        mock_operation_link_service.create_heuristic_links.assert_called_once()

    def test_update_budget_requires_id(
        self,
        app_service: ApplicationService,
    ) -> None:
        """update_budget raises error for None ID."""
        budget = Budget(
            record_id=None,
            description="Test",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=DateRange(date(2025, 1, 1), relativedelta(months=1)),
        )

        with pytest.raises(ValueError, match="valid ID"):
            app_service.update_budget(budget)

    def test_update_budget_recalculates_links(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_persistent_account: MagicMock,
    ) -> None:
        """update_budget deletes old links and creates new ones."""
        budget = Budget(
            record_id=1,
            description="Test",
            amount=Amount(-100.0, "EUR"),
            category=Category.GROCERIES,
            date_range=DateRange(date(2025, 1, 1), relativedelta(months=1)),
        )

        returned_budget = MagicMock()
        returned_budget.id = 1
        returned_budget.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.update_budget.return_value = returned_budget
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        app_service.update_budget(budget)

        mock_operation_link_service.delete_automatic_links_for_target.assert_called_once_with(
            LinkType.BUDGET, 1
        )
        mock_operation_link_service.create_heuristic_links.assert_called_once()

    def test_delete_budget_deletes_all_links(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """delete_budget deletes ALL links for target."""
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        app_service.delete_budget(1)

        mock_operation_link_service.delete_links_for_target.assert_called_once_with(
            LinkType.BUDGET, 1
        )
        mock_forecast_service.delete_budget.assert_called_once_with(1)


class TestCategorizeOperationsMultiple:
    """Tests for categorize_operations with multiple operations."""

    def test_categorizes_multiple_operations(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_forecast_service: MagicMock,
    ) -> None:
        """categorize_operations categorizes multiple operations."""
        # Setup operations
        mock_op1 = MagicMock()
        mock_op1.category = Category.OTHER
        mock_op2 = MagicMock()
        mock_op2.category = Category.OTHER

        mock_operation_service.get_operation_by_id.side_effect = [mock_op1, mock_op2]

        updated_op1 = MagicMock()
        updated_op2 = MagicMock()
        mock_operation_service.categorize_operation.side_effect = [
            updated_op1,
            updated_op2,
        ]

        mock_operation_link_service.get_link_for_operation.return_value = None
        mock_operation_link_service.create_heuristic_links.return_value = []
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        results = app_service.categorize_operations((1, 2), Category.GROCERIES)

        assert len(results) == 2
        assert results[0].operation is updated_op1
        assert results[1].operation is updated_op2

    def test_skips_nonexistent_operations(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
    ) -> None:
        """categorize_operations skips operations that don't exist."""
        mock_operation_service.get_operation_by_id.return_value = None

        results = app_service.categorize_operations((1, 2, 3), Category.GROCERIES)

        assert len(results) == 0

    def test_batch_creates_links_for_changed_operations(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_forecast_service: MagicMock,
    ) -> None:
        """categorize_operations creates links in a single batch."""
        # Setup operations with different categories
        mock_op1 = MagicMock()
        mock_op1.category = Category.OTHER
        mock_op2 = MagicMock()
        mock_op2.category = Category.OTHER

        mock_operation_service.get_operation_by_id.side_effect = [mock_op1, mock_op2]

        updated_op1 = MagicMock()
        updated_op1.unique_id = 1
        updated_op2 = MagicMock()
        updated_op2.unique_id = 2
        mock_operation_service.categorize_operation.side_effect = [
            updated_op1,
            updated_op2,
        ]

        # No existing links
        mock_operation_link_service.get_link_for_operation.return_value = None

        # Setup matchers
        planned_op = MagicMock()
        planned_op.id = 1
        planned_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.get_all_planned_operations.return_value = [planned_op]
        mock_forecast_service.get_all_budgets.return_value = []

        # Setup batch link creation - return links for both operations
        new_link1 = MagicMock(spec=OperationLink)
        new_link1.operation_unique_id = 1
        new_link2 = MagicMock(spec=OperationLink)
        new_link2.operation_unique_id = 2
        mock_operation_link_service.create_heuristic_links.return_value = [
            new_link1,
            new_link2,
        ]

        results = app_service.categorize_operations((1, 2), Category.GROCERIES)

        # Should call create_heuristic_links only once with both operations
        assert mock_operation_link_service.create_heuristic_links.call_count == 1
        call_args = mock_operation_link_service.create_heuristic_links.call_args
        assert len(call_args[0][0]) == 2  # Both operations in the tuple

        # Results should have the created links
        assert len(results) == 2
        assert results[0].new_link is new_link1
        assert results[1].new_link is new_link2

    def test_deletes_heuristic_links_before_batch_creation(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_forecast_service: MagicMock,
    ) -> None:
        """categorize_operations deletes existing heuristic links before creating."""
        # Setup operations
        mock_op1 = MagicMock()
        mock_op1.category = Category.OTHER
        mock_op2 = MagicMock()
        mock_op2.category = Category.OTHER

        mock_operation_service.get_operation_by_id.side_effect = [mock_op1, mock_op2]

        updated_op1 = MagicMock()
        updated_op1.unique_id = 1
        updated_op2 = MagicMock()
        updated_op2.unique_id = 2
        mock_operation_service.categorize_operation.side_effect = [
            updated_op1,
            updated_op2,
        ]

        # Existing heuristic links for both
        existing_link1 = MagicMock(spec=OperationLink)
        existing_link1.is_manual = False
        existing_link2 = MagicMock(spec=OperationLink)
        existing_link2.is_manual = False
        mock_operation_link_service.get_link_for_operation.side_effect = [
            existing_link1,
            existing_link2,
        ]

        mock_operation_link_service.create_heuristic_links.return_value = []
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        app_service.categorize_operations((1, 2), Category.GROCERIES)

        # Should delete both heuristic links
        assert mock_operation_link_service.delete_link.call_count == 2

    def test_preserves_manual_links_in_bulk(
        self,
        app_service: ApplicationService,
        mock_operation_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_forecast_service: MagicMock,
    ) -> None:
        """categorize_operations preserves manual links."""
        # Setup operation
        mock_op = MagicMock()
        mock_op.category = Category.OTHER
        mock_operation_service.get_operation_by_id.return_value = mock_op

        updated_op = MagicMock()
        updated_op.unique_id = 1
        mock_operation_service.categorize_operation.return_value = updated_op

        # Existing manual link
        existing_link = MagicMock(spec=OperationLink)
        existing_link.is_manual = True
        mock_operation_link_service.get_link_for_operation.return_value = existing_link

        mock_operation_link_service.create_heuristic_links.return_value = []
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        app_service.categorize_operations((1,), Category.GROCERIES)

        # Should NOT delete manual link
        mock_operation_link_service.delete_link.assert_not_called()
        # Should NOT try to create links (operation not in changed_operations)
        mock_operation_link_service.create_heuristic_links.assert_not_called()


class TestSplitOperations:
    """Tests for split operations (split_planned_operation_at_date, split_budget_at_date)."""

    def test_split_planned_operation_not_found(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
    ) -> None:
        """split_planned_operation_at_date raises error if operation not found."""
        mock_forecast_service.get_planned_operation_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            app_service.split_planned_operation_at_date(
                operation_id=1,
                split_date=date(2025, 3, 1),
            )

    def test_split_planned_operation_non_periodic(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
    ) -> None:
        """split_planned_operation_at_date raises error for non-periodic operation."""
        op = PlannedOperation(
            record_id=1,
            description="One-time",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        mock_forecast_service.get_planned_operation_by_id.return_value = op

        with pytest.raises(ValueError, match="non-periodic"):
            app_service.split_planned_operation_at_date(
                operation_id=1,
                split_date=date(2025, 3, 1),
            )

    def test_split_planned_operation_date_before_start(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
    ) -> None:
        """split_planned_operation_at_date raises error if split_date before first iteration."""
        op = PlannedOperation(
            record_id=1,
            description="Rent",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date_range=RecurringDay(
                start_date=date(2025, 1, 1),
                period=relativedelta(months=1),
            ),
        )
        mock_forecast_service.get_planned_operation_by_id.return_value = op

        with pytest.raises(ValueError, match="after the first iteration"):
            app_service.split_planned_operation_at_date(
                operation_id=1,
                split_date=date(2025, 1, 1),  # Same as initial date
            )

    def test_split_planned_operation_success(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """split_planned_operation_at_date terminates original and creates new."""
        # Original operation
        original_op = PlannedOperation(
            record_id=1,
            description="Rent",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date_range=RecurringDay(
                start_date=date(2025, 1, 1),
                period=relativedelta(months=1),
            ),
        )
        mock_forecast_service.get_planned_operation_by_id.return_value = original_op

        # New operation created by add_planned_operation
        new_op = MagicMock()
        new_op.id = 2
        new_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.add_planned_operation.return_value = new_op
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        # No existing links
        mock_operation_link_service.load_links_for_target.return_value = ()

        result = app_service.split_planned_operation_at_date(
            operation_id=1,
            split_date=date(2025, 3, 1),
            new_amount=Amount(-850.0, "EUR"),
        )

        assert result is new_op

        # Original should be updated with expiration_date
        mock_forecast_service.update_planned_operation.assert_called_once()
        updated_original = mock_forecast_service.update_planned_operation.call_args[0][
            0
        ]
        assert updated_original.date_range.last_date == date(2025, 2, 28)

        # New operation should be created
        mock_forecast_service.add_planned_operation.assert_called_once()
        created_op = mock_forecast_service.add_planned_operation.call_args[0][0]
        assert created_op.description == "Rent"
        assert created_op.amount == -850.0
        assert created_op.date_range.start_date == date(2025, 3, 1)

    def test_split_planned_operation_migrates_links(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """split_planned_operation_at_date migrates links >= split_date."""
        original_op = PlannedOperation(
            record_id=1,
            description="Rent",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date_range=RecurringDay(
                start_date=date(2025, 1, 1),
                period=relativedelta(months=1),
            ),
        )
        mock_forecast_service.get_planned_operation_by_id.return_value = original_op

        new_op = MagicMock()
        new_op.id = 2
        new_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.add_planned_operation.return_value = new_op
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        # Existing links: one before split, two after
        existing_links = (
            OperationLink(
                operation_unique_id="op1",
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2025, 1, 1),  # Before split
            ),
            OperationLink(
                operation_unique_id="op2",
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2025, 3, 1),  # At split date
            ),
            OperationLink(
                operation_unique_id="op3",
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2025, 4, 1),  # After split
            ),
        )
        mock_operation_link_service.load_links_for_target.return_value = existing_links

        app_service.split_planned_operation_at_date(
            operation_id=1,
            split_date=date(2025, 3, 1),
        )

        # Should delete 2 links (op2, op3) and create 2 new ones
        assert mock_operation_link_service.delete_link.call_count == 2
        assert mock_operation_link_service.upsert_link.call_count == 2

        # Check the new links have the correct target_id
        upsert_calls = mock_operation_link_service.upsert_link.call_args_list
        for call in upsert_calls:
            new_link = call[0][0]
            assert new_link.target_id == 2  # New operation ID

    def test_split_budget_not_found(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
    ) -> None:
        """split_budget_at_date raises error if budget not found."""
        mock_forecast_service.get_budget_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            app_service.split_budget_at_date(
                budget_id=1,
                split_date=date(2025, 3, 1),
            )

    def test_split_budget_non_periodic(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
    ) -> None:
        """split_budget_at_date raises error for non-periodic budget."""
        budget = Budget(
            record_id=1,
            description="One-time",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            date_range=DateRange(
                start_date=date(2025, 1, 1),
                duration=relativedelta(months=1),
            ),
        )
        mock_forecast_service.get_budget_by_id.return_value = budget

        with pytest.raises(ValueError, match="non-periodic"):
            app_service.split_budget_at_date(
                budget_id=1,
                split_date=date(2025, 3, 1),
            )

    def test_split_budget_success(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """split_budget_at_date terminates original and creates new."""
        # Create periodic budget
        base_date_range = DateRange(
            start_date=date(2025, 1, 1),
            duration=relativedelta(months=1),
        )
        periodic_date_range = RecurringDateRange(
            initial_date_range=base_date_range,
            period=relativedelta(months=1),
        )
        original_budget = Budget(
            record_id=1,
            description="Groceries",
            amount=Amount(-300.0, "EUR"),
            category=Category.GROCERIES,
            date_range=periodic_date_range,
        )
        mock_forecast_service.get_budget_by_id.return_value = original_budget

        # New budget created by add_budget
        new_budget = MagicMock()
        new_budget.id = 2
        new_budget.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.add_budget.return_value = new_budget
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        # No existing links
        mock_operation_link_service.load_links_for_target.return_value = ()

        result = app_service.split_budget_at_date(
            budget_id=1,
            split_date=date(2025, 3, 1),
            new_amount=Amount(-400.0, "EUR"),
        )

        assert result is new_budget

        # Original should be updated with expiration_date
        mock_forecast_service.update_budget.assert_called_once()

        # New budget should be created
        mock_forecast_service.add_budget.assert_called_once()
        created_budget = mock_forecast_service.add_budget.call_args[0][0]
        assert created_budget.description == "Groceries"
        assert created_budget.amount == -400.0
        assert created_budget.date_range.start_date == date(2025, 3, 1)

    def test_split_budget_migrates_links(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """split_budget_at_date migrates links >= split_date."""
        # Create periodic budget
        base_date_range = DateRange(
            start_date=date(2025, 1, 1),
            duration=relativedelta(months=1),
        )
        periodic_date_range = RecurringDateRange(
            initial_date_range=base_date_range,
            period=relativedelta(months=1),
        )
        original_budget = Budget(
            record_id=1,
            description="Groceries",
            amount=Amount(-300.0, "EUR"),
            category=Category.GROCERIES,
            date_range=periodic_date_range,
        )
        mock_forecast_service.get_budget_by_id.return_value = original_budget

        new_budget = MagicMock()
        new_budget.id = 2
        new_budget.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.add_budget.return_value = new_budget
        mock_forecast_service.get_all_planned_operations.return_value = []
        mock_forecast_service.get_all_budgets.return_value = []

        # Existing links: one before split, two after
        existing_links = (
            OperationLink(
                operation_unique_id="op1",
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=date(2025, 1, 1),  # Before split
            ),
            OperationLink(
                operation_unique_id="op2",
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=date(2025, 3, 1),  # At split date
            ),
            OperationLink(
                operation_unique_id="op3",
                target_type=LinkType.BUDGET,
                target_id=1,
                iteration_date=date(2025, 4, 1),  # After split
            ),
        )
        mock_operation_link_service.load_links_for_target.return_value = existing_links

        app_service.split_budget_at_date(
            budget_id=1,
            split_date=date(2025, 3, 1),
        )

        # Should delete 2 links (op2, op3) and create 2 new ones
        assert mock_operation_link_service.delete_link.call_count == 2
        assert mock_operation_link_service.upsert_link.call_count == 2

        # Check the new links have the correct target_id
        upsert_calls = mock_operation_link_service.upsert_link.call_args_list
        for call in upsert_calls:
            new_link = call[0][0]
            assert new_link.target_id == 2  # New budget ID

    def test_get_next_non_actualized_iteration_not_found(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
    ) -> None:
        """get_next_non_actualized_iteration returns None if target not found."""
        mock_forecast_service.get_planned_operation_by_id.return_value = None

        result = app_service.get_next_non_actualized_iteration(
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
        )

        assert result is None

    def test_get_next_non_actualized_iteration_non_periodic(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
    ) -> None:
        """get_next_non_actualized_iteration returns None for non-periodic."""
        op = PlannedOperation(
            record_id=1,
            description="One-time",
            amount=Amount(-100.0, "EUR"),
            category=Category.OTHER,
            date_range=SingleDay(date(2025, 1, 15)),
        )
        mock_forecast_service.get_planned_operation_by_id.return_value = op

        result = app_service.get_next_non_actualized_iteration(
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
        )

        assert result is None

    def test_get_next_non_actualized_iteration_finds_first_unlinked(
        self,
        app_service: ApplicationService,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """get_next_non_actualized_iteration skips actualized iterations."""
        op = PlannedOperation(
            record_id=1,
            description="Rent",
            amount=Amount(-800.0, "EUR"),
            category=Category.RENT,
            date_range=RecurringDay(
                start_date=date(2025, 1, 1),
                period=relativedelta(months=1),
            ),
        )
        mock_forecast_service.get_planned_operation_by_id.return_value = op

        # Jan and Feb are actualized
        existing_links = (
            OperationLink(
                operation_unique_id="op1",
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2025, 1, 1),
            ),
            OperationLink(
                operation_unique_id="op2",
                target_type=LinkType.PLANNED_OPERATION,
                target_id=1,
                iteration_date=date(2025, 2, 1),
            ),
        )
        mock_operation_link_service.load_links_for_target.return_value = existing_links

        result = app_service.get_next_non_actualized_iteration(
            target_type=LinkType.PLANNED_OPERATION,
            target_id=1,
        )

        # Should return March (first non-actualized after today if today < March)
        # Note: This test assumes we're running before March 2025
        # The method finds the first future iteration without a link
        assert result is not None
        assert result not in {date(2025, 1, 1), date(2025, 2, 1)}
