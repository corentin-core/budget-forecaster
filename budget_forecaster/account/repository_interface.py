"""Abstract interface for repository operations."""

from abc import ABC, abstractmethod

from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.planned_operation import PlannedOperation


class RepositoryInterface(ABC):
    """Abstract interface for Budget and PlannedOperation persistence."""

    # Budget methods

    @abstractmethod
    def get_all_budgets(self) -> list[Budget]:
        """Get all budgets.

        Returns:
            List of all budgets ordered by start date.
        """

    @abstractmethod
    def get_budget_by_id(self, budget_id: int) -> Budget | None:
        """Get a budget by its ID.

        Args:
            budget_id: The budget ID to look up.

        Returns:
            The Budget if found, None otherwise.
        """

    @abstractmethod
    def upsert_budget(self, budget: Budget) -> int:
        """Insert or update a budget.

        Args:
            budget: Budget to insert (id <= 0) or update (id > 0).

        Returns:
            The ID of the inserted or updated budget.
        """

    @abstractmethod
    def delete_budget(self, budget_id: int) -> None:
        """Delete a budget by its ID.

        Args:
            budget_id: ID of the budget to delete.
        """

    # PlannedOperation methods

    @abstractmethod
    def get_all_planned_operations(self) -> list[PlannedOperation]:
        """Get all planned operations.

        Returns:
            List of all planned operations ordered by start date.
        """

    @abstractmethod
    def get_planned_operation_by_id(self, op_id: int) -> PlannedOperation | None:
        """Get a planned operation by its ID.

        Args:
            op_id: The planned operation ID to look up.

        Returns:
            The PlannedOperation if found, None otherwise.
        """

    @abstractmethod
    def upsert_planned_operation(self, op: PlannedOperation) -> int:
        """Insert or update a planned operation.

        Args:
            op: PlannedOperation to insert (id <= 0) or update (id > 0).

        Returns:
            The ID of the inserted or updated planned operation.
        """

    @abstractmethod
    def delete_planned_operation(self, op_id: int) -> None:
        """Delete a planned operation by its ID.

        Args:
            op_id: ID of the planned operation to delete.
        """
