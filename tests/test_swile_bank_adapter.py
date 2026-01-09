"""Tests for the Swile bank adapter."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from budget_forecaster.bank_adapter.swile.swile_bank_adapter import SwileBankAdapter
from budget_forecaster.operation_range.historic_operation_factory import (
    HistoricOperationFactory,
)
from budget_forecaster.types import Category

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "swile"


@pytest.fixture
def swile_adapter() -> SwileBankAdapter:
    """Create a SwileBankAdapter instance."""
    return SwileBankAdapter()


@pytest.fixture
def operation_factory() -> HistoricOperationFactory:
    """Create a HistoricOperationFactory instance."""
    return HistoricOperationFactory(last_operation_id=0)


class TestSwileBankAdapterMatch:
    """Tests for the match class method."""

    def test_match_valid_directory(self, tmp_path: Path) -> None:
        """Test that match returns True for a valid Swile export directory."""
        (tmp_path / "operations.json").write_text("{}")
        (tmp_path / "wallets.json").write_text("{}")

        assert SwileBankAdapter.match(tmp_path) is True

    def test_match_missing_operations_file(self, tmp_path: Path) -> None:
        """Test that match returns False when operations.json is missing."""
        (tmp_path / "wallets.json").write_text("{}")

        assert SwileBankAdapter.match(tmp_path) is False

    def test_match_missing_wallets_file(self, tmp_path: Path) -> None:
        """Test that match returns False when wallets.json is missing."""
        (tmp_path / "operations.json").write_text("{}")

        assert SwileBankAdapter.match(tmp_path) is False

    def test_match_not_a_directory(self, tmp_path: Path) -> None:
        """Test that match returns False for a file instead of directory."""
        file_path = tmp_path / "not_a_directory.json"
        file_path.write_text("{}")

        assert SwileBankAdapter.match(file_path) is False


class TestSwileBankAdapterLoad:
    """Tests for the load_bank_export method."""

    def test_load_valid_export(
        self,
        swile_adapter: SwileBankAdapter,
        operation_factory: HistoricOperationFactory,
    ) -> None:
        """Test loading a valid Swile export."""
        swile_adapter.load_bank_export(FIXTURES_DIR, operation_factory)

        # Check balance is extracted correctly
        assert swile_adapter.balance == 125.50

        # Check operations are loaded (5 valid meal voucher transactions)
        # - op-001: CAPTURED meal voucher
        # - op-002: VALIDATED meal voucher
        # - op-003: AUTHORIZED meal voucher
        # - op-004: DECLINED (skipped)
        # - op-005: VALIDATED emission (credit)
        # - op-006: CAPTURED meal voucher (CreditCard part skipped)
        assert len(swile_adapter.operations) == 5

    def test_load_export_date(
        self,
        swile_adapter: SwileBankAdapter,
        operation_factory: HistoricOperationFactory,
    ) -> None:
        """Test that export date is the max operation date."""
        swile_adapter.load_bank_export(FIXTURES_DIR, operation_factory)

        # The latest transaction is op-003 on 2025-01-16
        assert swile_adapter.export_date == datetime(2025, 1, 16)

    def test_load_operations_amounts(
        self,
        swile_adapter: SwileBankAdapter,
        operation_factory: HistoricOperationFactory,
    ) -> None:
        """Test that operation amounts are correctly converted from centimes."""
        swile_adapter.load_bank_export(FIXTURES_DIR, operation_factory)

        amounts = sorted([op.amount for op in swile_adapter.operations])
        # Expected amounts (in euros): -25.00, -25.00, -15.00, -8.00, +189.00
        assert amounts == [-25.0, -25.0, -15.0, -8.0, 189.0]

    def test_load_operations_descriptions(
        self,
        swile_adapter: SwileBankAdapter,
        operation_factory: HistoricOperationFactory,
    ) -> None:
        """Test that operation descriptions are extracted from operation name."""
        swile_adapter.load_bank_export(FIXTURES_DIR, operation_factory)

        descriptions = {op.description for op in swile_adapter.operations}
        expected = {
            "Restaurant Test",
            "Supermarche Test",
            "Boulangerie Test",
            "Credit titres-resto",
            "Paiement mixte",
        }
        assert descriptions == expected

    def test_load_operations_category(
        self,
        swile_adapter: SwileBankAdapter,
        operation_factory: HistoricOperationFactory,
    ) -> None:
        """Test that all operations are categorized as OTHER."""
        swile_adapter.load_bank_export(FIXTURES_DIR, operation_factory)

        for operation in swile_adapter.operations:
            assert operation.category == Category.OTHER

    def test_load_operations_currency(
        self,
        swile_adapter: SwileBankAdapter,
        operation_factory: HistoricOperationFactory,
    ) -> None:
        """Test that operation currency is correctly extracted."""
        swile_adapter.load_bank_export(FIXTURES_DIR, operation_factory)

        for operation in swile_adapter.operations:
            assert operation.currency == "EUR"

    def test_skips_declined_transactions(
        self,
        swile_adapter: SwileBankAdapter,
        operation_factory: HistoricOperationFactory,
    ) -> None:
        """Test that DECLINED transactions are skipped."""
        swile_adapter.load_bank_export(FIXTURES_DIR, operation_factory)

        descriptions = {op.description for op in swile_adapter.operations}
        assert "Marchand Echec" not in descriptions

    def test_skips_non_meal_voucher_payments(
        self,
        swile_adapter: SwileBankAdapter,
        operation_factory: HistoricOperationFactory,
    ) -> None:
        """Test that non-meal voucher payment methods are skipped."""
        swile_adapter.load_bank_export(FIXTURES_DIR, operation_factory)

        # op-006 has 2 transactions: meal voucher (-25€) and credit card (-5€)
        # Only the meal voucher one should be counted
        paiement_mixte_ops = [
            op for op in swile_adapter.operations if op.description == "Paiement mixte"
        ]
        assert len(paiement_mixte_ops) == 1
        assert paiement_mixte_ops[0].amount == -25.0

    def test_load_empty_operations_raises_error(
        self,
        swile_adapter: SwileBankAdapter,
        operation_factory: HistoricOperationFactory,
        tmp_path: Path,
    ) -> None:
        """Test that loading with no valid transactions raises ValueError."""
        operations = {"items_count": 0, "has_more": False, "items": []}
        wallets = {"wallets": [{"type": "meal_voucher", "balance": {"value": 100.0}}]}

        (tmp_path / "operations.json").write_text(json.dumps(operations))
        (tmp_path / "wallets.json").write_text(json.dumps(wallets))

        with pytest.raises(ValueError, match="No meal voucher transactions found"):
            swile_adapter.load_bank_export(tmp_path, operation_factory)

    def test_load_invalid_balance_type_raises_error(
        self,
        swile_adapter: SwileBankAdapter,
        operation_factory: HistoricOperationFactory,
        tmp_path: Path,
    ) -> None:
        """Test that invalid balance type raises ValueError."""
        operations = {
            "items": [
                {
                    "name": "Test",
                    "transactions": [
                        {
                            "status": "CAPTURED",
                            "payment_method": "Wallets::MealVoucherWallet",
                            "date": "2025-01-15T12:00:00.000+01:00",
                            "amount": {"value": -1000, "currency": {"iso_3": "EUR"}},
                        }
                    ],
                }
            ]
        }
        wallets = {
            "wallets": [{"type": "meal_voucher", "balance": {"value": "invalid"}}]
        }

        (tmp_path / "operations.json").write_text(json.dumps(operations))
        (tmp_path / "wallets.json").write_text(json.dumps(wallets))

        with pytest.raises(ValueError, match="balance field should be a float"):
            swile_adapter.load_bank_export(tmp_path, operation_factory)


class TestSwileBankAdapterInit:
    """Tests for adapter initialization."""

    def test_adapter_name(self, swile_adapter: SwileBankAdapter) -> None:
        """Test that adapter has correct name."""
        assert swile_adapter.name == "swile"

    def test_initial_state(self, swile_adapter: SwileBankAdapter) -> None:
        """Test that adapter has correct initial state before loading."""
        assert swile_adapter.operations == ()
        assert swile_adapter.balance is None
        assert swile_adapter.export_date is None
