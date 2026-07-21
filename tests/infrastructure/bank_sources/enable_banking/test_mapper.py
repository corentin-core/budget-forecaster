"""Tests for the Enable Banking transaction/balance mapping."""

from datetime import date

import pytest

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.infrastructure.bank_sources.enable_banking.mapper import (
    map_transaction,
    select_closing_booked_balance,
)
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)


def _transaction(**overrides: object) -> dict:
    """Build a booked transaction payload, overriding fields as needed."""
    raw = {
        "status": "BOOK",
        "booking_date": "2026-01-15",
        "credit_debit_indicator": "DBIT",
        "transaction_amount": {"currency": "EUR", "amount": "42.90"},
        "remittance_information": ["CARTE 14/01 MONOPRIX", "PARIS"],
    }
    raw.update(overrides)
    return raw


class TestMapTransaction:
    """Tests for map_transaction."""

    def test_debit_maps_to_negative_amount(self) -> None:
        """A DBIT transaction becomes a negative-amount operation."""
        operation = map_transaction(_transaction(), HistoricOperationFactory(0))

        assert operation == HistoricOperation(
            unique_id=1,
            description="CARTE 14/01 MONOPRIX PARIS",
            amount=Amount(-42.90, "EUR"),
            category=Category.UNCATEGORIZED,
            operation_date=date(2026, 1, 15),
        )

    def test_credit_maps_to_positive_amount(self) -> None:
        """A CRDT transaction becomes a positive-amount operation."""
        raw = _transaction(credit_debit_indicator="CRDT")

        operation = map_transaction(raw, HistoricOperationFactory(0))

        assert operation is not None
        assert operation.amount == 42.90

    @pytest.mark.parametrize(
        "remittance,expected",
        [
            (["LINE ONE", "LINE TWO"], "LINE ONE LINE TWO"),
            (["  SPACED  "], "SPACED"),
            ([], ""),
            (None, ""),
        ],
        ids=["multi-line", "trimmed", "empty-list", "missing"],
    )
    def test_description_from_remittance(
        self, remittance: list[str] | None, expected: str
    ) -> None:
        """Remittance lines are joined and trimmed into the description."""
        raw = _transaction(remittance_information=remittance)

        operation = map_transaction(raw, HistoricOperationFactory(0))

        assert operation is not None
        assert operation.description == expected

    def test_booking_date_is_parsed(self) -> None:
        """The booking date is parsed as the operation date."""
        raw = _transaction(booking_date="2025-12-31")

        operation = map_transaction(raw, HistoricOperationFactory(0))

        assert operation is not None
        assert operation.operation_date == date(2025, 12, 31)

    def test_pending_transaction_is_skipped(self) -> None:
        """A pending (PDNG) transaction maps to None."""
        raw = _transaction(status="PDNG")

        assert map_transaction(raw, HistoricOperationFactory(0)) is None

    def test_unknown_indicator_raises(self) -> None:
        """An unexpected credit/debit indicator raises rather than guessing a sign."""
        raw = _transaction(credit_debit_indicator="XXXX")

        with pytest.raises(ValueError):
            map_transaction(raw, HistoricOperationFactory(0))


class TestSelectClosingBookedBalance:
    """Tests for select_closing_booked_balance."""

    def test_selects_closing_booked_among_several(self) -> None:
        """The CLBD balance is picked among several balance types."""
        balances = [
            {"balance_type": "ITAV", "balance_amount": {"amount": "500.00"}},
            {"balance_type": "CLBD", "balance_amount": {"amount": "1234.56"}},
        ]

        assert select_closing_booked_balance(balances) == 1234.56

    def test_returns_none_when_absent(self) -> None:
        """No CLBD entry yields a None balance."""
        balances = [{"balance_type": "ITAV", "balance_amount": {"amount": "500.00"}}]

        assert select_closing_booked_balance(balances) is None
