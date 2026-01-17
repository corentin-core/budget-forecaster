"""Abstract interfaces for repository operations.

This module defines separate interfaces for each entity following the
Interface Segregation Principle (ISP), plus a facade interface that
combines them all.
"""

from abc import ABC, abstractmethod

from budget_forecaster.account.account import Account
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.planned_operation import PlannedOperation


class BudgetRepositoryInterface(ABC):
    """Interface for Budget persistence operations."""

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
            budget: Budget to insert (id is None) or update (id is not None).

        Returns:
            The ID of the inserted or updated budget.
        """

    @abstractmethod
    def delete_budget(self, budget_id: int) -> None:
        """Delete a budget by its ID.

        Args:
            budget_id: ID of the budget to delete.
        """


class PlannedOperationRepositoryInterface(ABC):
    """Interface for PlannedOperation persistence operations."""

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
            op: PlannedOperation to insert (id is None) or update (id is not None).

        Returns:
            The ID of the inserted or updated planned operation.
        """

    @abstractmethod
    def delete_planned_operation(self, op_id: int) -> None:
        """Delete a planned operation by its ID.

        Args:
            op_id: ID of the planned operation to delete.
        """


class AccountRepositoryInterface(ABC):
    """Interface for Account persistence operations."""

    @abstractmethod
    def get_aggregated_account_name(self) -> str | None:
        """Get the aggregated account name.

        Returns:
            The aggregated account name, or None if not set.
        """

    @abstractmethod
    def set_aggregated_account_name(self, name: str) -> None:
        """Set or update the aggregated account name.

        Args:
            name: The name to set for the aggregated account.
        """

    @abstractmethod
    def get_all_accounts(self) -> list[Account]:
        """Get all accounts with their operations.

        Returns:
            List of all accounts.
        """

    @abstractmethod
    def get_account_by_name(self, name: str) -> Account | None:
        """Get an account by name.

        Args:
            name: The account name to look up.

        Returns:
            The Account if found, None otherwise.
        """

    @abstractmethod
    def upsert_account(self, account: Account) -> None:
        """Insert or update an account.

        Args:
            account: The account to insert or update.
        """


class OperationRepositoryInterface(ABC):
    """Interface for HistoricOperation persistence operations."""

    @abstractmethod
    def update_operation(self, operation: HistoricOperation) -> None:
        """Update a single operation.

        Args:
            operation: The operation to update.
        """

    @abstractmethod
    def operation_exists(self, unique_id: int) -> bool:
        """Check if an operation exists.

        Args:
            unique_id: The unique ID of the operation.

        Returns:
            True if the operation exists, False otherwise.
        """


class RepositoryInterface(
    BudgetRepositoryInterface,
    PlannedOperationRepositoryInterface,
    AccountRepositoryInterface,
    OperationRepositoryInterface,
    ABC,
):
    """Facade interface combining all repository operations.

    This interface aggregates all entity-specific interfaces and adds
    lifecycle methods for repository initialization and cleanup.
    """

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the repository.

        This method should be called before any other operations.
        It sets up the underlying storage (e.g., database schema).
        """

    @abstractmethod
    def close(self) -> None:
        """Close the repository and release resources.

        This method should be called when the repository is no longer needed.
        """
