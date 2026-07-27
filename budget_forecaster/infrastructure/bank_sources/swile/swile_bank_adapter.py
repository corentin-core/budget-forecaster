"""Module for the Swile bank adapter"""
import json
import re
import zipfile
from pathlib import Path

from budget_forecaster.exceptions import InvalidExportDataError
from budget_forecaster.infrastructure.bank_sources.file_export_adapter import (
    FileExportAdapterBase,
)
from budget_forecaster.infrastructure.bank_sources.swile.swile_parser import (
    parse_balance,
    parse_operations,
)
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)

_SWILE_ZIP_PATTERN = re.compile(r"^swile-export-\d{4}-\d{2}-\d{2}\.zip$")


class SwileBankAdapter(FileExportAdapterBase):
    """Adapter for the Swile Meal-Vouchers account"""

    def __init__(self) -> None:
        super().__init__("swile")

    def load_bank_export(
        self, bank_export: Path, operation_factory: HistoricOperationFactory
    ) -> None:
        """Load export from a swile-export-YYYY-MM-DD.zip archive.

        The zip holds operations.json and wallets.json at the root. An export
        with no meal-voucher transaction is rejected as invalid.
        """
        with zipfile.ZipFile(bank_export, "r") as zf:
            operations_json = json.loads(zf.read("operations.json"))
            wallets_json = json.loads(zf.read("wallets.json"))

        self._balance = parse_balance(wallets_json, path=bank_export)
        if not (operations := parse_operations(operations_json, operation_factory)):
            raise InvalidExportDataError(
                "No meal voucher transactions found in the operations.json file",
                path=bank_export,
            )
        self._operations = list(operations)
        self._export_date = max(op.operation_date for op in operations)

    @classmethod
    def match(cls, bank_export: Path) -> bool:
        """Return True if the path is a swile-export-YYYY-MM-DD.zip file."""
        return (
            bank_export.is_file()
            and _SWILE_ZIP_PATTERN.match(bank_export.name) is not None
        )
