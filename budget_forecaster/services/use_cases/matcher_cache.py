"""Lazy-loaded cache of operation matchers for heuristic link creation."""

import logging

from budget_forecaster.core.types import LinkType, MatcherKey
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.operation_matcher import OperationMatcher

logger = logging.getLogger(__name__)


class MatcherCache:
    """Lazy-loaded cache mapping targets to their operation matchers.

    This cache is shared across use cases that need to create heuristic
    links (import, categorize, target CRUD). It is built lazily on first
    access and updated incrementally when targets are added or removed.
    """

    def __init__(self, forecast_service: ForecastService) -> None:
        self._forecast_service = forecast_service
        self._matchers: dict[MatcherKey, OperationMatcher] | None = None

    def _build_matchers(self) -> dict[MatcherKey, OperationMatcher]:
        """Build matchers for all planned operations and budgets."""
        matchers: dict[MatcherKey, OperationMatcher] = {}

        for planned_op in self._forecast_service.get_all_planned_operations():
            if planned_op.id is not None:
                key = MatcherKey(LinkType.PLANNED_OPERATION, planned_op.id)
                matchers[key] = planned_op.matcher

        for budget in self._forecast_service.get_all_budgets():
            if budget.id is not None:
                key = MatcherKey(LinkType.BUDGET, budget.id)
                matchers[key] = budget.matcher

        logger.debug(
            "Built %d matchers (%d planned operations, %d budgets)",
            len(matchers),
            sum(1 for k in matchers if k.link_type == LinkType.PLANNED_OPERATION),
            sum(1 for k in matchers if k.link_type == LinkType.BUDGET),
        )

        return matchers

    def get_matchers(self) -> dict[MatcherKey, OperationMatcher]:
        """Get the matcher cache, building it if necessary."""
        if self._matchers is None:
            self._matchers = self._build_matchers()
        return self._matchers

    def add_matcher(self, target: PlannedOperation | Budget) -> None:
        """Add or update a matcher for a target."""
        if target.id is None:
            return

        matchers = self.get_matchers()
        if isinstance(target, PlannedOperation):
            key = MatcherKey(LinkType.PLANNED_OPERATION, target.id)
        else:
            key = MatcherKey(LinkType.BUDGET, target.id)
        matchers[key] = target.matcher

    def remove_matcher(self, key: MatcherKey) -> None:
        """Remove a matcher from the cache."""
        matchers = self.get_matchers()
        matchers.pop(key, None)
