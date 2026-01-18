"""Service for orchestrating operation link lifecycle.

This module contains the OperationLinkService class that bridges
the OperationMatcher (uses links in memory) and the OperationLinkRepository
(persists links in the database).
"""

from datetime import datetime, timedelta

from budget_forecaster.account.repository_interface import (
    OperationLinkRepositoryInterface,
)
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.operation_link import LinkType, OperationLink
from budget_forecaster.operation_range.operation_matcher import OperationMatcher
from budget_forecaster.operation_range.operation_range import OperationRange
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.types import (
    BudgetId,
    IterationDate,
    OperationId,
    PlannedOperationId,
)


def compute_match_score(
    operation: HistoricOperation,
    operation_range: OperationRange,
    iteration_date: datetime,
    approximation_amount_ratio: float = 0.05,
    approximation_date_range: timedelta = timedelta(days=5),
    description_hints: set[str] | None = None,
) -> float:
    """Compute a match score (0-100) for an operation against a specific iteration.

    Uses the same criteria as OperationMatcher with weighted scoring:
    - Amount: 40% of score
    - Date: 30% of score
    - Category: 20% of score
    - Description: 10% of score

    Args:
        operation: The historic operation to score.
        operation_range: The operation range to match against.
        iteration_date: The date of the specific iteration.
        approximation_amount_ratio: Tolerance ratio for amount matching.
        approximation_date_range: Tolerance for date matching.
        description_hints: Keywords that must appear in operation descriptions.

    Returns:
        A score from 0 to 100 indicating match quality.
    """
    hints = description_hints or set()
    approx_date_days = approximation_date_range.days

    score = 0.0

    # Amount score (40%)
    if (planned_amount := abs(operation_range.amount)) > 0:
        amount_diff = abs(abs(operation.amount) - planned_amount) / planned_amount
        if amount_diff <= approximation_amount_ratio:
            score += 40.0  # Full score if within tolerance
        else:
            # Gradual decrease beyond tolerance
            score += max(0.0, 40.0 * (1 - (amount_diff - approximation_amount_ratio)))

    # Date score (30%) - distance to specific iteration
    if (days_diff := abs((operation.date - iteration_date).days)) <= approx_date_days:
        score += 30.0  # Full score if within tolerance
    else:
        # Gradual decrease: score drops to 0 at 30 days beyond tolerance
        score += max(0.0, 30.0 * (1 - (days_diff - approx_date_days) / 30))

    # Category score (20%)
    if operation.category == operation_range.category:
        score += 20.0

    # Description score (10%)
    if hints:
        if all(hint in operation.description for hint in hints):
            score += 10.0
    # If no hints are configured, we don't award description points
    # (this matches the existing match_description behavior)

    return score


