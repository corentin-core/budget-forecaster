"""Module for the PersistentAccount class."""
import pathlib

from budget_forecaster.account.account import Account, AccountParameters
from budget_forecaster.account.aggregated_account import AggregatedAccount
from budget_forecaster.account.sqlite_repository import SqliteRepository
from budget_forecaster.operation_range.historic_operation import HistoricOperation


class PersistentAccount:
    """Saved multiple accounts in a SQLite database and aggregate them as one."""

    def __init__(self, database_path: pathlib.Path) -> None:
        self._repository = SqliteRepository(database_path)
        self._aggregated_account: AggregatedAccount | None = None

    def save(self) -> None:
        """Save the accounts to the database."""
        self._repository.set_aggregated_account_name(self.account.name)
        for acc in self.accounts:
            self._repository.upsert_account(acc)

    def load(self) -> None:
        """Load the accounts from the database."""
        self._repository.initialize()

        if (aggregated_name := self._repository.get_aggregated_account_name()) is None:
            raise FileNotFoundError("No account found")

        accounts = self._repository.get_all_accounts()
        self._aggregated_account = AggregatedAccount(aggregated_name, accounts)

    @property
    def account(self) -> Account:
        """Return the aggregated account."""
        if self._aggregated_account is None:
            raise FileNotFoundError("No account found")
        return self._aggregated_account.account

    @property
    def accounts(self) -> tuple[Account, ...]:
        """Return the individual accounts."""
        if self._aggregated_account is None:
            raise FileNotFoundError("No account found")
        return self._aggregated_account.accounts

    def upsert_account(self, account: AccountParameters) -> None:
        """Add or update an account."""
        if self._aggregated_account is None:
            raise FileNotFoundError("No account found")
        self._aggregated_account.upsert_account(account)

    def replace_account(self, new_account: Account) -> None:
        """Replace an existing account."""
        if self._aggregated_account is None:
            raise FileNotFoundError("No account found")
        self._aggregated_account.replace_account(new_account)

    def replace_operation(self, new_operation: HistoricOperation) -> None:
        """Replace an existing operation."""
        if self._aggregated_account is None:
            raise FileNotFoundError("No account found")
        self._aggregated_account.replace_operation(new_operation)

    @property
    def repository(self) -> SqliteRepository:
        """Return the underlying SQLite repository."""
        return self._repository

    def close(self) -> None:
        """Close the database connection."""
        self._repository.close()
