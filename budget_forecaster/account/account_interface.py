"""Module defining the AccountInterface protocol."""
# pylint: disable=unnecessary-ellipsis
from typing import Protocol

from budget_forecaster.account.account import Account, AccountParameters
from budget_forecaster.operation_range.historic_operation import HistoricOperation


class AccountInterface(Protocol):
    """Common interface for account managers."""

    @property
    def account(self) -> Account:
        """Return the aggregated account."""
        ...

    @property
    def accounts(self) -> tuple[Account, ...]:
        """Return the individual accounts."""
        ...

    def upsert_account(self, account: AccountParameters) -> None:
        """Add or update an account."""
        ...

    def replace_account(self, new_account: Account) -> None:
        """Replace an existing account."""
        ...

    def replace_operation(self, new_operation: HistoricOperation) -> None:
        """Replace an existing operation."""
        ...
