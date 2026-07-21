"""Tests for FileExportAdapterFactory."""

from pathlib import Path

import pytest

from budget_forecaster.exceptions import UnsupportedExportError
from budget_forecaster.infrastructure.bank_sources.bnp_paribas.bnp_paribas_bank_adapter import (
    BnpParibasBankAdapter,
)
from budget_forecaster.infrastructure.bank_sources.file_export_adapter_factory import (
    FileExportAdapterFactory,
)


class TestCreateAdapter:
    """Tests for FileExportAdapterFactory.create_adapter."""

    def test_returns_bnp_adapter_for_xls_file(self, tmp_path: Path) -> None:
        """Returns a BnpParibasBankAdapter for .xls files."""
        xls_file = tmp_path / "export.xls"
        xls_file.write_text("")

        adapter = FileExportAdapterFactory.create_adapter(xls_file)

        assert isinstance(adapter, BnpParibasBankAdapter)

    def test_raises_for_unsupported_format(self, tmp_path: Path) -> None:
        """Raises UnsupportedExportError for unknown file formats."""
        unknown_file = tmp_path / "export.pdf"
        unknown_file.write_text("")

        with pytest.raises(UnsupportedExportError):
            FileExportAdapterFactory.create_adapter(unknown_file)
