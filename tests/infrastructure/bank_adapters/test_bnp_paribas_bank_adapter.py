"""Tests for the BNP Paribas bank adapter."""

import warnings
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from budget_forecaster.core.types import Category
from budget_forecaster.infrastructure.bank_adapters.bnp_paribas.bnp_paribas_bank_adapter import (
    BnpParibasBankAdapter,
)
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)

BNP_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "bnp"
CATEGORY_MAPPING_PATH = BNP_FIXTURES_DIR / "category_mapping.yaml"


@pytest.fixture
def adapter() -> BnpParibasBankAdapter:
    """Create a BnpParibasBankAdapter with test category mapping."""
    return BnpParibasBankAdapter(category_mapping_path=CATEGORY_MAPPING_PATH)


@pytest.fixture
def operation_factory() -> HistoricOperationFactory:
    """Create a HistoricOperationFactory instance."""
    return HistoricOperationFactory(last_operation_id=0)


class TestBnpParibasBankAdapterMatch:
    """Tests for the match class method."""

    def test_match_xls_file(self, tmp_path: Path) -> None:
        """Test that match returns True for .xls files."""
        xls_file = tmp_path / "export.xls"
        xls_file.touch()
        assert BnpParibasBankAdapter.match(xls_file) is True

    def test_match_xlsx_file(self, tmp_path: Path) -> None:
        """Test that match returns False for .xlsx files."""
        xlsx_file = tmp_path / "export.xlsx"
        xlsx_file.touch()
        assert BnpParibasBankAdapter.match(xlsx_file) is False

    def test_match_csv_file(self, tmp_path: Path) -> None:
        """Test that match returns False for .csv files."""
        csv_file = tmp_path / "export.csv"
        csv_file.touch()
        assert BnpParibasBankAdapter.match(csv_file) is False


class TestBnpParibasBankAdapterLoad:
    """Tests for the load_bank_export method."""

    def test_load_extracts_export_date(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export: Path,
    ) -> None:
        """Test that export date is extracted from 'Solde au DD/MM/YYYY' header."""
        adapter.load_bank_export(bnp_export, operation_factory)
        assert adapter.export_date == date(2025, 1, 15)

    def test_load_fallback_export_date(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export_no_date: Path,
    ) -> None:
        """Test that export date falls back to today when header is not parseable."""
        adapter.load_bank_export(bnp_export_no_date, operation_factory)
        assert adapter.export_date == date.today()

    def test_load_extracts_balance(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export: Path,
    ) -> None:
        """Test that balance is extracted from header column C."""
        adapter.load_bank_export(bnp_export, operation_factory)
        assert adapter.balance == 1234.56

    def test_load_extracts_operations_count(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export: Path,
    ) -> None:
        """Test that all operations are extracted from the export."""
        adapter.load_bank_export(bnp_export, operation_factory)
        assert len(adapter.operations) == 4

    def test_load_operations_amounts(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export: Path,
    ) -> None:
        """Test that operation amounts are correctly extracted."""
        adapter.load_bank_export(bnp_export, operation_factory)
        amounts = sorted(op.amount for op in adapter.operations)
        assert amounts == [-85.20, -75.00, -42.99, 2500.00]

    def test_load_operations_dates(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export: Path,
    ) -> None:
        """Test that operation dates are correctly parsed from DD-MM-YYYY format."""
        adapter.load_bank_export(bnp_export, operation_factory)
        dates = sorted(op.operation_date for op in adapter.operations)
        assert dates == [
            date(2025, 1, 10),
            date(2025, 1, 11),
            date(2025, 1, 12),
            date(2025, 1, 13),
        ]

    def test_load_operations_descriptions(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export: Path,
    ) -> None:
        """Test that operation descriptions are extracted from 'Libelle operation'."""
        adapter.load_bank_export(bnp_export, operation_factory)
        descriptions = {op.description for op in adapter.operations}
        assert descriptions == {
            "CARREFOUR MARKET",
            "VIREMENT SALAIRE",
            "NAVIGO PASS",
            "FNAC ACHAT EN LIGNE",
        }


