"""Shared fixtures for bank adapter tests."""

from pathlib import Path

import pytest

BNP_FIXTURES_DIR = Path(__file__).parents[2] / "fixtures" / "bnp"


@pytest.fixture
def bnp_export() -> Path:
    """Path to a realistic BNP Paribas .xls export file."""
    return BNP_FIXTURES_DIR / "bnp_export.xls"


@pytest.fixture
def bnp_export_no_date() -> Path:
    """Path to a BNP export where the header doesn't contain 'Solde au ...'."""
    return BNP_FIXTURES_DIR / "bnp_no_date.xls"
