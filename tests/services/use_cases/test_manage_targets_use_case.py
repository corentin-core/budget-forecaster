"""Tests for the ManageTargetsUseCase."""

# pylint: disable=too-few-public-methods

from datetime import date
from unittest.mock import MagicMock

import pytest

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import SingleDay
from budget_forecaster.core.types import (
    BudgetId,
    LinkType,
    MatcherKey,
    PlannedOperationId,
)
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.operation.operation_matcher import OperationMatcher
from budget_forecaster.services.use_cases.manage_targets_use_case import (
    ManageTargetsUseCase,
)
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache


@pytest.fixture(name="mock_forecast_service")
def mock_forecast_service_fixture() -> MagicMock:
    """Create a mock forecast service."""
    return MagicMock(spec=ForecastService)


@pytest.fixture(name="mock_persistent_account")
def mock_persistent_account_fixture() -> MagicMock:
    """Create a mock persistent account."""
    mock = MagicMock()
    mock.account.operations = ()
    return mock


@pytest.fixture(name="mock_operation_link_service")
def mock_operation_link_service_fixture() -> MagicMock:
    """Create a mock operation link service."""
    return MagicMock(spec=OperationLinkService)


@pytest.fixture(name="mock_matcher_cache")
def mock_matcher_cache_fixture() -> MagicMock:
    """Create a mock matcher cache."""
    return MagicMock(spec=MatcherCache)


@pytest.fixture(name="use_case")
def use_case_fixture(
    mock_forecast_service: MagicMock,
    mock_persistent_account: MagicMock,
    mock_operation_link_service: MagicMock,
    mock_matcher_cache: MagicMock,
) -> ManageTargetsUseCase:
    """Create a ManageTargetsUseCase with mock dependencies."""
    return ManageTargetsUseCase(
        mock_forecast_service,
        mock_persistent_account,
        mock_operation_link_service,
        mock_matcher_cache,
    )


