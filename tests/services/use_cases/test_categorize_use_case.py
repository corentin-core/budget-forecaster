"""Tests for the CategorizeUseCase."""

# pylint: disable=redefined-outer-name

from unittest.mock import MagicMock

import pytest

from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.operation.operation_service import OperationService
from budget_forecaster.services.use_cases.categorize_use_case import CategorizeUseCase
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache


@pytest.fixture
def mock_operation_service() -> MagicMock:
    """Create a mock operation service."""
    return MagicMock(spec=OperationService)


@pytest.fixture
def mock_operation_link_service() -> MagicMock:
    """Create a mock operation link service."""
    return MagicMock(spec=OperationLinkService)


@pytest.fixture
def mock_matcher_cache() -> MagicMock:
    """Create a mock matcher cache."""
    mock = MagicMock(spec=MatcherCache)
    mock.get_matchers.return_value = {}
    return mock


@pytest.fixture
def use_case(
    mock_operation_service: MagicMock,
    mock_operation_link_service: MagicMock,
    mock_matcher_cache: MagicMock,
) -> CategorizeUseCase:
    """Create a CategorizeUseCase with mock dependencies."""
    return CategorizeUseCase(
        mock_operation_service, mock_operation_link_service, mock_matcher_cache
    )


class TestCategorizeOperations:
    """Tests for categorize_operations."""

    def test_skips_nonexistent_operations(
        self,
        use_case: CategorizeUseCase,
        mock_operation_service: MagicMock,
    ) -> None:
        """Non-existent operations are silently skipped."""
        mock_operation_service.get_operation_by_id.return_value = None

        results = use_case.categorize_operations((999,), Category.GROCERIES)

        assert len(results) == 0

    def test_delegates_to_operation_service(
        self,
        use_case: CategorizeUseCase,
        mock_operation_service: MagicMock,
    ) -> None:
        """Categorization delegates to the operation service."""
        op = MagicMock()
        op.unique_id = 1
        op.category = Category.GROCERIES
        mock_operation_service.get_operation_by_id.return_value = op
        mock_operation_service.categorize_operation.return_value = op

        results = use_case.categorize_operations((1,), Category.GROCERIES)

        assert len(results) == 1
        mock_operation_service.categorize_operation.assert_called_once_with(
            1, Category.GROCERIES
        )

    def test_deletes_heuristic_link_on_category_change(
        self,
        use_case: CategorizeUseCase,
        mock_operation_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Heuristic links are deleted when category changes."""
        op = MagicMock()
        op.unique_id = 1
        op.category = Category.GROCERIES
        mock_operation_service.get_operation_by_id.return_value = op

        updated = MagicMock()
        updated.unique_id = 1
        mock_operation_service.categorize_operation.return_value = updated

        existing_link = MagicMock(spec=OperationLink)
        existing_link.is_manual = False
        mock_operation_link_service.get_link_for_operation.return_value = existing_link

        use_case.categorize_operations((1,), Category.RENT)

        mock_operation_link_service.delete_link.assert_called_once_with(1)

    def test_preserves_manual_links(
        self,
        use_case: CategorizeUseCase,
        mock_operation_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Manual links are preserved when category changes."""
        op = MagicMock()
        op.unique_id = 1
        op.category = Category.GROCERIES
        mock_operation_service.get_operation_by_id.return_value = op

        updated = MagicMock()
        updated.unique_id = 1
        mock_operation_service.categorize_operation.return_value = updated

        existing_link = MagicMock(spec=OperationLink)
        existing_link.is_manual = True
        mock_operation_link_service.get_link_for_operation.return_value = existing_link

        use_case.categorize_operations((1,), Category.RENT)

        mock_operation_link_service.delete_link.assert_not_called()
