"""Mapping from Enable Banking payloads to domain objects."""

from datetime import date
from typing import Any

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)

# Transaction status: only booked transactions are imported.
_BOOKED = "BOOK"

# Balance type: closing booked (solde comptable clôturé).
_CLOSING_BOOKED = "CLBD"


def map_transaction(
    raw: dict[str, Any], operation_factory: HistoricOperationFactory
) -> HistoricOperation | None:
    """Map one Enable Banking transaction to a HistoricOperation.

    Returns None for non-booked transactions, which are skipped.
    """
    if raw.get("status") != _BOOKED:
        return None
    return operation_factory.create_operation(
        description=_remittance_description(raw.get("remittance_information")),
        amount=_signed_amount(raw),
        category=Category.UNCATEGORIZED,
        operation_date=date.fromisoformat(raw["booking_date"]),
    )


def select_closing_booked_balance(balances: tuple[dict[str, Any], ...]) -> float | None:
    """Return the closing booked (CLBD) balance amount, or None if absent."""
    for balance in balances:
        if balance.get("balance_type") == _CLOSING_BOOKED:
            return float(balance["balance_amount"]["amount"])
    return None


def _remittance_description(remittance_information: list[str] | None) -> str:
    """Join remittance information lines into a single description."""
    if not remittance_information:
        return ""
    return " ".join(part.strip() for part in remittance_information if part).strip()


def _signed_amount(raw: dict[str, Any]) -> Amount:
    """Build a signed amount: DBIT is an expense, CRDT an income."""
    transaction_amount = raw["transaction_amount"]
    value = float(transaction_amount["amount"])
    indicator = raw["credit_debit_indicator"]
    if indicator == "CRDT":
        signed = value
    elif indicator == "DBIT":
        signed = -value
    else:
        raise ValueError(f"Unknown credit_debit_indicator: {indicator!r}")
    return Amount(signed, transaction_amount.get("currency", "EUR"))
