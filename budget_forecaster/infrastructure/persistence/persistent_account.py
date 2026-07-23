"""Module for the PersistentAccount class."""

import logging

from budget_forecaster.core.types import ImportStats
from budget_forecaster.domain.account.account import Account, AccountParameters
from budget_forecaster.domain.account.aggregated_account import (
    AggregatedAccount,
    Reconciliation,
)
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.exceptions import AccountNotLoadedError
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)

logger = logging.getLogger(__name__)


class PersistentAccount:
    """Manage multiple accounts in a repository and aggregate them as one.

    The repository must be initialized before constructing this object.
    Raises AccountNotLoadedError if the repository contains no account data.
    """

    def __init__(self, repository: RepositoryInterface) -> None:
        """Initialize and load accounts from an already-initialized repository.

        Args:
            repository: The repository for data persistence (must be initialized).

        Raises:
            AccountNotLoadedError: If no account data exists in the repository.
        """
        self._repository = repository
        self._aggregated_account = self._load()

    def _load(self) -> AggregatedAccount:
        """Load accounts from the repository.

        Returns:
            The aggregated account loaded from the repository.

        Raises:
            AccountNotLoadedError: If no account data exists in the repository.
        """
        if (aggregated_name := self._repository.get_aggregated_account_name()) is None:
            raise AccountNotLoadedError()

        accounts = self._repository.get_all_accounts()
        return AggregatedAccount(aggregated_name, accounts)

    def next_operation_factory(self) -> HistoricOperationFactory:
        """Create an operation factory seeded past the highest existing id.

        Keeps operation ids unique whatever the source (file import, API sync).
        """
        last_id = max((op.unique_id for op in self.account.operations), default=0)
        return HistoricOperationFactory(last_id)

    def save(self) -> None:
        """Save the accounts to the repository."""
        self._repository.set_aggregated_account_name(self.account.name)
        for acc in self.accounts:
            self._repository.upsert_account(acc)

    def reload(self) -> None:
        """Reload the accounts from the repository."""
        self._aggregated_account = self._load()

    @property
    def account(self) -> Account:
        """Return the aggregated account."""
        return self._aggregated_account.account

    @property
    def accounts(self) -> tuple[Account, ...]:
        """Return the individual accounts."""
        return self._aggregated_account.accounts

    def upsert_account(self, account: AccountParameters) -> ImportStats:
        """Add or update an account.

        Moves the link off each file op collapsed into an API op onto the
        surviving API op, so a cross-source reconciliation keeps the forecast's
        actual attributions and never loses a user-set link.

        Returns:
            ImportStats with the number of new and duplicate operations.
        """
        result = self._aggregated_account.upsert_account(account)
        for reconciliation in result.reconciliations:
            self._move_link(reconciliation)
        return result.stats

    def _move_link(self, reconciliation: Reconciliation) -> None:
        """Move the dropped op's link onto the surviving API op.

        Both ops describe the same transaction, so the link stays valid. A
        manual link already on the survivor wins; otherwise the dropped op's
        link overwrites whatever the survivor had.
        """
        if (
            link := self._repository.get_link_for_operation(reconciliation.dropped_id)
        ) is None:
            return
        survivor = self._repository.get_link_for_operation(reconciliation.kept_id)
        if survivor is not None and survivor.is_manual:
            if link.is_manual:
                logger.warning(
                    "Discarding manual link on op %d: survivor op %d is already "
                    "manually linked",
                    reconciliation.dropped_id,
                    reconciliation.kept_id,
                )
            self._repository.delete_link(reconciliation.dropped_id)
            return
        self._repository.delete_link(reconciliation.dropped_id)
        self._repository.upsert_link(
            link._replace(operation_unique_id=reconciliation.kept_id, link_id=None)
        )

    def replace_account(self, new_account: Account) -> None:
        """Replace an existing account."""
        self._aggregated_account.replace_account(new_account)

    def replace_operation(self, new_operation: HistoricOperation) -> None:
        """Replace an existing operation."""
        self._aggregated_account.replace_operation(new_operation)

    @property
    def repository(self) -> RepositoryInterface:
        """Return the underlying repository."""
        return self._repository

    def close(self) -> None:
        """Close the repository connection."""
        self._repository.close()
