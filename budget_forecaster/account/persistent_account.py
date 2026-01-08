"""Module for the PersistentAccount class."""
import pathlib

from budget_forecaster.account.aggregated_account import AggregatedAccount
from budget_forecaster.account.sqlite_repository import SqliteRepository


class PersistentAccount:
    """Saved multiple accounts in a SQLite database and aggregate them as one."""

    def __init__(self, database_path: pathlib.Path) -> None:
        self._repository = SqliteRepository(database_path)
        self._aggregated_account: AggregatedAccount | None = None

    def save(self) -> None:
        """Save the accounts to the database."""
        self._repository.set_aggregated_account_name(
            self.aggregated_account.account.name
        )
        for account in self.aggregated_account.accounts:
            self._repository.upsert_account(account)

    def load(self) -> None:
        """Load the accounts from the database."""
        self._repository.initialize()

        if (aggregated_name := self._repository.get_aggregated_account_name()) is None:
            raise FileNotFoundError("No account found")

        accounts = self._repository.get_all_accounts()
        self._aggregated_account = AggregatedAccount(aggregated_name, accounts)

    @property
    def aggregated_account(self) -> AggregatedAccount:
        """Return the aggregated account."""
        if self._aggregated_account is None:
            raise FileNotFoundError("No account found")
        return self._aggregated_account

    def close(self) -> None:
        """Close the database connection."""
        self._repository.close()
