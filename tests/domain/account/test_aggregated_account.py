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
) -> HistoricOperation:
    return HistoricOperation(
        unique_id=unique_id,
        description=description,
        amount=Amount(amount),
        category=category,
        operation_date=operation_date,
    )


def _make_account(
    name: str = "BNP",
    balance: float = 1000.0,
    balance_date: date = date(2025, 1, 15),
    operations: tuple[HistoricOperation, ...] = (),
) -> Account:
    return Account(
        name=name,
        balance=balance,
        currency="EUR",
        balance_date=balance_date,
        operations=operations,
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
