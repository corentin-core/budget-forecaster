"""Tests for AggregatedAccount."""

from datetime import date

import pytest

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category, ImportStats
from budget_forecaster.domain.account.account import Account, AccountParameters
from budget_forecaster.domain.account.aggregated_account import AggregatedAccount
from budget_forecaster.domain.operation.historic_operation import HistoricOperation


def _make_operation(
    unique_id: int,
    description: str,
    amount: float,
    operation_date: date,
    category: Category = Category.UNCATEGORIZED,
    source_ref: str | None = None,
) -> HistoricOperation:
    return HistoricOperation(
        unique_id=unique_id,
        description=description,
        amount=Amount(amount),
        category=category,
        operation_date=operation_date,
        source_ref=source_ref,
    )


def _make_account(
    name: str = "BNP",
    balance: float = 1000.0,
    balance_date: date = date(2025, 1, 15),
    operations: tuple[HistoricOperation, ...] = (),
    external_id: str | None = None,
) -> Account:
    return Account(
        name=name,
        balance=balance,
        currency="EUR",
        balance_date=balance_date,
        operations=operations,
        external_id=external_id,
    )


class TestUpdateAccount:
    """Tests for AggregatedAccount.update_account (static method)."""

    def test_new_operations_are_appended(self) -> None:
        """New operations are appended to existing ones."""
        existing_op = _make_operation(1, "OP1", -50.0, date(2025, 1, 10))
        current = _make_account(operations=(existing_op,))

        new_op = _make_operation(2, "OP2", -30.0, date(2025, 1, 12))
        new_params = AccountParameters(
            name="BNP",
            balance=970.0,
            currency="EUR",
            balance_date=date(2025, 1, 15),
            operations=(new_op,),
        )

        result = AggregatedAccount.update_account(current, new_params)

        assert len(result.account.operations) == 2
        assert result.stats.new_operations == 1
        assert result.stats.duplicates_skipped == 0

    def test_duplicate_operations_are_skipped(self) -> None:
        """Operations already present are not duplicated."""
        op = _make_operation(1, "OP1", -50.0, date(2025, 1, 10))
        current = _make_account(operations=(op,))

        new_params = AccountParameters(
            name="BNP",
            balance=950.0,
            currency="EUR",
            balance_date=date(2025, 1, 15),
            operations=(op,),
        )

        result = AggregatedAccount.update_account(current, new_params)

        assert len(result.account.operations) == 1
        assert result.stats.new_operations == 0
        assert result.stats.duplicates_skipped == 1

    def test_balance_updated_when_export_is_newer(self) -> None:
        """Balance is updated when the new export date is more recent."""
        current = _make_account(balance=1000.0, balance_date=date(2025, 1, 10))
        new_params = AccountParameters(
            name="BNP",
            balance=1200.0,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=(),
        )

        result = AggregatedAccount.update_account(current, new_params)

        assert result.account.balance == 1200.0
        assert result.account.balance_date == date(2025, 1, 20)

    def test_balance_kept_when_export_is_older(self) -> None:
        """Balance is kept when the current account is more recent."""
        current = _make_account(balance=1000.0, balance_date=date(2025, 1, 20))
        new_params = AccountParameters(
            name="BNP",
            balance=900.0,
            currency="EUR",
            balance_date=date(2025, 1, 10),
            operations=(),
        )

        result = AggregatedAccount.update_account(current, new_params)

        assert result.account.balance == 1000.0
        assert result.account.balance_date == date(2025, 1, 20)

    def test_balance_none_with_newer_export_computes_from_operations(self) -> None:
        """When balance is None and export is newer, balance is computed."""
        current = _make_account(balance=1000.0, balance_date=date(2025, 1, 10))
        new_op = _make_operation(1, "NEW OP", -50.0, date(2025, 1, 15))
        new_params = AccountParameters(
            name="BNP",
            balance=None,
            currency="EUR",
            balance_date=date(2025, 1, 20),
            operations=(new_op,),
        )

        result = AggregatedAccount.update_account(current, new_params)

        # balance = 1000.0 + (-50.0) since op is after current balance_date
        assert result.account.balance == 950.0

    def test_balance_none_with_older_export_keeps_current(self) -> None:
        """When balance is None and export is older, current balance is kept."""
        current = _make_account(balance=1000.0, balance_date=date(2025, 1, 20))
        new_params = AccountParameters(
            name="BNP",
            balance=None,
            currency="EUR",
            balance_date=date(2025, 1, 10),
            operations=(),
        )

        result = AggregatedAccount.update_account(current, new_params)

        assert result.account.balance == 1000.0

    def test_balance_date_derived_from_operations_when_none(self) -> None:
        """When balance_date is None, it is derived from operations."""
        current = _make_account(balance=1000.0, balance_date=date(2025, 1, 5))
        new_op = _make_operation(1, "OP", -50.0, date(2025, 1, 20))
        new_params = AccountParameters(
            name="BNP",
            balance=1200.0,
            currency="EUR",
            balance_date=None,
            operations=(new_op,),
        )

        result = AggregatedAccount.update_account(current, new_params)

        # balance_date derived from max operation date
        assert result.account.balance_date == date(2025, 1, 20)


