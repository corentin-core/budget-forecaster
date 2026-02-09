"""Tests for BankAdapterFactory."""

from pathlib import Path

import pytest

from budget_forecaster.exceptions import UnsupportedExportError
from budget_forecaster.infrastructure.bank_adapters.bank_adapter_factory import (
    BankAdapterFactory,
)
from budget_forecaster.infrastructure.bank_adapters.bnp_paribas.bnp_paribas_bank_adapter import (
    BnpParibasBankAdapter,
)


class TestCreateBankAdapter:
    """Tests for BankAdapterFactory.create_bank_adapter."""

    def test_returns_bnp_adapter_for_xls_file(self, tmp_path: Path) -> None:
        """Returns a BnpParibasBankAdapter for .xls files."""
        xls_file = tmp_path / "export.xls"
        xls_file.write_text("")

        adapter = BankAdapterFactory.create_bank_adapter(xls_file)

        assert isinstance(adapter, BnpParibasBankAdapter)

    def test_raises_for_unsupported_format(self, tmp_path: Path) -> None:
        """Raises UnsupportedExportError for unknown file formats."""
        unknown_file = tmp_path / "export.pdf"
        unknown_file.write_text("")

        with pytest.raises(UnsupportedExportError):
            BankAdapterFactory.create_bank_adapter(unknown_file)
