"""Abstract interfaces for repository operations.

This module defines separate interfaces for each entity following the
Interface Segregation Principle (ISP), plus a facade interface that
combines them all.
"""

from abc import ABC, abstractmethod
from typing import Self

from budget_forecaster.core.types import LinkType, OperationId, TargetId
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation


class BudgetRepositoryInterface(ABC):
    """Interface for Budget persistence operations."""

    @abstractmethod
    def get_all_budgets(self) -> tuple[Budget, ...]:
        """Get all budgets.

        Returns:
            List of all budgets ordered by start date.
        """

    @abstractmethod
    def get_budget_by_id(self, budget_id: int) -> Budget:
        """Get a budget by its ID.

        Args:
            budget_id: The budget ID to look up.

        Returns:
            The Budget.

        Raises:
            BudgetNotFoundError: If no budget with the given ID exists.
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
    def get_all_planned_operations(self) -> tuple[PlannedOperation, ...]:
        """Get all planned operations.

        Returns:
            List of all planned operations ordered by start date.
        """

    @abstractmethod
    def get_planned_operation_by_id(self, op_id: int) -> PlannedOperation:
        """Get a planned operation by its ID.

        Args:
            op_id: The planned operation ID to look up.

        Returns:
            The PlannedOperation.

        Raises:
            PlannedOperationNotFoundError: If no planned operation with the given ID exists.
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
    def get_all_accounts(self) -> tuple[Account, ...]:
        """Get all accounts with their operations.

        Returns:
            List of all accounts.
        """

    @abstractmethod
    def get_account_by_name(self, name: str) -> Account:
        """Get an account by name.

        Args:
            name: The account name to look up.

        Returns:
            The Account.

        Raises:
            AccountNotFoundError: If no account with the given name exists.
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


class OperationLinkRepositoryInterface(ABC):
    """Interface for OperationLink persistence operations."""

    @abstractmethod
    def get_link_for_operation(
        self, operation_unique_id: OperationId
    ) -> OperationLink | None:
        """Get the link for a historic operation, if any.

        Args:
            operation_unique_id: The unique ID of the operation.

        Returns:
            The OperationLink if found, None otherwise.
        """

    @abstractmethod
    def get_all_links(self) -> tuple[OperationLink, ...]:
        """Get all operation links.

        Returns:
            Tuple of all OperationLinks in the repository.
        """

    @abstractmethod
    def get_links_for_planned_operation(
        self, planned_op_id: int
    ) -> tuple[OperationLink, ...]:
        """Get all links targeting a planned operation.

        Args:
            planned_op_id: The ID of the planned operation.

        Returns:
            Tuple of OperationLinks targeting this planned operation.
        """

    @abstractmethod
    def get_links_for_budget(self, budget_id: int) -> tuple[OperationLink, ...]:
        """Get all links targeting a budget.

        Args:
            budget_id: The ID of the budget.

        Returns:
            Tuple of OperationLinks targeting this budget.
        """

    @abstractmethod
    def upsert_link(self, link: OperationLink) -> None:
        """Insert or replace a link.

        If the operation already has a link, it is replaced with the new one.

        Args:
            link: The OperationLink to insert or replace.
        """

    @abstractmethod
    def delete_link(self, operation_unique_id: OperationId) -> None:
        """Delete the link for an operation.

        Args:
            operation_unique_id: The unique ID of the operation.
        """

    @abstractmethod
    def delete_automatic_links_for_target(
        self, target_type: LinkType, target_id: TargetId
    ) -> None:
        """Delete all automatic links for a given target.

        Used for recalculation when a planned operation or budget is modified.

        Args:
            target_type: The type of target (planned operation or budget).
            target_id: The ID of the target.
        """

    @abstractmethod
    def delete_links_for_target(
        self, target_type: LinkType, target_id: TargetId
    ) -> None:
        """Delete all links for a given target (both manual and automatic).

        Used for cascade delete when a planned operation or budget is deleted.

        Args:
            target_type: The type of target (planned operation or budget).
            target_id: The ID of the target.
        """


class RepositoryInterface(
    BudgetRepositoryInterface,
    PlannedOperationRepositoryInterface,
    AccountRepositoryInterface,
    OperationRepositoryInterface,
    OperationLinkRepositoryInterface,
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

    @abstractmethod
    def __enter__(self) -> Self:
        """Enter the context manager.

        Initializes the repository and returns it.
        """

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit the context manager.

        Closes the repository.
        """