class OperationLinkService:
    """Orchestrates operation link lifecycle between matcher and repository.

    This service is responsible for:
    - Loading links from DB and injecting them into matchers
    - Creating heuristic links during import/actualize
    - Recalculating links when planned ops/budgets change
    - Preserving manual links during recalculation
    """

    def __init__(self, repository: OperationLinkRepositoryInterface) -> None:
        """Initialize the service.

        Args:
            repository: Repository for operation link persistence.
        """
        self._repository = repository

    def load_links_for_matcher(
        self, linked_type: LinkType, linked_id: PlannedOperationId | BudgetId
    ) -> dict[OperationId, IterationDate]:
        """Load links from DB as a dict suitable for OperationMatcher.

        Args:
            linked_type: The type of target (planned operation or budget).
            linked_id: The ID of the target.

        Returns:
            Dict mapping operation_unique_id to iteration_date.
        """
        match linked_type:
            case LinkType.PLANNED_OPERATION:
                links = self._repository.get_links_for_planned_operation(linked_id)
            case LinkType.BUDGET:
                links = self._repository.get_links_for_budget(linked_id)
        return {link.operation_unique_id: link.iteration_date for link in links}

    def create_matcher_with_links(
        self,
        operation_range: OperationRange,
        linked_type: LinkType,
        linked_id: PlannedOperationId | BudgetId,
        **matcher_kwargs,
    ) -> OperationMatcher:
        """Create an OperationMatcher pre-loaded with links from DB.

        Args:
            operation_range: The operation range to match against.
            linked_type: The type of target (planned operation or budget).
            linked_id: The ID of the target.
            **matcher_kwargs: Additional arguments for OperationMatcher.

        Returns:
            A configured OperationMatcher with links loaded.
        """
        links = self.load_links_for_matcher(linked_type, linked_id)
        return OperationMatcher(
            operation_range=operation_range,
            operation_links=links,
            **matcher_kwargs,
        )

    def create_heuristic_links(
        self,
        operations: tuple[HistoricOperation, ...],
        matchers_by_target: dict[
            tuple[LinkType, PlannedOperationId | BudgetId], OperationMatcher
        ],
    ) -> tuple[OperationLink, ...]:
        """Create and persist heuristic links for unlinked operations.

        For each operation that is not already linked, tries to find a
        matching target using the provided matchers. If a match is found,
        creates and persists a heuristic link.

        Args:
            operations: Operations to process.
            matchers_by_target: Dict mapping (LinkType, id) to OperationMatcher.

        Returns:
            Tuple of created OperationLinks.
        """
        created_links: list[OperationLink] = []

        for operation in operations:
            # Skip if already linked
            if self._repository.get_link_for_operation(operation.unique_id):
                continue

            # Try each matcher to find a match
            best_match: tuple[
                tuple[LinkType, PlannedOperationId | BudgetId], OperationMatcher, float
            ] | None = None

            for (linked_type, linked_id), matcher in matchers_by_target.items():
                # Check if operation matches this target using the matcher's logic
                if not matcher.match(operation):
                    continue

                # Find the iteration using the matcher's date tolerance
                current_iteration = (
                    matcher.operation_range.time_range.current_time_range(
                        operation.date,
                        approx_before=matcher.approximation_date_range,
                        approx_after=matcher.approximation_date_range,
                    )
                )
                if current_iteration is None:
                    continue
                iteration_date = current_iteration.initial_date

                # Compute match score for tie-breaking
                score = compute_match_score(
                    operation,
                    matcher.operation_range,
                    iteration_date,
                    approximation_amount_ratio=matcher.approximation_amount_ratio,
                    approximation_date_range=matcher.approximation_date_range,
                    description_hints=matcher.description_hints,
                )

                if (
                    best_match is None
                    or score > best_match[2]  # pylint: disable=unsubscriptable-object
                ):
                    best_match = ((linked_type, linked_id), matcher, score)

            # Create link for best match
            if best_match is not None:
                (linked_type, linked_id), matcher, _ = best_match
                current_iteration = (
                    matcher.operation_range.time_range.current_time_range(
                        operation.date,
                        approx_before=matcher.approximation_date_range,
                        approx_after=matcher.approximation_date_range,
                    )
                )
                if current_iteration is not None:
                    link = OperationLink(
                        operation_unique_id=operation.unique_id,
                        linked_type=linked_type,
                        linked_id=linked_id,
                        iteration_date=current_iteration.initial_date,
                        is_manual=False,
                    )
                    self._repository.create_link(link)
                    created_links.append(link)

        return tuple(created_links)

    def recalculate_links_for_target(
        self,
        target: PlannedOperation | Budget,
        operations: tuple[HistoricOperation, ...],
    ) -> tuple[OperationLink, ...]:
        """Recalculate heuristic links for a target after it was modified.

        Deletes all heuristic (non-manual) links for this target, then
        recreates them by running matching against all unlinked operations.

        Manual links are preserved and never overwritten.

        Args:
            target: The planned operation or budget to recalculate links for.
            operations: All operations to consider for linking.

        Returns:
            Tuple of newly created OperationLinks.
        """
        if target.id is None:
            return ()

        linked_type = (
            LinkType.PLANNED_OPERATION
            if isinstance(target, PlannedOperation)
            else LinkType.BUDGET
        )

        # Delete only heuristic links for this target (manual links preserved)
        self._repository.delete_automatic_links_for_target(linked_type, target.id)

        # Recreate heuristic links
        return self.create_heuristic_links(
            operations,
            {(linked_type, target.id): target.matcher},
        )
