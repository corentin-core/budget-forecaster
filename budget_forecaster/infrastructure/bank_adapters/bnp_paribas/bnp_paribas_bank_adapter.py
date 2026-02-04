"""Module for the BNP Paribas bank adapter."""
import re
import unicodedata
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.infrastructure.bank_adapters.bank_adapter import BankAdapterBase
from budget_forecaster.services.operation.historic_operation_factory import (
    HistoricOperationFactory,
)

# Path to the external category mapping file
DEFAULT_MAPPING_PATH = Path(__file__).parent / "category_mapping.yaml"

# Build reverse lookup from Category values to Category enum
_CATEGORY_BY_VALUE: dict[str, Category] = {cat.value: cat for cat in Category}


def normalize_text(text: str) -> str:
    """Normalize text by removing accents and converting to lowercase.

    Args:
        text: The text to normalize.

    Returns:
        Normalized text without accents, in lowercase.
    """
    # Normalize unicode to decomposed form (é -> e + combining accent)
    normalized = unicodedata.normalize("NFD", text)
    # Remove combining characters (accents)
    without_accents = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return without_accents.lower()


def load_category_keywords(
    mapping_path: Path | None = None,
) -> list[tuple[str, Category]]:
    """Load category keywords from YAML file.

    Args:
        mapping_path: Path to the YAML mapping file. Uses default if None.

    Returns:
        List of (keyword, Category) tuples, sorted by keyword length (longest first).
    """
    path = mapping_path or DEFAULT_MAPPING_PATH
    if not path.exists():
        warnings.warn(
            f"Category mapping file not found: {path}. Using empty mapping.",
            stacklevel=2,
        )
        return []

    with open(path, encoding="utf-8") as f:
        raw_config: dict = yaml.safe_load(f) or {}

    raw_keywords: dict[str, str] = raw_config.get("keywords", {})

    result: list[tuple[str, Category]] = []
    for keyword, internal_category in raw_keywords.items():
        if internal_category in _CATEGORY_BY_VALUE:
            # Normalize keyword for matching
            result.append(
                (normalize_text(keyword), _CATEGORY_BY_VALUE[internal_category])
            )
        else:
            warnings.warn(
                f"Unknown internal category '{internal_category}' for keyword "
                f"'{keyword}'. Valid categories: {list(_CATEGORY_BY_VALUE.keys())}",
                stacklevel=2,
            )

    # Sort by keyword length (longest first) for more specific matches
    result.sort(key=lambda x: len(x[0]), reverse=True)
    return result


class BnpParibasBankAdapter(BankAdapterBase):
    """Adapter for the BNP Paribas bank export operations."""

    def __init__(self, category_mapping_path: Path | None = None) -> None:
        super().__init__("bnp")
        self._category_keywords = load_category_keywords(category_mapping_path)
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
        """Get internal category for a BNP category using keyword matching.

        Searches for keywords in the normalized BNP category string.
        Returns the category for the first (longest) matching keyword.
        Falls back to OTHER if no keyword matches.
        """
        normalized = normalize_text(bnp_category)

        for keyword, category in self._category_keywords:
            if keyword in normalized:
                return category

        self._unknown_categories.add(bnp_category)
        return Category.UNCATEGORIZED

    @property
    def unknown_categories(self) -> set[str]:
        """Return the set of unknown BNP categories encountered during import."""
        return self._unknown_categories

    @classmethod
    def match(cls, bank_export: Path) -> bool:
        return bank_export.suffix == ".xls"

    @classmethod
    def find_unmapped_categories(cls, bank_export: Path) -> set[str]:
        """Find BNP categories in an export file that don't match any keyword."""
        operation_df = pd.read_excel(bank_export, header=2)

        if "Sous Categorie operation" not in operation_df.columns:
            raise ValueError(
                f"Not a valid BNP export file. "
                f"Expected column 'Sous Categorie operation', "
                f"found: {list(operation_df.columns)}"
            )

        keywords = load_category_keywords()
        bnp_categories = set(operation_df["Sous Categorie operation"].dropna().unique())

        unmapped: set[str] = set()
        for bnp_category in bnp_categories:
            normalized = normalize_text(bnp_category)
            if not any(keyword in normalized for keyword, _ in keywords):
                unmapped.add(bnp_category)

        return unmapped
