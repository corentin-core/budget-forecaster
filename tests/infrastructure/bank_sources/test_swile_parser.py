"""The Swile parser turns operations/wallets payloads into ops and balance."""

from datetime import date

import pytest

from budget_forecaster.core.types import Category
from budget_forecaster.exceptions import InvalidExportDataError
from budget_forecaster.infrastructure.bank_sources.swile.swile_parser import (
    parse_balance,
    parse_operations,
)
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)


def _meal_voucher(
    name: str, value: int, day: str, status: str = "CAPTURED", tx_id: str = "tx-1"
) -> dict:
    return {
        "name": name,
        "transactions": [
            {
                "id": tx_id,
                "status": status,
                "payment_method": "Wallets::MealVoucherWallet",
                "date": f"{day}T13:50:50.073+01:00",
                "amount": {"value": value, "currency": {"iso_3": "EUR"}},
            }
        ],
    }


@pytest.fixture(name="factory")
def factory_fixture() -> HistoricOperationFactory:
    """A factory starting operation ids at 1."""
    return HistoricOperationFactory(last_operation_id=0)


def test_parse_operations_keeps_meal_vouchers(
    factory: HistoricOperationFactory,
) -> None:
    """Meal-voucher transactions become operations with euro amounts."""
    payload = {
        "items": [
            _meal_voucher("Restaurant", -2500, "2025-01-15"),
            _meal_voucher("Boulangerie", -800, "2025-01-16"),
        ]
    }

    operations = parse_operations(payload, factory)

    assert [op.amount for op in operations] == [-25.0, -8.0]
    assert {op.description for op in operations} == {"Restaurant", "Boulangerie"}
    assert all(op.category == Category.UNCATEGORIZED for op in operations)
    assert operations[1].operation_date == date(2025, 1, 16)


def test_parse_operations_carries_transaction_id_as_source_ref(
    factory: HistoricOperationFactory,
) -> None:
    """The transaction id becomes the source ref, so dedup survives label drift."""
    payload = {
        "items": [_meal_voucher("Restaurant", -2500, "2025-01-15", tx_id="tx-9")]
    }

    operations = parse_operations(payload, factory)

    assert operations[0].source_ref == "tx-9"


def test_parse_operations_source_ref_none_without_transaction_id(
    factory: HistoricOperationFactory,
) -> None:
    """A transaction with no id falls back to a content-based dedup key."""
    transaction = {
        "status": "CAPTURED",
        "payment_method": "Wallets::MealVoucherWallet",
        "date": "2025-01-15T13:50:50.073+01:00",
        "amount": {"value": -2500, "currency": {"iso_3": "EUR"}},
    }
    payload = {"items": [{"name": "Restaurant", "transactions": [transaction]}]}

    assert parse_operations(payload, factory)[0].source_ref is None


def test_parse_operations_skips_non_meal_voucher_and_declined(
    factory: HistoricOperationFactory,
) -> None:
    """Card payments and declined transactions are dropped."""
    payload = {
        "items": [
            {
                "name": "Mixed",
                "transactions": [
                    {
                        "status": "CAPTURED",
                        "payment_method": "Wallets::CreditCardWallet",
                        "date": "2025-01-15T00:00:00.000+01:00",
                        "amount": {"value": -500, "currency": {"iso_3": "EUR"}},
                    },
                    {
                        "status": "DECLINED",
                        "payment_method": "Wallets::MealVoucherWallet",
                        "date": "2025-01-15T00:00:00.000+01:00",
                        "amount": {"value": -900, "currency": {"iso_3": "EUR"}},
                    },
                ],
            }
        ]
    }

    assert not parse_operations(payload, factory)


def test_parse_balance_returns_meal_voucher_wallet() -> None:
    """The meal-voucher wallet balance is returned as-is."""
    payload = {
        "wallets": [
            {"type": "gift", "balance": {"value": 10.0}},
            {"type": "meal_voucher", "balance": {"value": 125.5}},
        ]
    }
    assert parse_balance(payload) == 125.5


def test_parse_balance_none_without_meal_voucher_wallet() -> None:
    """No meal-voucher wallet yields None."""
    payload = {"wallets": [{"type": "gift", "balance": {"value": 10.0}}]}
    assert parse_balance(payload) is None


def test_parse_balance_rejects_non_numeric_value() -> None:
    """A non-numeric balance value raises InvalidExportDataError."""
    payload = {"wallets": [{"type": "meal_voucher", "balance": {"value": "bad"}}]}
    with pytest.raises(InvalidExportDataError, match="balance field should be a float"):
        parse_balance(payload)
