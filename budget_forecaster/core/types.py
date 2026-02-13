"""Module containing custom types for the budget_forecaster package."""
import enum
from datetime import date
from typing import Callable, NamedTuple

from budget_forecaster.i18n import _

OperationId = int
"""Unique identifier for a historic operation."""

PlannedOperationId = int
"""Unique identifier for a planned operation."""

BudgetId = int
"""Unique identifier for a budget."""

OperationLinkId = int
"""Unique identifier for an operation link."""

IterationDate = date
"""Date identifying a specific iteration of a planned operation or budget."""

TargetId = PlannedOperationId | BudgetId
"""Identifier for a link target (planned operation or budget)."""

TargetName = str
"""Display name/description of a link target."""


class LinkType(enum.StrEnum):
    """Type of link target."""

    PLANNED_OPERATION = "planned_operation"
    BUDGET = "budget"


class MatcherKey(NamedTuple):
    """Key identifying a matcher (link type + target id)."""

    link_type: LinkType
    target_id: TargetId


# Import progress callback type aliases
ImportProgressCurrent = int
"""Current progress count (number of files processed)."""

ImportProgressTotal = int
"""Total number of files to process."""

ImportProgressFilename = str
"""Name of the file currently being processed."""

ImportProgressCallback = Callable[
    [ImportProgressCurrent, ImportProgressTotal, ImportProgressFilename], None
]
"""Callback for import progress updates: (current, total, filename) -> None."""


class ImportStats(NamedTuple):
    """Statistics about an import operation."""

    total_in_file: int
    """Total number of operations in the imported file."""

    new_operations: int
    """Number of new operations added to the database."""

    duplicates_skipped: int
    """Number of duplicate operations that were already in the database."""


class Category(enum.StrEnum):
    """A category is a group of transactions.

    The enum *value* is a language-neutral key used for persistence.
    Use :attr:`display_name` for the user-facing translated label.
    """

    # Uncategorized (default for imports)
    UNCATEGORIZED = "uncategorized"

    # Income
    SALARY = "salary"
    TAX_CREDIT = "tax_credit"
    BENEFITS = "benefits"

    # Housing
    HOUSE_LOAN = "house_loan"
    WORKS_LOAN = "works_loan"
    RENT = "rent"
    LOAN_INSURANCE = "loan_insurance"
    HOUSE_WORKS = "house_works"
    FURNITURE = "furniture"

    # Investments
    SAVINGS = "savings"

    # Insurance
    CAR_INSURANCE = "car_insurance"
    HOUSE_INSURANCE = "house_insurance"
    OTHER_INSURANCE = "other_insurance"

    # Children
    CHILDCARE = "childcare"
    CHILD_SUPPORT = "child_support"

    # Leisure
    ENTERTAINMENT = "entertainment"
    LEISURE = "leisure"
    HOLIDAYS = "holidays"

    # Utilities
    ELECTRICITY = "electricity"
    WATER = "water"
    INTERNET = "internet"
    PHONE = "phone"

    # Daily life
    GROCERIES = "groceries"
    CLOTHING = "clothing"
    HEALTH_CARE = "health_care"
    CARE = "care"
    PUBLIC_TRANSPORT = "public_transport"
    CAR_FUEL = "car_fuel"
    PARKING = "parking"
    TOLL = "toll"
    CAR_MAINTENANCE = "car_maintenance"
    CAR_LOAN = "car_loan"
    GIFTS = "gifts"

    # Professional
    PROFESSIONAL_EXPENSES = "professional_expenses"

    # Other
    OTHER = "other"
    CHARITY = "charity"
    BANK_FEES = "bank_fees"
    TAXES = "taxes"

    @property
    def display_name(self) -> str:
        """Return the translated display name for this category."""
        return _(self.value)
