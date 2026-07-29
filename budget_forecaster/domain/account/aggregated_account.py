"""Module for aggregating multiple accounts into a single account."""
from datetime import date
from functools import partial
from typing import Iterable, NamedTuple

from budget_forecaster.core.types import Category, ImportStats, OperationId
from budget_forecaster.domain.account.account import Account, AccountParameters
from budget_forecaster.domain.operation import cross_source
from budget_forecaster.domain.operation.historic_operation import HistoricOperation


class Reconciliation(NamedTuple):
    """A cross-source pair collapsed to one op: the dropped op and the kept one.

    The API op is always the one kept; the file op is dropped. Callers use this
    to move the dropped op's link onto the survivor.
    """

    dropped_id: OperationId
    kept_id: OperationId


def _is_cross_source_duplicate(
    incoming: HistoricOperation, existing: HistoricOperation
) -> bool:
    """Whether a file op and an API op describe the same transaction.

    Falls back to signed amount and a small date window, since the same
    transaction gets a different description (hence a different content ref)
    from each source. Cross-source only: exactly one op must carry a
    source_ref, so two same-source ops sharing amount and date stay distinct.
    """
    if (incoming.source_ref is None) == (existing.source_ref is None):
        return False
    return cross_source.is_amount_date_match(
        cross_source.amount_cents(incoming.amount),
        incoming.operation_date,
        cross_source.amount_cents(existing.amount),
        existing.operation_date,
    )


def _matches_known_ref(operation: HistoricOperation, existing_refs: set[str]) -> bool:
    """Whether the op's reference or content ref already exists (exact dedup)."""
    keys = {operation.content_ref}
    if operation.source_ref is not None:
        keys.add(operation.source_ref)
    return not keys.isdisjoint(existing_refs)


def _reconcile_rank(
    incoming_date: date, existing: tuple[HistoricOperation, ...], index: int
) -> tuple[int, int]:
    """Rank a candidate existing op: nearest date first, lowest id to break ties."""
    candidate = existing[index]
    return (
        cross_source.date_gap(incoming_date, candidate.operation_date),
        candidate.unique_id,
    )


def _kept_api_op(
    file_op: HistoricOperation, api_op: HistoricOperation
) -> HistoricOperation:
    """The API op that survives a reconciliation, adopting the file's category.

    The API source carries no category, so the file's is kept; when the file is
    uncategorized the API's own value stands.
    """
    category = (
        file_op.category
        if file_op.category != Category.UNCATEGORIZED
        else api_op.category
    )
    if category == api_op.category:
        return api_op
    return api_op.replace(category=category)


class _MergeResult(NamedTuple):
    """Merged operations, the reconciled pairs, and the count of genuinely new ops."""

    operations: tuple[HistoricOperation, ...]
    reconciliations: tuple[Reconciliation, ...]
    new_count: int


class UpdateResult(NamedTuple):
    """Result of updating an account with new operations."""

    account: Account
    stats: ImportStats
    reconciliations: tuple[Reconciliation, ...] = ()


