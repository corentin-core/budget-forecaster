"""Module for the PersistentAccount class."""

from budget_forecaster.core.types import ImportStats
from budget_forecaster.domain.account.account import Account, AccountParameters
from budget_forecaster.domain.account.aggregated_account import AggregatedAccount
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.exceptions import AccountNotLoadedError
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)


class PersistentAccount:
    """Manage multiple accounts in a repository and aggregate them as one."""

    def __init__(self, repository: RepositoryInterface) -> None:
        """Initialize with a repository.

        Args:
            repository: The repository for data persistence.
        """
        self._repository = repository
        self._aggregated_account: AggregatedAccount | None = None

    def save(self) -> None:
        """Save the accounts to the repository."""
        self._repository.set_aggregated_account_name(self.account.name)
        for acc in self.accounts:
            self._repository.upsert_account(acc)

    def load(self) -> None:
        """Load the accounts from the repository."""
        self._repository.initialize()

        if (aggregated_name := self._repository.get_aggregated_account_name()) is None:
            raise AccountNotLoadedError()

        accounts = self._repository.get_all_accounts()
        self._aggregated_account = AggregatedAccount(aggregated_name, accounts)

    @property
    def account(self) -> Account:
        """Return the aggregated account."""
        if self._aggregated_account is None:
            raise AccountNotLoadedError()
        return self._aggregated_account.account

    @property
    def accounts(self) -> tuple[Account, ...]:
        """Return the individual accounts."""
        if self._aggregated_account is None:
            raise AccountNotLoadedError()
        return self._aggregated_account.accounts

    def upsert_account(self, account: AccountParameters) -> ImportStats:
        """Add or update an account.

        Returns:
            ImportStats with the number of new and duplicate operations.
        """
        if self._aggregated_account is None:
            raise AccountNotLoadedError()
        return self._aggregated_account.upsert_account(account)

    def replace_account(self, new_account: Account) -> None:
        """Replace an existing account."""
        if self._aggregated_account is None:
            raise AccountNotLoadedError()
        self._aggregated_account.replace_account(new_account)

    def replace_operation(self, new_operation: HistoricOperation) -> None:
        """Replace an existing operation."""
        if self._aggregated_account is None:
            raise AccountNotLoadedError()
        self._aggregated_account.replace_operation(new_operation)

    @property
    def repository(self) -> RepositoryInterface:
        """Return the underlying repository."""
        return self._repository

    def close(self) -> None:
        """Close the repository connection."""
        self._repository.close()
