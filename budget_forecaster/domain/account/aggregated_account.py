"""Module for aggregating multiple accounts into a single account."""
from datetime import date
from typing import Iterable, NamedTuple

from budget_forecaster.core.types import ImportStats
from budget_forecaster.domain.account.account import Account, AccountParameters
from budget_forecaster.domain.operation.historic_operation import HistoricOperation


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
        self._accounts = tuple(accounts)
        self._aggregated_account = self._aggregate_accounts(aggregated_name, accounts)

    @staticmethod
    def _aggregate_accounts(
        aggregated_name: str, accounts: Iterable[Account]
    ) -> Account:
        balance = 0.0
        currency = ""
        balance_date = date.min
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
        return self._aggregated_account

    @property
    def accounts(self) -> tuple[Account, ...]:
        """Return the accounts."""
        return self._accounts

    @staticmethod
    def update_account(
        current_account: Account, new_account: AccountParameters
    ) -> UpdateResult:
        """Update an existing account with new operations.

        Returns:
            UpdateResult containing the updated account and import statistics.
        """
        # An op is a duplicate if its reference is already known (API/API
        # idempotency) or its content ref matches an existing op. An incoming
        # API op reconciles against an already-stored file op by content; the
        # reverse (file op incoming, API op already stored) is not reconciled.
        existing_refs = {
            operation.source_ref or operation.content_ref
            for operation in current_account.operations
        }
        operations = list(current_account.operations)
        new_count = 0
        for operation in new_account.operations:
            keys = {operation.content_ref}
            if operation.source_ref is not None:
                keys.add(operation.source_ref)
            if keys.isdisjoint(existing_refs):
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
            operation.operation_date for operation in new_account.operations
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
                    if operation.operation_date > current_account.balance_date
                )
            else:
                balance = current_account.balance
        else:
            balance = (
                new_account.balance
                if export_date > current_account.balance_date
                else current_account.balance
            )

        # Adopt the external id the incoming source declares (backfill a
        # pre-existing account, or reflect a config re-identification); keep the
        # stored id when the source declares none.
        external_id = new_account.external_id or current_account.external_id

        # Create the new account
        updated_account = current_account._replace(
            balance=balance,
            balance_date=balance_date,
            operations=tuple(operations),
            external_id=external_id,
        )
        return UpdateResult(account=updated_account, stats=stats)

    def upsert_account(self, account: AccountParameters) -> ImportStats:
        """Add or update an account.

        The target is resolved external-id-first, then by name; a new account is
        created when neither matches.

        Returns:
            ImportStats with the number of new and duplicate operations.
        """
        if (match_index := self._find_match_index(account)) is None:
            self._accounts = (*self._accounts, self._create_account(account))
            total = len(account.operations)
            return ImportStats(
                total_in_file=total,
                new_operations=total,
                duplicates_skipped=0,
            )

        result = self.update_account(self._accounts[match_index], account)
        self._accounts = tuple(
            result.account if index == match_index else current_account
            for index, current_account in enumerate(self._accounts)
        )
        return result.stats

    def _find_match_index(self, account: AccountParameters) -> int | None:
        """Resolve the target sub-account: external id first, then name.

        Matching by id first recognizes a renamed account that kept its id; the
        name fallback keeps file imports (no id) and pre-id databases working.
        """
        if account.external_id is not None:
            for index, current_account in enumerate(self._accounts):
                if current_account.external_id == account.external_id:
                    return index
        for index, current_account in enumerate(self._accounts):
            if current_account.name == account.name:
                return index
        return None

    @staticmethod
    def _create_account(account: AccountParameters) -> Account:
        balance_date = account.balance_date or max(
            op.operation_date for op in account.operations
        )
        return Account(
            name=account.name,
            balance=account.balance or 0.0,
            currency=account.currency,
            balance_date=balance_date,
            operations=account.operations,
            external_id=account.external_id,
        )

    def replace_account(self, new_account: Account) -> None:
        """Replace an account in the aggregated account."""
        self._accounts = tuple(
            new_account if account.name == new_account.name else account
            for account in self._accounts
        )

    def replace_operation(self, new_operation: HistoricOperation) -> None:
        """Replace an operation in the account."""
        for account in self._accounts:
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