class TestAddPlannedOperation:
    """Tests for add_planned_operation."""

    def test_delegates_and_creates_links(
        self,
        use_case: ManageTargetsUseCase,
        mock_forecast_service: MagicMock,
        mock_matcher_cache: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Adding a planned operation creates it and triggers link creation."""
        new_op = MagicMock(spec=PlannedOperation)
        new_op.id = 42
        new_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.add_planned_operation.return_value = new_op
        mock_operation_link_service.create_heuristic_links.return_value = []

        result = use_case.add_planned_operation(MagicMock(spec=PlannedOperation))

        assert result is new_op
        mock_matcher_cache.add_matcher.assert_called_once_with(new_op)
        mock_operation_link_service.create_heuristic_links.assert_called_once()


class TestUpdatePlannedOperation:
    """Tests for update_planned_operation."""

    def test_requires_id(self, use_case: ManageTargetsUseCase) -> None:
        """Update requires a valid ID."""
        op = MagicMock(spec=PlannedOperation)
        op.id = None

        with pytest.raises(ValueError, match="valid ID"):
            use_case.update_planned_operation(op)

    def test_recalculates_links(
        self,
        use_case: ManageTargetsUseCase,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Update deletes automatic links and recreates them."""
        op = MagicMock(spec=PlannedOperation)
        op.id = 1
        updated_op = MagicMock(spec=PlannedOperation)
        updated_op.id = 1
        updated_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.update_planned_operation.return_value = updated_op
        mock_operation_link_service.create_heuristic_links.return_value = []

        use_case.update_planned_operation(op)

        mock_operation_link_service.delete_automatic_links_for_target.assert_called_once_with(
            LinkType.PLANNED_OPERATION, 1
        )


class TestDeletePlannedOperation:
    """Tests for delete_planned_operation."""

    def test_deletes_links_and_operation(
        self,
        use_case: ManageTargetsUseCase,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_matcher_cache: MagicMock,
    ) -> None:
        """Delete removes all links, matcher, and the operation."""
        use_case.delete_planned_operation(PlannedOperationId(5))

        mock_operation_link_service.delete_links_for_target.assert_called_once_with(
            LinkType.PLANNED_OPERATION, 5
        )
        mock_matcher_cache.remove_matcher.assert_called_once_with(
            MatcherKey(LinkType.PLANNED_OPERATION, 5)
        )
        mock_forecast_service.delete_planned_operation.assert_called_once_with(5)


class TestAddBudget:
    """Tests for add_budget."""

    def test_delegates_and_creates_links(
        self,
        use_case: ManageTargetsUseCase,
        mock_forecast_service: MagicMock,
        mock_matcher_cache: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Adding a budget creates it and triggers link creation."""
        new_budget = MagicMock(spec=Budget)
        new_budget.id = 10
        new_budget.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.add_budget.return_value = new_budget
        mock_operation_link_service.create_heuristic_links.return_value = []

        result = use_case.add_budget(MagicMock(spec=Budget))

        assert result is new_budget
        mock_matcher_cache.add_matcher.assert_called_once_with(new_budget)


class TestDeleteBudget:
    """Tests for delete_budget."""

    def test_deletes_links_and_budget(
        self,
        use_case: ManageTargetsUseCase,
        mock_forecast_service: MagicMock,
        mock_operation_link_service: MagicMock,
        mock_matcher_cache: MagicMock,
    ) -> None:
        """Delete removes all links, matcher, and the budget."""
        use_case.delete_budget(BudgetId(3))

        mock_operation_link_service.delete_links_for_target.assert_called_once_with(
            LinkType.BUDGET, 3
        )
        mock_matcher_cache.remove_matcher.assert_called_once_with(
            MatcherKey(LinkType.BUDGET, 3)
        )
        mock_forecast_service.delete_budget.assert_called_once_with(3)


class TestSplitPlannedOperation:
    """Tests for split_planned_operation_at_date."""

    def test_not_found_raises(
        self,
        use_case: ManageTargetsUseCase,
        mock_forecast_service: MagicMock,
    ) -> None:
        """Splitting a non-existent operation raises ValueError."""
        mock_forecast_service.get_planned_operation_by_id.return_value = None

        with pytest.raises(ValueError, match="not found"):
            use_case.split_planned_operation_at_date(
                999, date(2025, 6, 1), Amount(100.0)
            )

    def test_split_creates_continuation(
        self,
        use_case: ManageTargetsUseCase,
        mock_forecast_service: MagicMock,
        mock_matcher_cache: MagicMock,
        mock_operation_link_service: MagicMock,
    ) -> None:
        """Splitting creates a terminated + continuation pair."""
        original = MagicMock(spec=PlannedOperation)
        original.id = 1
        terminated = MagicMock(spec=PlannedOperation)
        continuation = MagicMock(spec=PlannedOperation)
        original.split_at.return_value = (terminated, continuation)

        new_op = MagicMock(spec=PlannedOperation)
        new_op.id = 2
        mock_forecast_service.get_planned_operation_by_id.return_value = original
        mock_forecast_service.add_planned_operation.return_value = new_op
        mock_operation_link_service.load_links_for_target.return_value = []

        result = use_case.split_planned_operation_at_date(1, date(2025, 6, 1))

        assert result is new_op
        mock_forecast_service.update_planned_operation.assert_called_once_with(
            terminated
        )
        mock_forecast_service.add_planned_operation.assert_called_once_with(
            continuation
        )
        mock_matcher_cache.add_matcher.assert_called_once_with(new_op)


class TestGetNextNonActualizedIteration:
    """Tests for get_next_non_actualized_iteration."""

    def test_not_found_returns_none(
        self,
        use_case: ManageTargetsUseCase,
        mock_forecast_service: MagicMock,
    ) -> None:
        """Non-existent target returns None."""
        mock_forecast_service.get_planned_operation_by_id.return_value = None

        result = use_case.get_next_non_actualized_iteration(
            LinkType.PLANNED_OPERATION, 999
        )

        assert result is None

    def test_non_periodic_returns_none(
        self,
        use_case: ManageTargetsUseCase,
        mock_forecast_service: MagicMock,
    ) -> None:
        """Non-periodic target returns None."""
        target = MagicMock(spec=PlannedOperation)
        target.id = 1
        target.date_range = SingleDay(date(2025, 1, 1))
        mock_forecast_service.get_planned_operation_by_id.return_value = target

        result = use_case.get_next_non_actualized_iteration(
            LinkType.PLANNED_OPERATION, 1
        )

        assert result is None
