"""Module for the Swile bank adapter"""
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.exceptions import InvalidExportDataError
from budget_forecaster.infrastructure.bank_adapters.bank_adapter import BankAdapterBase
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)

_SWILE_ZIP_PATTERN = re.compile(r"^swile-export-\d{4}-\d{2}-\d{2}\.zip$")


class SwileBankAdapter(BankAdapterBase):
    """Adapter for the Swile Meal-Vouchers account"""

    def __init__(self) -> None:
        super().__init__("swile")

    def load_bank_export(
        self, bank_export: Path, operation_factory: HistoricOperationFactory
    ) -> None:
        """Load export from a swile-export-YYYY-MM-DD.zip archive.

        The zip must contain operations.json and wallets.json at the root level.
        """
        with zipfile.ZipFile(bank_export, "r") as zf:
            operations_json = json.loads(zf.read("operations.json"))
            wallets_json = json.loads(zf.read("wallets.json"))

        for wallet in wallets_json["wallets"]:
            if wallet["type"] == "meal_voucher":
                if not isinstance(wallet["balance"]["value"], (float, int)):
                    raise InvalidExportDataError(
                        "The balance field should be a float",
                        path=bank_export,
                    )
                self._balance = wallet["balance"]["value"]
                break

        for operation in operations_json["items"]:
            for transaction in operation["transactions"]:
                if transaction["status"] not in ("AUTHORIZED", "VALIDATED", "CAPTURED"):
                    continue

                if transaction["payment_method"] != "Wallets::MealVoucherWallet":
                    # we only consider meal vouchers as the other transactions are deduced from the
                    # main account
                    continue

                amount = transaction["amount"]["value"] / 100.0
                # date has format "2025-01-24T13:50:50.073+01:00"
                op_date = datetime.strptime(transaction["date"][:10], "%Y-%m-%d").date()
                self._operations.append(
                    operation_factory.create_operation(
                        description=operation["name"],
                        amount=Amount(
                            amount, transaction["amount"]["currency"]["iso_3"]
                        ),
                        category=Category.UNCATEGORIZED,
                        operation_date=op_date,
                    )
                )

        if not self._operations:
            raise InvalidExportDataError(
                "No meal voucher transactions found in the operations.json file",
                path=bank_export,
            )

        self._export_date = max(op.operation_date for op in self._operations)

    @classmethod
    def match(cls, bank_export: Path) -> bool:
        """Return True if the path is a swile-export-YYYY-MM-DD.zip file."""
        return (
            bank_export.is_file()
            and _SWILE_ZIP_PATTERN.match(bank_export.name) is not None
        )
