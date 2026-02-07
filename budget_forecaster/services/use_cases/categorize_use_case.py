"""Use case for categorizing operations."""

import logging

from budget_forecaster.core.types import Category, OperationId
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.operation.operation_service import (
    OperationCategoryUpdate,
    OperationService,
)
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache

logger = logging.getLogger(__name__)


class CategorizeUseCase:  # pylint: disable=too-few-public-methods
    """Categorize operations and manage heuristic links on category change."""

    def __init__(
        self,
        operation_service: OperationService,
        operation_link_service: OperationLinkService,
        matcher_cache: MatcherCache,
    ) -> None:
        self._operation_service = operation_service
        self._operation_link_service = operation_link_service
        self._matcher_cache = matcher_cache

    def categorize_operations(
        self, operation_ids: tuple[OperationId, ...], category: Category
    ) -> tuple[OperationCategoryUpdate, ...]:
        """Categorize one or more operations and create heuristic links.

        When a category changes:
        1. Delete existing heuristic link (if any) - manual links are preserved
        2. Batch create new heuristic links for all changed operations

        Args:
            operation_ids: Tuple of operation IDs to categorize.
            category: The category to assign to all operations.

        Returns:
            Tuple of OperationCategoryUpdate for each successfully updated operation.
            Operations not found are silently skipped.
        """
        results: list[OperationCategoryUpdate] = []
        changed_operations: list[HistoricOperation] = []

        for op_id in operation_ids:
            if (op := self._operation_service.get_operation_by_id(op_id)) is None:
                continue

            old_category = op.category
            if (
                updated := self._operation_service.categorize_operation(op_id, category)
            ) is None:
                continue

            if category_changed := old_category != category:
                existing = self._operation_link_service.get_link_for_operation(op_id)
                if existing is not None and not existing.is_manual:
                    self._operation_link_service.delete_link(op_id)
                    changed_operations.append(updated)
                elif existing is None:
                    changed_operations.append(updated)

            results.append(OperationCategoryUpdate(updated, category_changed, None))

        # Batch create heuristic links for all changed operations
        created_links: dict[OperationId, OperationLink] = {}
        if changed_operations and (matchers := self._matcher_cache.get_matchers()):
            for link in self._operation_link_service.create_heuristic_links(
                tuple(changed_operations), matchers
            ):
                created_links[link.operation_unique_id] = link

        # Enrich results with created links
        return tuple(
            OperationCategoryUpdate(
                r.operation,
                r.category_changed,
                created_links.get(r.operation.unique_id),
            )
            if r.operation.unique_id in created_links
            else r
            for r in results
        )
