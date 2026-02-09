"""Shared fixtures for bank adapter tests."""

from pathlib import Path

import pandas as pd
import pytest

BNP_FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "bnp"


@pytest.fixture
def bnp_export(tmp_path: Path) -> Path:
    """Create a realistic BNP Paribas .xls export file.

    Structure matches what BnpParibasBankAdapter.load_bank_export expects:
    - Row 0: header row, col B = "Solde au DD/MM/YYYY", col C = balance
    - Row 2+: operations with specific column names
    """
    export_path = tmp_path / "bnp_export.xls"

    # Build the header rows (rows 0-1) and operation rows (row 2+)
    # Row 0 (will become the "header" when read with header=0):
    #   col A = ignored, col B = "Solde au 15/01/2025", col C = 1234.56
    # Row 1: separator / empty (becomes header=2 area start)
    # Row 2+: operation data
    header_df = pd.DataFrame(
        {
            "Unnamed: 0": [""],
            "Solde au 15/01/2025": [""],
            1234.56: [None],
        }
    )

    operations_df = pd.DataFrame(
        {
            "Date operation": [
                "10-01-2025",
                "11-01-2025",
                "12-01-2025",
                "13-01-2025",
            ],
            "Libelle operation": [
                "CARREFOUR MARKET",
                "VIREMENT SALAIRE",
                "NAVIGO PASS",
                "FNAC ACHAT EN LIGNE",
            ],
            "Montant operation": [-85.20, 2500.00, -75.00, -42.99],
            "Sous Categorie operation": [
                "Alimentation / Supermarché",
                "Revenus / Salaire",
                "Transports / Transport en commun",
                "Catégorie Inconnue",
            ],
        }
    )

    with pd.ExcelWriter(export_path, engine="xlsxwriter") as writer:
        header_df.to_excel(writer, sheet_name="Sheet1", index=False, startrow=0)
        operations_df.to_excel(
            writer, sheet_name="Sheet1", index=False, startrow=2, header=True
        )

    return export_path


@pytest.fixture
def bnp_export_no_date(tmp_path: Path) -> Path:
    """Create a BNP export where the header doesn't contain 'Solde au ...'."""
    export_path = tmp_path / "bnp_no_date.xls"

    header_df = pd.DataFrame(
        {
            "Unnamed: 0": [""],
            "Compte courant": [""],
            1000.00: [None],
        }
    )

    operations_df = pd.DataFrame(
        {
            "Date operation": ["10-01-2025"],
            "Libelle operation": ["TEST"],
            "Montant operation": [-10.0],
            "Sous Categorie operation": ["Test"],
        }
    )

    with pd.ExcelWriter(export_path, engine="xlsxwriter") as writer:
        header_df.to_excel(writer, sheet_name="Sheet1", index=False, startrow=0)
        operations_df.to_excel(
            writer, sheet_name="Sheet1", index=False, startrow=2, header=True
        )

    return export_path