class UpsertResult(NamedTuple):
    """Import statistics plus the cross-source pairs collapsed during the upsert."""

    stats: ImportStats
    reconciliations: tuple[Reconciliation, ...] = ()


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
    def _merge_operations(
        existing: tuple[HistoricOperation, ...],
        incoming: tuple[HistoricOperation, ...],
    ) -> _MergeResult:
        """Merge incoming ops into the existing ones, collapsing duplicates.

        An op is a duplicate when its reference or content ref matches an
        existing op (exact key), or when it reconciles with a cross-source op by
        amount and date. A reconciled pair keeps the API op (dropping the file
        op) and the API op adopts the file's category. Cross-source matching is
        one-to-one, so distinct transactions sharing an amount and date are not
        collapsed. Incoming ops are processed in (date, id) order so an
        ambiguous cluster resolves the same way as the purge migration.
        """
        existing_refs = {op.source_ref or op.content_ref for op in existing}
        reconciled: set[int] = set()
        replacements: dict[int, HistoricOperation] = {}
        dropped: set[int] = set()
        appended: list[HistoricOperation] = []
        reconciliations: list[Reconciliation] = []
        new_count = 0

        for operation in sorted(
            incoming, key=lambda op: (op.operation_date, op.unique_id)
        ):
            if _matches_known_ref(operation, existing_refs):
                continue
            candidates = [
                index
                for index, candidate in enumerate(existing)
                if index not in reconciled
                and _is_cross_source_duplicate(operation, candidate)
            ]
            if not candidates:
                appended.append(operation)
                new_count += 1
                continue
            match_index = min(
                candidates,
                key=partial(_reconcile_rank, operation.operation_date, existing),
            )
            reconciled.add(match_index)
            existing_op = existing[match_index]
            if existing_op.source_ref is not None:
                # Existing op is the API record we keep; the incoming file copy
                # only lends its category.
                if (
                    kept := _kept_api_op(file_op=operation, api_op=existing_op)
                ) is not existing_op:
                    replacements[match_index] = kept
                reconciliations.append(
                    Reconciliation(operation.unique_id, existing_op.unique_id)
                )
            else:
                # Existing op is the file copy we drop; the incoming API op wins.
                dropped.add(match_index)
                appended.append(_kept_api_op(file_op=existing_op, api_op=operation))
                reconciliations.append(
                    Reconciliation(existing_op.unique_id, operation.unique_id)
                )

        merged = [
            replacements.get(index, op)
            for index, op in enumerate(existing)
            if index not in dropped
        ]
        merged.extend(appended)
        return _MergeResult(tuple(merged), tuple(reconciliations), new_count)

    @staticmethod
    def _resolve_balance(
        current_account: Account,
        new_account: AccountParameters,
        export_date: date,
    ) -> tuple[float, date]:
        """Resolve the account's balance and its as-of date after a merge.

        An authoritative source (a live API sync) is a fresh snapshot: balance
        and date win together, so a same-day re-sync overwrites a stale value.
        Otherwise the newer date wins, keeping a re-imported older file export
        from regressing the stored balance; a missing balance is reconstructed
        from the new operations.
        """
        if new_account.authoritative and new_account.balance is not None:
            return new_account.balance, export_date

        balance_date = max(current_account.balance_date, export_date)
        if new_account.balance is not None:
            balance = (
                new_account.balance
                if export_date > current_account.balance_date
                else current_account.balance
            )
        elif export_date > current_account.balance_date:
            balance = current_account.balance + sum(
                operation.amount
                for operation in new_account.operations
                if operation.operation_date > current_account.balance_date
            )
        else:
            balance = current_account.balance
        return balance, balance_date

    @staticmethod
    def update_account(
        current_account: Account, new_account: AccountParameters
    ) -> UpdateResult:
        """Update an existing account with new operations.

        Returns:
            UpdateResult with the updated account, import statistics, and the
            cross-source pairs collapsed during the merge.
        """
        merge = AggregatedAccount._merge_operations(
            current_account.operations, new_account.operations
        )

        total_in_file = len(new_account.operations)
        stats = ImportStats(
            total_in_file=total_in_file,
            new_operations=merge.new_count,
            duplicates_skipped=total_in_file - merge.new_count,
        )

        export_date = new_account.balance_date or max(
            operation.operation_date for operation in new_account.operations
        )
        balance, balance_date = AggregatedAccount._resolve_balance(
            current_account, new_account, export_date
        )

        # Adopt the external id the incoming source declares (backfill a
        # pre-existing account, or reflect a config re-identification); keep the
        # stored id when the source declares none.
        external_id = new_account.external_id or current_account.external_id

        # Create the new account
        updated_account = current_account._replace(
            balance=balance,
            balance_date=balance_date,
            operations=merge.operations,
            external_id=external_id,
        )
        return UpdateResult(
            account=updated_account,
            stats=stats,
            reconciliations=merge.reconciliations,
        )

    def upsert_account(self, account: AccountParameters) -> UpsertResult:
        """Add or update an account.

        The target is resolved external-id-first, then by name; a new account is
        created when neither matches.

        Returns:
            UpsertResult with import statistics and the cross-source pairs
            collapsed during the upsert.
        """
        if (match_index := self._find_match_index(account)) is None:
            self._accounts = (*self._accounts, self._create_account(account))
            total = len(account.operations)
            return UpsertResult(
                ImportStats(
                    total_in_file=total,
                    new_operations=total,
                    duplicates_skipped=0,
                )
            )

        result = self.update_account(self._accounts[match_index], account)
        self._accounts = tuple(
            result.account if index == match_index else current_account
            for index, current_account in enumerate(self._accounts)
        )
        return UpsertResult(result.stats, result.reconciliations)

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