class TestBnpParibasBankAdapterCategories:
    """Tests for category mapping via load_bank_export."""

    def test_known_categories_are_mapped(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export: Path,
    ) -> None:
        """Test that known BNP categories are mapped to internal categories."""
        adapter.load_bank_export(bnp_export, operation_factory)
        ops_by_desc = {op.description: op for op in adapter.operations}

        # "Alimentation / Supermarché" -> normalized "alimentation / supermarche"
        # matches keyword "alimentation" -> Courses
        assert ops_by_desc["CARREFOUR MARKET"].category == Category.GROCERIES

        # "Revenus / Salaire" -> normalized "revenus / salaire"
        # matches keyword "salaire" -> Salaire
        assert ops_by_desc["VIREMENT SALAIRE"].category == Category.SALARY

        # "Transports / Transport en commun" -> matches "transport"
        assert ops_by_desc["NAVIGO PASS"].category == Category.PUBLIC_TRANSPORT

    def test_unknown_category_falls_back_to_uncategorized(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export: Path,
    ) -> None:
        """Test that unknown BNP categories fall back to UNCATEGORIZED."""
        adapter.load_bank_export(bnp_export, operation_factory)
        ops_by_desc = {op.description: op for op in adapter.operations}

        assert ops_by_desc["FNAC ACHAT EN LIGNE"].category == Category.UNCATEGORIZED

    def test_unknown_categories_are_tracked(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export: Path,
    ) -> None:
        """Test that unknown categories are collected in unknown_categories set."""
        adapter.load_bank_export(bnp_export, operation_factory)
        assert "Catégorie Inconnue" in adapter.unknown_categories

    def test_unknown_categories_emit_warning(
        self,
        adapter: BnpParibasBankAdapter,
        operation_factory: HistoricOperationFactory,
        bnp_export: Path,
    ) -> None:
        """Test that a warning is emitted for unknown BNP categories."""
        with pytest.warns(UserWarning, match="Unknown BNP categories"):
            adapter.load_bank_export(bnp_export, operation_factory)

    def test_no_warning_when_all_categories_known(
        self,
        operation_factory: HistoricOperationFactory,
        tmp_path: Path,
    ) -> None:
        """Test that no warning is emitted when all categories are mapped."""
        all_known_adapter = BnpParibasBankAdapter(
            category_mapping_path=CATEGORY_MAPPING_PATH
        )

        export_path = tmp_path / "all_known.xls"
        header_df = pd.DataFrame(
            {"A": [""], "Solde au 15/01/2025": [""], 1000.0: [None]}
        )
        operations_df = pd.DataFrame(
            {
                "Date operation": ["10-01-2025"],
                "Libelle operation": ["CARREFOUR"],
                "Montant operation": [-50.0],
                "Sous Categorie operation": ["Alimentation"],
            }
        )
        with pd.ExcelWriter(export_path, engine="xlsxwriter") as writer:
            header_df.to_excel(writer, index=False, startrow=0)
            operations_df.to_excel(writer, index=False, startrow=2, header=True)

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            all_known_adapter.load_bank_export(export_path, operation_factory)


class TestBnpParibasBankAdapterFindUnmapped:
    """Tests for the find_unmapped_categories class method."""

    def test_find_unmapped_returns_unknown_categories(self, bnp_export: Path) -> None:
        """Test that unmapped categories are found in an export file."""
        unmapped = BnpParibasBankAdapter.find_unmapped_categories(bnp_export)
        assert "Catégorie Inconnue" in unmapped

    def test_find_unmapped_excludes_known_categories(self, bnp_export: Path) -> None:
        """Test that known categories are not in the unmapped set."""
        unmapped = BnpParibasBankAdapter.find_unmapped_categories(bnp_export)
        # These should be matched by the default category_mapping.yaml
        assert "Alimentation / Supermarché" not in unmapped
        assert "Revenus / Salaire" not in unmapped

    def test_find_unmapped_invalid_file_raises(self, tmp_path: Path) -> None:
        """Test that an invalid export raises ValueError."""
        bad_file = tmp_path / "bad.xls"
        pd.DataFrame({"Wrong Column": [1, 2]}).to_excel(bad_file, index=False)

        with pytest.raises(ValueError, match="Not a valid BNP export file"):
            BnpParibasBankAdapter.find_unmapped_categories(bad_file)


class TestBnpParibasBankAdapterInit:
    """Tests for adapter initialization."""

    def test_adapter_name(self, adapter: BnpParibasBankAdapter) -> None:
        """Test that adapter has correct name."""
        assert adapter.name == "bnp"

    def test_initial_state(self, adapter: BnpParibasBankAdapter) -> None:
        """Test that adapter has correct initial state before loading."""
        assert adapter.operations == ()
        assert adapter.balance is None
        assert adapter.export_date is None

    def test_missing_mapping_file_uses_empty(self, tmp_path: Path) -> None:
        """Test that a missing mapping file produces an empty keyword list."""
        with pytest.warns(UserWarning, match="Category mapping file not found"):
            missing_adapter = BnpParibasBankAdapter(
                category_mapping_path=tmp_path / "nonexistent.yaml"
            )
        assert missing_adapter.unknown_categories == set()