class TestDedupWithSourceRef:
    """Tests for the two-level dedup rule (source_ref + content ref)."""

    @staticmethod
    def _params(operations: tuple[HistoricOperation, ...]) -> AccountParameters:
        return AccountParameters(
            name="BNP",
            balance=None,
            currency="EUR",
            balance_date=date(2025, 1, 15),
            operations=operations,
        )

    def test_api_op_deduped_by_reference(self) -> None:
        """An incoming API op whose reference already exists is a duplicate."""
        existing = _make_operation(
            1, "OP", -50.0, date(2025, 1, 10), source_ref="ref-1"
        )
        current = _make_account(operations=(existing,))

        # Same reference, different content: still a duplicate.
        incoming = _make_operation(
            2, "OP RELABELLED", -50.0, date(2025, 1, 11), source_ref="ref-1"
        )

        result = AggregatedAccount.update_account(current, self._params((incoming,)))

        assert result.stats.duplicates_skipped == 1
        assert len(result.account.operations) == 1

    def test_distinct_reference_is_kept(self) -> None:
        """An incoming API op with a new reference is appended."""
        existing = _make_operation(
            1, "OP", -50.0, date(2025, 1, 10), source_ref="ref-1"
        )
        current = _make_account(operations=(existing,))

        incoming = _make_operation(
            2, "OTHER", -20.0, date(2025, 1, 11), source_ref="ref-2"
        )

        result = AggregatedAccount.update_account(current, self._params((incoming,)))

        assert result.stats.new_operations == 1
        assert len(result.account.operations) == 2

    def test_same_day_identical_api_ops_are_kept(self) -> None:
        """Two same-day identical API ops with distinct references are both kept."""
        current = _make_account(operations=())

        op1 = _make_operation(
            1, "MONOPRIX", -12.5, date(2025, 1, 10), source_ref="ref-a"
        )
        op2 = _make_operation(
            2, "MONOPRIX", -12.5, date(2025, 1, 10), source_ref="ref-b"
        )

        result = AggregatedAccount.update_account(current, self._params((op1, op2)))

        assert result.stats.new_operations == 2
        assert len(result.account.operations) == 2

    def test_api_op_reconciled_against_file_op(self) -> None:
        """An incoming API op matching a file op by content is a duplicate."""
        file_op = _make_operation(
            1, "MONOPRIX", -12.5, date(2025, 1, 10)
        )  # no reference
        current = _make_account(operations=(file_op,))

        api_op = _make_operation(
            2, "MONOPRIX", -12.5, date(2025, 1, 10), source_ref="ref-1"
        )

        result = AggregatedAccount.update_account(current, self._params((api_op,)))

        assert result.stats.duplicates_skipped == 1
        assert len(result.account.operations) == 1

    def test_file_ops_dedup_by_content(self) -> None:
        """Reference-less (file) ops keep deduping on content."""
        file_op = _make_operation(1, "LOYER", -800.0, date(2025, 1, 5))
        current = _make_account(operations=(file_op,))

        same = _make_operation(2, "LOYER", -800.0, date(2025, 1, 5))

        result = AggregatedAccount.update_account(current, self._params((same,)))

        assert result.stats.duplicates_skipped == 1
        assert len(result.account.operations) == 1

    def test_file_op_incoming_after_api_op_is_not_reconciled(self) -> None:
        """Accepted limitation: an incoming file op is not matched against an
        existing API op, so re-importing a statement after API sync duplicates."""
        api_op = _make_operation(
            1, "MONOPRIX", -12.5, date(2025, 1, 10), source_ref="ref-1"
        )
        current = _make_account(operations=(api_op,))

        file_op = _make_operation(2, "MONOPRIX", -12.5, date(2025, 1, 10))

        result = AggregatedAccount.update_account(current, self._params((file_op,)))

        assert result.stats.new_operations == 1
        assert len(result.account.operations) == 2


