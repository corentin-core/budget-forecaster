"""Tests for the Enable Banking source."""

from datetime import date
from unittest.mock import MagicMock

from budget_forecaster.infrastructure.bank_sources.enable_banking.source import (
    EnableBankingSource,
)
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)


def test_fetch_maps_booked_operations_and_closing_balance() -> None:
    """fetch keeps booked operations, ignores pending, and reads the CLBD balance."""
    client = MagicMock()
    client.get_transactions.return_value = [
        {
            "status": "BOOK",
            "booking_date": "2026-01-10",
            "credit_debit_indicator": "DBIT",
            "transaction_amount": {"currency": "EUR", "amount": "10.00"},
            "remittance_information": ["COFFEE"],
        },
        {
            "status": "PDNG",
            "booking_date": "2026-01-11",
            "credit_debit_indicator": "DBIT",
            "transaction_amount": {"currency": "EUR", "amount": "5.00"},
            "remittance_information": ["PENDING"],
        },
    ]
    client.get_balances.return_value = [
        {"balance_type": "ITAV", "balance_amount": {"amount": "900.00"}},
        {"balance_type": "CLBD", "balance_amount": {"amount": "1000.00"}},
    ]
    source = EnableBankingSource(client, name="bnp")

    source.fetch("acc-1", HistoricOperationFactory(0), date_from=date(2026, 1, 1))

    client.get_transactions.assert_called_once_with("acc-1", date(2026, 1, 1))
    assert len(source.operations) == 1
    assert source.operations[0].description == "COFFEE"
    assert source.operations[0].amount == -10.00
    assert source.operations[0].currency == "EUR"
    assert source.balance == 1000.00
    assert source.export_date == date.today()


def test_fetch_stamps_export_date_from_balance_reference_date() -> None:
    """The CLBD reference_date becomes the balance's as-of date, not today."""
    client = MagicMock()
    client.get_transactions.return_value = []
    client.get_balances.return_value = [
        {
            "balance_type": "CLBD",
            "balance_amount": {"amount": "582.53"},
            "reference_date": "2026-07-27",
        },
    ]
    source = EnableBankingSource(client, name="bnp")

    source.fetch("acc-1", HistoricOperationFactory(0))

    assert source.balance == 582.53
    assert source.export_date == date(2026, 7, 27)


def test_fetch_without_closing_balance_leaves_balance_none() -> None:
    """No CLBD entry yields a None balance and a today() as-of date."""
    client = MagicMock()
    client.get_transactions.return_value = []
    client.get_balances.return_value = [
        {"balance_type": "ITAV", "balance_amount": {"amount": "900.00"}},
    ]
    source = EnableBankingSource(client, name="bnp")

    source.fetch("acc-1", HistoricOperationFactory(0))

    assert source.balance is None
    assert source.export_date == date.today()
