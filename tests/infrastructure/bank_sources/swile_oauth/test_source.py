"""The API source fetches, parses and exposes operations and balance."""

from datetime import date
from unittest.mock import MagicMock

from budget_forecaster.infrastructure.bank_sources.swile_oauth.source import (
    SwileApiSource,
)
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)

_OPERATIONS = {
    "items": [
        {
            "name": "Restaurant",
            "transactions": [
                {
                    "status": "CAPTURED",
                    "payment_method": "Wallets::MealVoucherWallet",
                    "date": "2025-01-15T13:50:50.073+01:00",
                    "amount": {"value": -2500, "currency": {"iso_3": "EUR"}},
                }
            ],
        }
    ]
}
_WALLETS = {"wallets": [{"type": "meal_voucher", "balance": {"value": 100.0}}]}


def test_fetch_populates_operations_balance_and_date() -> None:
    """fetch fills operations, balance, and export date from the payloads."""
    client = MagicMock()
    client.get_operations.return_value = _OPERATIONS
    client.get_wallets.return_value = _WALLETS
    source = SwileApiSource(client, "acc-token", name="swile")

    source.fetch("swile", HistoricOperationFactory(last_operation_id=0))

    assert [op.amount for op in source.operations] == [-25.0]
    assert source.balance == 100.0
    assert source.export_date == date.today()


def test_fetch_uses_the_injected_access_token() -> None:
    """The stored access token is passed to both endpoint calls."""
    client = MagicMock()
    client.get_operations.return_value = _OPERATIONS
    client.get_wallets.return_value = _WALLETS
    source = SwileApiSource(client, "acc-token", name="swile")

    source.fetch("swile", HistoricOperationFactory(last_operation_id=0))

    client.get_operations.assert_called_once_with("acc-token")
    client.get_wallets.assert_called_once_with("acc-token")