class TestUpsertAccount:
    """Tests for AggregatedAccount.upsert_account."""

    def test_update_existing_account(self) -> None:
        """Upserting an existing account updates it."""
        op = _make_operation(1, "OP", -50.0, date(2025, 1, 10))
        account = _make_account(operations=(op,))
        agg = AggregatedAccount("All", [account])

        new_op = _make_operation(2, "NEW", -30.0, date(2025, 1, 12))
        new_params = AccountParameters(
            name="BNP",
            balance=920.0,
            currency="EUR",
            balance_date=date(2025, 1, 15),
            operations=(new_op,),
        )

        stats = agg.upsert_account(new_params)

        assert stats == ImportStats(
            total_in_file=1, new_operations=1, duplicates_skipped=0
        )
        assert agg.accounts[0].operations == (op, new_op)

    def test_source_ref_is_scoped_per_account(self) -> None:
        """The same reference in another account is not a cross-account duplicate."""
        existing = _make_operation(
            1, "OP", -50.0, date(2025, 1, 10), source_ref="ref-1"
        )
        bnp = _make_account(name="BNP", operations=(existing,))
        agg = AggregatedAccount("All", [bnp])

        same_ref_other_account = _make_operation(
            2, "OTHER", -20.0, date(2025, 1, 12), source_ref="ref-1"
        )
        params = AccountParameters(
            name="Swile",
            balance=500.0,
            currency="EUR",
            balance_date=date(2025, 1, 15),
            operations=(same_ref_other_account,),
        )

        stats = agg.upsert_account(params)

        assert stats == ImportStats(
            total_in_file=1, new_operations=1, duplicates_skipped=0
        )
        assert len(agg.accounts) == 2

    def test_upsert_new_account(self) -> None:
        """Upserting a non-existing account name creates it with all operations."""
        account = _make_account(name="BNP")
        agg = AggregatedAccount("All", [account])

        new_op = _make_operation(1, "OP", -50.0, date(2025, 1, 10))
        new_params = AccountParameters(
            name="Swile",
            balance=500.0,
            currency="EUR",
            balance_date=date(2025, 1, 15),
            operations=(new_op,),
        )

        stats = agg.upsert_account(new_params)

        assert stats == ImportStats(
            total_in_file=1, new_operations=1, duplicates_skipped=0
        )
        # Regression: account must actually be created with its operations
        assert len(agg.accounts) == 2
        expected_swile = Account(
            name="Swile",
            balance=500.0,
            currency="EUR",
            balance_date=date(2025, 1, 15),
            operations=(new_op,),
        )
        assert agg.accounts[1] == expected_swile

    def test_upsert_on_empty_aggregated_account(self) -> None:
        """Upserting into an aggregated account with no sub-accounts creates one."""
        agg = AggregatedAccount("All", [])

        new_op = _make_operation(1, "SALARY", 3000.0, date(2025, 1, 28))
        new_params = AccountParameters(
            name="bnp",
            balance=3000.0,
            currency="EUR",
            balance_date=date(2025, 1, 29),
            operations=(new_op,),
        )

        stats = agg.upsert_account(new_params)

        assert stats == ImportStats(
            total_in_file=1, new_operations=1, duplicates_skipped=0
        )
        expected = Account(
            name="bnp",
            balance=3000.0,
            currency="EUR",
            balance_date=date(2025, 1, 29),
            operations=(new_op,),
        )
        assert agg.accounts == (expected,)

    def test_upsert_new_account_then_update(self) -> None:
        """First import creates the account, second import deduplicates."""
        agg = AggregatedAccount("All", [])

        # First import — creates the account
        op1 = _make_operation(1, "RENT", -950.0, date(2025, 1, 5))
        params1 = AccountParameters(
            name="bnp",
            balance=1000.0,
            currency="EUR",
            balance_date=date(2025, 1, 10),
            operations=(op1,),
        )
        stats1 = agg.upsert_account(params1)
        assert stats1 == ImportStats(
            total_in_file=1, new_operations=1, duplicates_skipped=0
        )
        assert len(agg.accounts) == 1

        # Second import — same operation + one new
        op2 = _make_operation(2, "INTERNET", -35.0, date(2025, 1, 8))
        params2 = AccountParameters(
            name="bnp",
            balance=965.0,
            currency="EUR",
            balance_date=date(2025, 1, 15),
            operations=(op1, op2),
        )
        stats2 = agg.upsert_account(params2)
        assert stats2 == ImportStats(
            total_in_file=2, new_operations=1, duplicates_skipped=1
        )
        assert len(agg.accounts) == 1
        assert agg.accounts[0].operations == (op1, op2)


