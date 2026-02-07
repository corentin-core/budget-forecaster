"""Module defining the AccountInterface protocol."""
from typing import Protocol

from budget_forecaster.core.types import ImportStats
from budget_forecaster.domain.account.account import Account, AccountParameters
from budget_forecaster.domain.operation.historic_operation import HistoricOperation


class AccountInterface(Protocol):
    """Common interface for account managers."""

    @property
    def account(self) -> Account:
        """Return the aggregated account."""

    @property
    def accounts(self) -> tuple[Account, ...]:
        """Return the individual accounts."""

    def upsert_account(self, account: AccountParameters) -> ImportStats:
        """Add or update an account.

        Returns:
            ImportStats with the number of new and duplicate operations.
        """

    def replace_account(self, new_account: Account) -> None:
        """Replace an existing account."""

    def replace_operation(self, new_operation: HistoricOperation) -> None:
        """Replace an existing operation."""
