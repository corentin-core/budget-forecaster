"""Tests for the MatcherCache."""


from unittest.mock import MagicMock

import pytest

from budget_forecaster.core.types import LinkType, MatcherKey
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.operation_matcher import OperationMatcher
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache


@pytest.fixture(name="mock_forecast_service")
def mock_forecast_service_fixture() -> MagicMock:
    """Create a mock forecast service."""
    mock = MagicMock(spec=ForecastService)
    mock.get_all_planned_operations.return_value = []
    mock.get_all_budgets.return_value = []
    return mock


@pytest.fixture(name="matcher_cache")
def matcher_cache_fixture(mock_forecast_service: MagicMock) -> MatcherCache:
    """Create a MatcherCache with mock dependencies."""
    return MatcherCache(mock_forecast_service)


class TestGetMatchers:
    """Tests for lazy matcher building."""

    def test_builds_matchers_lazily(
        self,
        matcher_cache: MatcherCache,
        mock_forecast_service: MagicMock,
    ) -> None:
        """Matchers are built lazily on first access."""
        planned_op = MagicMock()
        planned_op.id = 1
        planned_op.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.get_all_planned_operations.return_value = [planned_op]

        budget = MagicMock()
        budget.id = 2
        budget.matcher = MagicMock(spec=OperationMatcher)
        mock_forecast_service.get_all_budgets.return_value = [budget]

        matchers = matcher_cache.get_matchers()

        assert len(matchers) == 2
        assert MatcherKey(LinkType.PLANNED_OPERATION, 1) in matchers
        assert MatcherKey(LinkType.BUDGET, 2) in matchers

    def test_caches_matchers(
        self,
        matcher_cache: MatcherCache,
        mock_forecast_service: MagicMock,
    ) -> None:
        """Matchers are cached after first build."""
        matcher_cache.get_matchers()
        matcher_cache.get_matchers()

        assert mock_forecast_service.get_all_planned_operations.call_count == 1
        assert mock_forecast_service.get_all_budgets.call_count == 1


class TestAddMatcher:
    """Tests for adding matchers to the cache."""

    def test_adds_planned_operation_matcher(
        self,
        matcher_cache: MatcherCache,
    ) -> None:
        """Adding a planned operation registers its matcher."""
        target = MagicMock(spec=PlannedOperation)
        target.id = 42
        target.matcher = MagicMock(spec=OperationMatcher)

        matcher_cache.add_matcher(target)

        matchers = matcher_cache.get_matchers()
        assert MatcherKey(LinkType.PLANNED_OPERATION, 42) in matchers
        assert matchers[MatcherKey(LinkType.PLANNED_OPERATION, 42)] is target.matcher

    def test_adds_budget_matcher(
        self,
        matcher_cache: MatcherCache,
    ) -> None:
        """Adding a budget registers its matcher."""
        target = MagicMock(spec=Budget)
        target.id = 7
        target.matcher = MagicMock(spec=OperationMatcher)

        matcher_cache.add_matcher(target)

        matchers = matcher_cache.get_matchers()
        assert MatcherKey(LinkType.BUDGET, 7) in matchers

    def test_ignores_target_without_id(
        self,
        matcher_cache: MatcherCache,
    ) -> None:
        """Targets without an ID are silently ignored."""
        target = MagicMock(spec=PlannedOperation)
        target.id = None

        matcher_cache.add_matcher(target)

        matchers = matcher_cache.get_matchers()
        assert len(matchers) == 0


class TestRemoveMatcher:
    """Tests for removing matchers from the cache."""

    def test_removes_existing_matcher(
        self,
        matcher_cache: MatcherCache,
    ) -> None:
        """Removing a key deletes the matcher."""
        target = MagicMock(spec=PlannedOperation)
        target.id = 1
        target.matcher = MagicMock(spec=OperationMatcher)
        matcher_cache.add_matcher(target)

        key = MatcherKey(LinkType.PLANNED_OPERATION, 1)
        matcher_cache.remove_matcher(key)

        matchers = matcher_cache.get_matchers()
        assert key not in matchers

    def test_removes_nonexistent_key_silently(
        self,
        matcher_cache: MatcherCache,
    ) -> None:
        """Removing a non-existent key does not raise."""
        key = MatcherKey(LinkType.BUDGET, 999)
        matcher_cache.remove_matcher(key)  # Should not raise
