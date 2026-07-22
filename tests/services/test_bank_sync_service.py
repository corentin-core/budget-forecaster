"""Unit tests for BankSyncService."""

from datetime import date
from unittest.mock import MagicMock

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category, ImportStats
from budget_forecaster.services.bank_sync_service import BankSyncService
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)


def _operation(factory: HistoricOperationFactory, description: str, amount: float):
    return factory.create_operation(
        description=description,
        amount=Amount(amount, "EUR"),
        category=Category.UNCATEGORIZED,
        operation_date=date(2026, 1, 10),
        source_ref=description,
    )


def test_sync_fetches_source_and_merges_into_account() -> None:
    """sync fetches the source and upserts its operations and balance."""
    factory = HistoricOperationFactory(0)
    operations = (
        _operation(factory, "COFFEE", -3.5),
        _operation(factory, "SALARY", 2000.0),
    )

    source = MagicMock()
    source.name = "bnp"
    source.balance = 1500.0
    source.export_date = date(2026, 1, 15)
    source.operations = operations

    persistent_account = MagicMock()
    persistent_account.next_operation_factory.return_value = factory
    stats = ImportStats(total_in_file=2, new_operations=2, duplicates_skipped=0)
    persistent_account.upsert_account.return_value = stats

    service = BankSyncService(persistent_account, source)
    result = service.sync("acc-1", date_from=date(2026, 1, 1))

    source.fetch.assert_called_once_with("acc-1", factory, date(2026, 1, 1))
    account_params = persistent_account.upsert_account.call_args.args[0]
    assert account_params.name == "bnp"
    assert account_params.balance == 1500.0
    assert account_params.currency == "EUR"
    assert account_params.balance_date == date(2026, 1, 15)
    assert account_params.operations == operations
    persistent_account.save.assert_called_once()
    persistent_account.reload.assert_called_once()
    assert result == stats


def test_sync_falls_back_to_today_when_source_has_no_date() -> None:
    """A source without an export date dates the account at today."""
    source = MagicMock()
    source.name = "bnp"
    source.balance = None
    source.export_date = None
    source.operations = ()

    persistent_account = MagicMock()
    persistent_account.next_operation_factory.return_value = HistoricOperationFactory(0)
    persistent_account.upsert_account.return_value = ImportStats(0, 0, 0)

    BankSyncService(persistent_account, source).sync("acc-1")

    account_params = persistent_account.upsert_account.call_args.args[0]
    assert account_params.balance_date == date.today()
