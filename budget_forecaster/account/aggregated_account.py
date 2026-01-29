"""Module for aggregating multiple accounts into a single account."""
from datetime import datetime
from typing import Iterable, NamedTuple

from budget_forecaster.account.account import Account, AccountParameters
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.types import ImportStats


class UpdateResult(NamedTuple):
    """Result of updating an account with new operations."""

    account: Account
    stats: ImportStats


class AggregatedAccount:
    """Aggregate multiple accounts into a single account."""

    def __init__(
        self,
        aggregated_name: str,
        accounts: Iterable[Account],
    ) -> None:
        self.__accounts = tuple(accounts)
        self.__aggregated_account = self.__aggregate_accounts(aggregated_name, accounts)

    @staticmethod
    def __aggregate_accounts(
        aggregated_name: str, accounts: Iterable[Account]
    ) -> Account:
        balance = 0.0
        currency = ""
        balance_date = datetime.min
        operations: list[HistoricOperation] = []

        for account in accounts:
            balance += account.balance
            currency = account.currency
            balance_date = max(balance_date, account.balance_date)
            operations.extend(account.operations)

        return Account(
            name=aggregated_name,
            balance=balance,
            currency=currency,
            balance_date=balance_date,
            operations=tuple(operations),
        )

    @property
    def account(self) -> Account:
        """Return the aggregated account."""
        return self.__aggregated_account

    @property
    def accounts(self) -> tuple[Account, ...]:
        """Return the accounts."""
        return self.__accounts

    @staticmethod
    def update_account(
        current_account: Account, new_account: AccountParameters
    ) -> UpdateResult:
        """Update an existing account with new operations.

        Returns:
            UpdateResult containing the updated account and import statistics.
        """
        # Keep only the operations that are not already in the account
        current_operations_hash = {
            hash((operation.description, operation.amount, operation.date))
            for operation in current_account.operations
        }
        operations = list(current_account.operations)
        new_count = 0
        for operation in new_account.operations:
            if (
                hash((operation.description, operation.amount, operation.date))
                not in current_operations_hash
            ):
                operations.append(operation)
                new_count += 1

        total_in_file = len(new_account.operations)
        stats = ImportStats(
            total_in_file=total_in_file,
            new_operations=new_count,
            duplicates_skipped=total_in_file - new_count,
        )

        # Get balance date
        export_date = new_account.balance_date or max(
            operation.date for operation in new_account.operations
        )
        balance_date = (
            current_account.balance_date
            if current_account.balance_date > export_date
            else export_date
        )

        # Get balance
        if new_account.balance is None:
            if export_date > current_account.balance_date:
                # add the new operations to the current account
                balance = current_account.balance + sum(
                    operation.amount
                    for operation in new_account.operations
                    if operation.date > current_account.balance_date
                )
            else:
                balance = current_account.balance
        else:
            balance = (
                new_account.balance
                if export_date > current_account.balance_date
                else current_account.balance
            )

        # Create the new account
        updated_account = current_account._replace(
            balance=balance,
            balance_date=balance_date,
            operations=tuple(operations),
        )
        return UpdateResult(account=updated_account, stats=stats)

    def upsert_account(self, account: AccountParameters) -> ImportStats:
        """Add or update an account.

        Returns:
            ImportStats with the number of new and duplicate operations.
        """
        updated_accounts: list[Account] = []
        stats: ImportStats | None = None

        for current_account in self.__accounts:
            if current_account.name == account.name:
                result = self.update_account(current_account, account)
                updated_accounts.append(result.account)
                stats = result.stats
            else:
                updated_accounts.append(current_account)

        self.__accounts = tuple(updated_accounts)

        # If no matching account was found, return stats for all operations as new
        if stats is None:
            total = len(account.operations)
            stats = ImportStats(
                total_in_file=total,
                new_operations=total,
                duplicates_skipped=0,
            )

        return stats

    def replace_account(self, new_account: Account) -> None:
        """Replace an account in the aggregated account."""
        self.__accounts = tuple(
            new_account if account.name == new_account.name else account
            for account in self.__accounts
        )

    def replace_operation(self, new_operation: HistoricOperation) -> None:
        """Replace an operation in the account."""
        for account in self.__accounts:
            if any(
                operation.unique_id == new_operation.unique_id
                for operation in account.operations
            ):
                self.replace_account(
                    account._replace(
                        operations=tuple(
                            new_operation
                            if operation.unique_id == new_operation.unique_id
                            else operation
                            for operation in account.operations
                        )
                    )
                )
                return
        raise ValueError(f"Operation with ID {new_operation.unique_id} not found")
