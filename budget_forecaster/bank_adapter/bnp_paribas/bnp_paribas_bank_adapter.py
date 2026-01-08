"""Module for the BNP Paribas bank adapter."""
import re
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from budget_forecaster.amount import Amount
from budget_forecaster.bank_adapter.bank_adapter import BankAdapterBase
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.historic_operation_factory import (
    HistoricOperationFactory,
)
from budget_forecaster.types import Category

# Path to the external category mapping file
DEFAULT_MAPPING_PATH = Path(__file__).parent / "category_mapping.yaml"

# Build reverse lookup from Category values to Category enum
_CATEGORY_BY_VALUE: dict[str, Category] = {cat.value: cat for cat in Category}


def load_category_mapping(mapping_path: Path | None = None) -> dict[str, Category]:
    """Load category mapping from YAML file.

    Args:
        mapping_path: Path to the YAML mapping file. Uses default if None.

    Returns:
        Dictionary mapping BNP subcategories to Category enum values.
    """
    path = mapping_path or DEFAULT_MAPPING_PATH
    if not path.exists():
        warnings.warn(
            f"Category mapping file not found: {path}. Using empty mapping.",
            stacklevel=2,
        )
        return {}

    with open(path, encoding="utf-8") as f:
        raw_mapping: dict[str, str] = yaml.safe_load(f) or {}

    result: dict[str, Category] = {}
    for bnp_category, internal_category in raw_mapping.items():
        if internal_category in _CATEGORY_BY_VALUE:
            result[bnp_category] = _CATEGORY_BY_VALUE[internal_category]
        else:
            warnings.warn(
                f"Unknown internal category '{internal_category}' for BNP category "
                f"'{bnp_category}'. Valid categories: {list(_CATEGORY_BY_VALUE.keys())}",
                stacklevel=2,
            )
    return result


class BnpParibasBankAdapter(BankAdapterBase):
    """Adapter for the BNP Paribas bank export operations."""

    def __init__(self, category_mapping_path: Path | None = None) -> None:
        super().__init__("bnp")
        self._category_mapping = load_category_mapping(category_mapping_path)
        self._unknown_categories: set[str] = set()

    def load_bank_export(
        self, bank_export: Path, operation_factory: HistoricOperationFactory
    ) -> None:
        # get export date
        export_date_cell = pd.read_excel(
            bank_export, index_col=None, usecols="B", header=0, nrows=0
        ).columns.values[0]
        if (re_match := re.match("Solde au (.*)", export_date_cell)) is not None:
            self._export_date = datetime.strptime(re_match.group(1), "%d/%m/%Y")
        else:
            self._export_date = datetime.now()
        # get balance
        self._balance = float(
            pd.read_excel(
                bank_export, index_col=None, usecols="C", header=0, nrows=0
            ).columns.values[0]
        )
        # get operations
        self._operations: list[HistoricOperation] = []
        operation_df = pd.read_excel(bank_export, header=2)
        for _, row in operation_df.iterrows():
            bnp_category = row["Sous Categorie operation"]
            category = self._get_category(bnp_category)
            self._operations.append(
                operation_factory.create_operation(
                    description=row["Libelle operation"],
                    amount=Amount(row["Montant operation"]),
                    category=category,
                    date=datetime.strptime(row["Date operation"], "%d-%m-%Y"),
                )
            )

        # Report unknown categories at the end
        if self._unknown_categories:
            warnings.warn(
                f"Unknown BNP categories (assigned to 'Autre'): "
                f"{sorted(self._unknown_categories)}. "
                f"Add them to category_mapping.yaml to map them correctly.",
                stacklevel=2,
            )

    def _get_category(self, bnp_category: str) -> Category:
        """Get internal category for a BNP category, with fallback to OTHER."""
        if bnp_category in self._category_mapping:
            return self._category_mapping[bnp_category]
        self._unknown_categories.add(bnp_category)
        return Category.OTHER

    @property
    def unknown_categories(self) -> set[str]:
        """Return the set of unknown BNP categories encountered during import."""
        return self._unknown_categories

    @classmethod
    def match(cls, bank_export: Path) -> bool:
        return bank_export.suffix == ".xls"

    @classmethod
    def find_unmapped_categories(cls, bank_export: Path) -> set[str]:
        """Find BNP categories in an export file that are not in the mapping."""
        operation_df = pd.read_excel(bank_export, header=2)

        if "Sous Categorie operation" not in operation_df.columns:
            raise ValueError(
                f"Not a valid BNP export file. "
                f"Expected column 'Sous Categorie operation', "
                f"found: {list(operation_df.columns)}"
            )

        category_mapping = load_category_mapping()
        bnp_categories = set(operation_df["Sous Categorie operation"].dropna().unique())
        return bnp_categories - set(category_mapping.keys())
