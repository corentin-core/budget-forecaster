"""Pure parsing of Swile export payloads (operations + wallets).

Shared by the file adapter (reads a downloaded zip) and the OAuth API source
(fetches from Swile's endpoints). Only meal-voucher wallet transactions are
kept: card payments are already deduced from the main bank account and would
double-count.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.exceptions import InvalidExportDataError
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)

_MEAL_VOUCHER_STATUSES = ("AUTHORIZED", "VALIDATED", "CAPTURED")
_MEAL_VOUCHER_PAYMENT_METHOD = "Wallets::MealVoucherWallet"


def parse_balance(
    wallets_payload: dict[str, Any], *, path: Path | None = None
) -> float | None:
    """Return the meal-voucher wallet balance, or None if there is no such wallet.

    path is attached to the error when the balance value is malformed, so the
    file adapter can point at the offending export.
    """
    for wallet in wallets_payload["wallets"]:
        if wallet["type"] == "meal_voucher":
            value = wallet["balance"]["value"]
            if not isinstance(value, (float, int)):
                raise InvalidExportDataError(
                    "The balance field should be a float", path=path
                )
            return value
    return None


def parse_operations(
    operations_payload: dict[str, Any],
    operation_factory: HistoricOperationFactory,
) -> tuple[HistoricOperation, ...]:
    """Build the meal-voucher operations from an operations payload.

    Empty when no meal-voucher transaction is present; the caller decides
    whether that is an error (downloaded export) or expected (periodic sync).
    """
    operations: list[HistoricOperation] = []
    for operation in operations_payload["items"]:
        for transaction in operation["transactions"]:
            if transaction["status"] not in _MEAL_VOUCHER_STATUSES:
                continue
            if transaction["payment_method"] != _MEAL_VOUCHER_PAYMENT_METHOD:
                continue
            amount = transaction["amount"]["value"] / 100.0
            # date has format "2025-01-24T13:50:50.073+01:00"
            op_date = datetime.strptime(transaction["date"][:10], "%Y-%m-%d").date()
            operations.append(
                operation_factory.create_operation(
                    description=operation["name"],
                    amount=Amount(amount, transaction["amount"]["currency"]["iso_3"]),
                    category=Category.UNCATEGORIZED,
                    operation_date=op_date,
                    source_ref=transaction.get("id"),
                )
            )
    return tuple(operations)
