"""Service for managing operations.

This service provides a UI-agnostic API for querying and modifying operations.
It can be used by TUI, GUI, or Web interfaces.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, NamedTuple

from budget_forecaster.core.types import Category
from budget_forecaster.domain.account.account_interface import AccountInterface
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink


class OperationCategoryUpdate(NamedTuple):
    """Result of categorizing an operation.

    Attributes:
        operation: The updated HistoricOperation.
        category_changed: True if the category was actually changed.
        new_link: The newly created link, or None if no link was created.
    """

    operation: HistoricOperation
    category_changed: bool
    new_link: OperationLink | None


@dataclass
class OperationFilter:
    """Filter criteria for operations."""

    search_text: str | None = None
    category: Category | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    uncategorized_only: bool = False

    def matches(  # pylint: disable=too-many-return-statements
        self, operation: HistoricOperation
    ) -> bool:
        """Check if an operation matches this filter."""
        if self.search_text:
            if self.search_text.lower() not in operation.description.lower():
                return False

        if self.category is not None and operation.category != self.category:
            return False

        if self.date_from is not None and operation.date < self.date_from:
            return False

        if self.date_to is not None and operation.date > self.date_to:
            return False

        if self.min_amount is not None and operation.amount < self.min_amount:
            return False

        if self.max_amount is not None and operation.amount > self.max_amount:
            return False

        if self.uncategorized_only and operation.category != Category.UNCATEGORIZED:
            return False

        return True


class OperationService:
    """Service for managing operations.

    This service provides methods to query and modify operations through
    the AccountInterface. It is designed to be UI-agnostic and can be
    used by any presentation layer (TUI, GUI, Web).
    """

    def __init__(self, account_manager: AccountInterface) -> None:
        """Initialize the service with an account manager.

        Args:
            account_manager: An object implementing AccountInterface
                           (e.g., PersistentAccount)
        """
        self._account_manager = account_manager

    @property
    def operations(self) -> tuple[HistoricOperation, ...]:
        """Get all operations from the account."""
        return self._account_manager.account.operations

    def get_operations(
        self,
        filter_criteria: OperationFilter | None = None,
        sort_key: Callable[[HistoricOperation], Any] | None = None,
        sort_reverse: bool = True,
    ) -> list[HistoricOperation]:
        """Get operations with optional filtering and sorting.

        Args:
            filter_criteria: Optional filter to apply
            sort_key: Function to extract sort key from operation.
                     Defaults to sorting by date.
            sort_reverse: If True, sort descending. Defaults to True.

        Returns:
            List of operations matching the filter, sorted as specified.
        """
        operations = list(self.operations)

        if filter_criteria:
            operations = [op for op in operations if filter_criteria.matches(op)]

        def default_sort_key(op: HistoricOperation) -> datetime:
            return op.date

        return sorted(
            operations,
            key=sort_key if sort_key is not None else default_sort_key,
            reverse=sort_reverse,
        )

    def get_operation_by_id(self, operation_id: int) -> HistoricOperation | None:
        """Get a single operation by its ID.

        Args:
            operation_id: The unique ID of the operation.

        Returns:
            The operation if found, None otherwise.
        """
        for operation in self.operations:
            if operation.unique_id == operation_id:
                return operation
        return None

    def get_uncategorized_operations(self) -> list[HistoricOperation]:
        """Get all operations that need categorization.

        Returns:
            List of operations with category OTHER, sorted by date descending.
        """
        return self.get_operations(
            filter_criteria=OperationFilter(uncategorized_only=True)
        )

    def update_operation(
        self,
        operation_id: int,
        *,
        category: Category | None = None,
        description: str | None = None,
    ) -> HistoricOperation | None:
        """Update an operation's fields.

        Args:
            operation_id: The ID of the operation to update.
            category: New category (if provided).
            description: New description (if provided).

        Returns:
            The updated operation, or None if not found.
        """
        if (operation := self.get_operation_by_id(operation_id)) is None:
            return None

        kwargs: dict[str, object] = {}
        if category is not None:
            kwargs["category"] = category
        if description is not None:
            kwargs["description"] = description

        if not kwargs:
            return operation

        new_operation = operation.replace(**kwargs)
        self._account_manager.replace_operation(new_operation)
        return new_operation

    def categorize_operation(
        self, operation_id: int, category: Category
    ) -> HistoricOperation | None:
        """Categorize an operation.

        Args:
            operation_id: The ID of the operation to categorize.
            category: The category to assign.

        Returns:
            The updated operation, or None if not found.
        """
        return self.update_operation(operation_id, category=category)

    def bulk_categorize(
        self, operation_ids: list[int], category: Category
    ) -> list[HistoricOperation]:
        """Categorize multiple operations at once.

        Args:
            operation_ids: List of operation IDs to categorize.
            category: The category to assign to all operations.

        Returns:
            List of updated operations (excludes any that weren't found).
        """
        updated = []
        for op_id in operation_ids:
            if (result := self.categorize_operation(op_id, category)) is not None:
                updated.append(result)
        return updated

    def find_similar_operations(
        self, operation: HistoricOperation, limit: int = 5
    ) -> list[HistoricOperation]:
        """Find operations with similar descriptions.

        Useful for suggesting categories based on past categorizations.

        Args:
            operation: The operation to find similar ones for.
            limit: Maximum number of results to return.

        Returns:
            List of similar operations, excluding the input operation.
        """
        # Simple word-based similarity
        words = set(operation.description.lower().split())

        def similarity_score(other: HistoricOperation) -> int:
            if other.unique_id == operation.unique_id:
                return -1
            other_words = set(other.description.lower().split())
            return len(words & other_words)

        all_ops = list(self.operations)
        all_ops.sort(key=similarity_score, reverse=True)

        # Filter out operations with no common words and the operation itself
        similar = [
            op
            for op in all_ops
            if similarity_score(op) > 0 and op.unique_id != operation.unique_id
        ]
        return similar[:limit]

    def suggest_category(self, operation: HistoricOperation) -> Category | None:
        """Suggest a category based on similar operations.

        Args:
            operation: The operation to suggest a category for.

        Returns:
            The most common category among similar operations,
            or None if no suggestion can be made.
        """
        if not (similar := self.find_similar_operations(operation)):
            return None

        # Find the most common category (excluding UNCATEGORIZED)
        if not (
            categories := [
                op.category for op in similar if op.category != Category.UNCATEGORIZED
            ]
        ):
            return None

        # Return the most frequent category
        return max(set(categories), key=categories.count)

    def get_category_totals(
        self, filter_criteria: OperationFilter | None = None
    ) -> dict[Category, float]:
        """Get total amounts per category.

        Args:
            filter_criteria: Optional filter to apply before aggregating.

        Returns:
            Dictionary mapping categories to their total amounts.
        """
        operations = self.get_operations(filter_criteria)
        totals: dict[Category, float] = {}

        for op in operations:
            if op.category not in totals:
                totals[op.category] = 0.0
            totals[op.category] += op.amount

        return totals

    def get_monthly_totals(
        self, filter_criteria: OperationFilter | None = None
    ) -> dict[str, float]:
        """Get total amounts per month.

        Args:
            filter_criteria: Optional filter to apply before aggregating.

        Returns:
            Dictionary mapping month strings (YYYY-MM) to their total amounts.
        """
        operations = self.get_operations(filter_criteria)
        totals: dict[str, float] = {}

        for op in operations:
            if (month_key := op.date.strftime("%Y-%m")) not in totals:
                totals[month_key] = 0.0
            totals[month_key] += op.amount

        return totals

    @property
    def balance(self) -> float:
        """Get the current account balance."""
        return self._account_manager.account.balance

    @property
    def currency(self) -> str:
        """Get the account currency."""
        return self._account_manager.account.currency

    @property
    def balance_date(self) -> datetime:
        """Get the date of the last balance update."""
        return self._account_manager.account.balance_date