class TestReplaceOperation:
    """Tests for AggregatedAccount.replace_operation."""

    def test_replaces_existing_operation(self) -> None:
        """Replacing an existing operation updates it in the correct account."""
        op = _make_operation(1, "OLD", -50.0, date(2025, 1, 10))
        account = _make_account(operations=(op,))
        agg = AggregatedAccount("All", [account])

        new_op = _make_operation(1, "NEW", -50.0, date(2025, 1, 10), Category.GROCERIES)
        agg.replace_operation(new_op)

        updated_op = agg.accounts[0].operations[0]
        assert updated_op == new_op

    def test_raises_for_unknown_operation_id(self) -> None:
        """Replacing a non-existing operation raises ValueError."""
        account = _make_account()
        agg = AggregatedAccount("All", [account])

        unknown_op = _make_operation(999, "UNKNOWN", -10.0, date(2025, 1, 1))
        with pytest.raises(ValueError, match="not found"):
            agg.replace_operation(unknown_op)

    def test_replace_account_updates_matching(self) -> None:
        """Replacing an account updates the matching one by name."""
        account = _make_account(name="BNP", balance=1000.0)
        agg = AggregatedAccount("All", [account])

        updated = _make_account(name="BNP", balance=2000.0)
        agg.replace_account(updated)

        assert agg.accounts[0].balance == 2000.0


class TestAggregation:
    """Tests for AggregatedAccount constructor and properties."""

    def test_aggregates_balances_and_operations(self) -> None:
        """Aggregation sums balances and merges operations."""
        op1 = _make_operation(1, "OP1", -50.0, date(2025, 1, 10))
        op2 = _make_operation(2, "OP2", -30.0, date(2025, 1, 12))
        acc1 = _make_account(name="BNP", balance=1000.0, operations=(op1,))
        acc2 = _make_account(name="Swile", balance=500.0, operations=(op2,))

        agg = AggregatedAccount("All", [acc1, acc2])

        assert agg.account.balance == 1500.0
        assert len(agg.account.operations) == 2
        assert agg.account.name == "All"

    def test_balance_date_is_max_of_accounts(self) -> None:
        """Aggregated balance_date is the max across accounts."""
        acc1 = _make_account(name="BNP", balance_date=date(2025, 1, 10))
        acc2 = _make_account(name="Swile", balance_date=date(2025, 1, 20))

        agg = AggregatedAccount("All", [acc1, acc2])

        assert agg.account.balance_date == date(2025, 1, 20)


class TestUpsertResolution:
    """Tests for external-id-first / name-fallback account resolution."""

    @staticmethod
    def _params(
        name: str = "bnp",
        external_id: str | None = None,
        operations: tuple[HistoricOperation, ...] = (),
    ) -> AccountParameters:
        return AccountParameters(
            name=name,
            balance=None,
            currency="EUR",
            balance_date=date(2025, 2, 1),
            operations=operations,
            external_id=external_id,
        )

    def test_matches_by_external_id_over_name(self) -> None:
        """An account matching by external id wins over a name collision."""
        by_name = _make_account(name="bnp", external_id=None)
        by_id = _make_account(name="other", external_id="FR76")
        agg = AggregatedAccount("All", [by_name, by_id])

        op = _make_operation(1, "OP", -10.0, date(2025, 2, 2), source_ref="r1")
        agg.upsert_account(
            self._params(name="bnp", external_id="FR76", operations=(op,))
        )

        # The op lands on the external-id match, not the name match.
        matched = next(a for a in agg.accounts if a.external_id == "FR76")
        assert len(matched.operations) == 1
        assert next(a for a in agg.accounts if a.name == "bnp").operations == ()

    def test_falls_back_to_name_and_backfills_external_id(self) -> None:
        """A pre-existing account matched by name is stamped with the id."""
        existing = _make_account(name="bnp", external_id=None)
        agg = AggregatedAccount("All", [existing])

        op = _make_operation(1, "OP", -10.0, date(2025, 2, 2), source_ref="r1")
        agg.upsert_account(
            self._params(name="bnp", external_id="FR76", operations=(op,))
        )

        assert len(agg.accounts) == 1
        assert agg.accounts[0].external_id == "FR76"
        assert len(agg.accounts[0].operations) == 1

    def test_distinct_external_ids_create_separate_accounts(self) -> None:
        """Two ids under the same name stay distinct sub-accounts."""
        first = _make_account(name="bnp", external_id="FR76")
        agg = AggregatedAccount("All", [first])

        op = _make_operation(1, "OP", -10.0, date(2025, 2, 2), source_ref="r1")
        agg.upsert_account(
            self._params(name="bnp", external_id="FR99", operations=(op,))
        )

        assert {a.external_id for a in agg.accounts} == {"FR76", "FR99"}

    def test_undeclared_account_matches_by_name(self) -> None:
        """An incoming account with no id merges into the name match."""
        existing = _make_account(name="bnp", external_id="FR76")
        agg = AggregatedAccount("All", [existing])

        op = _make_operation(1, "OP", -10.0, date(2025, 2, 2), source_ref="r1")
        agg.upsert_account(self._params(name="bnp", external_id=None, operations=(op,)))

        assert len(agg.accounts) == 1
        assert agg.accounts[0].external_id == "FR76"
        assert len(agg.accounts[0].operations) == 1
