"""Module for aggregating multiple accounts into a single account."""
from datetime import datetime
from typing import Iterable

from budget_forecaster.account.account import Account, AccountParameters
from budget_forecaster.operation_range.historic_operation import HistoricOperation


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
    ) -> Account:
        """Update an existing account with a new one."""
        # Keep only the operations that are not already in the account
        current_operations_hash = {
            hash((operation.description, operation.amount, operation.date))
            for operation in current_account.operations
        }
        operations = list(current_account.operations)
        for operation in new_account.operations:
            if (
                hash((operation.description, operation.amount, operation.date))
                not in current_operations_hash
            ):
                operations.append(operation)

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
        return current_account._replace(
            balance=balance,
            balance_date=balance_date,
            operations=tuple(operations),
        )

    def upsert_account(self, account: AccountParameters) -> None:
        """Add or update an account."""
        # check if the account already exists and update it if it does
        self.__accounts = tuple(
            self.update_account(current_account, account)
            if current_account.name == account.name
            else current_account
            for current_account in self.__accounts
        )

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
