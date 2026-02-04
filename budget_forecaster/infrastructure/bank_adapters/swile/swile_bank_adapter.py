"""Module for the Swile bank adapter"""
import json
from datetime import datetime
from pathlib import Path

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.infrastructure.bank_adapters.bank_adapter import BankAdapterBase
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)


class SwileBankAdapter(BankAdapterBase):
    """Adapter for the Swile Meal-Vouchers account"""

    def __init__(self) -> None:
        super().__init__("swile")

    def load_bank_export(
        self, bank_export: Path, operation_factory: HistoricOperationFactory
    ) -> None:
        """
        Load export from operations.json and wallets.json files retrieved from swile website
        The path must be a folder containing these two files
        """
        operations_json = json.loads(
            (bank_export / "operations.json").read_text(encoding="utf-8")
        )
        wallets_json = json.loads(
            (bank_export / "wallets.json").read_text(encoding="utf-8")
        )

        for wallet in wallets_json["wallets"]:
            if wallet["type"] == "meal_voucher":
                if not isinstance(wallet["balance"]["value"], (float, int)):
                    raise ValueError("The balance field should be a float")
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
                date = datetime.strptime(transaction["date"][:10], "%Y-%m-%d")
                self._operations.append(
                    operation_factory.create_operation(
                        description=operation["name"],
                        amount=Amount(
                            amount, transaction["amount"]["currency"]["iso_3"]
                        ),
                        category=Category.UNCATEGORIZED,
                        date=date,
                    )
                )

        if not self._operations:
            raise ValueError(
                "No meal voucher transactions found in the operations.json file"
            )

        self._export_date = max(op.date for op in self._operations)

    @classmethod
    def match(cls, bank_export: Path) -> bool:
        return (
            bank_export.is_dir()
            and (bank_export / "operations.json").is_file()
            and (bank_export / "wallets.json").is_file()
        )
