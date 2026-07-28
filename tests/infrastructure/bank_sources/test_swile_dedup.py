"""Swile parser output reconciles against earlier file imports.

A stored French file credit and an English-labeled API credit with the same
amount and date collapse to one, since the parser now carries the transaction
id as the source ref.
"""

from datetime import date

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.account.account import Account, AccountParameters
from budget_forecaster.domain.account.aggregated_account import AggregatedAccount
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.infrastructure.bank_sources.swile.swile_parser import (
    parse_operations,
)
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)


def _api_credit_payload(label: str, value: int, day: str, tx_id: str) -> dict:
    return {
        "items": [
            {
                "name": label,
                "transactions": [
                    {
                        "id": tx_id,
                        "status": "CAPTURED",
                        "payment_method": "Wallets::MealVoucherWallet",
                        "date": f"{day}T13:50:50.073+01:00",
                        "amount": {"value": value, "currency": {"iso_3": "EUR"}},
                    }
                ],
            }
        ]
    }


def test_english_api_credit_reconciles_against_french_file_credit() -> None:
    """An API op with a different label collapses onto the stored file op."""
    french_file_op = HistoricOperation(
        unique_id=1,
        description="Crédit titres-restaurant",
        amount=Amount(198.0),
        category=Category.UNCATEGORIZED,
        operation_date=date(2025, 1, 5),
        source_ref=None,
    )
    current = Account(
        name="swile",
        balance=198.0,
        currency="EUR",
        balance_date=date(2025, 1, 15),
        operations=(french_file_op,),
    )

    parsed = parse_operations(
        _api_credit_payload("Meal voucher credit", 19800, "2025-01-05", "tx-credit"),
        HistoricOperationFactory(last_operation_id=1),
    )

    result = AggregatedAccount.update_account(
        current,
        AccountParameters(
            name="swile",
            balance=198.0,
            currency="EUR",
            balance_date=date(2025, 1, 15),
            operations=parsed,
        ),
    )

    assert result.stats.duplicates_skipped == 1
    assert len(result.account.operations) == 1
    assert result.account.operations[0].source_ref == "tx-credit"
