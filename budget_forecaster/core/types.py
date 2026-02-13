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

    PLANNED_OPERATION = enum.auto()
    BUDGET = enum.auto()


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
    UNCATEGORIZED = enum.auto()

    # Income
    SALARY = enum.auto()
    TAX_CREDIT = enum.auto()
    BENEFITS = enum.auto()

    # Housing
    HOUSE_LOAN = enum.auto()
    WORKS_LOAN = enum.auto()
    RENT = enum.auto()
    LOAN_INSURANCE = enum.auto()
    HOUSE_WORKS = enum.auto()
    FURNITURE = enum.auto()

    # Investments
    SAVINGS = enum.auto()

    # Insurance
    CAR_INSURANCE = enum.auto()
    HOUSE_INSURANCE = enum.auto()
    OTHER_INSURANCE = enum.auto()

    # Children
    CHILDCARE = enum.auto()
    CHILD_SUPPORT = enum.auto()

    # Leisure
    ENTERTAINMENT = enum.auto()
    LEISURE = enum.auto()
    HOLIDAYS = enum.auto()

    # Utilities
    ELECTRICITY = enum.auto()
    WATER = enum.auto()
    INTERNET = enum.auto()
    PHONE = enum.auto()

    # Daily life
    GROCERIES = enum.auto()
    CLOTHING = enum.auto()
    HEALTH_CARE = enum.auto()
    CARE = enum.auto()
    PUBLIC_TRANSPORT = enum.auto()
    CAR_FUEL = enum.auto()
    PARKING = enum.auto()
    TOLL = enum.auto()
    CAR_MAINTENANCE = enum.auto()
    CAR_LOAN = enum.auto()
    GIFTS = enum.auto()

    # Professional
    PROFESSIONAL_EXPENSES = enum.auto()

    # Other
    OTHER = enum.auto()
    CHARITY = enum.auto()
    BANK_FEES = enum.auto()
    TAXES = enum.auto()

    @property
    def display_name(self) -> str:
        """Return the translated display name for this category."""
        return _(self.name.replace("_", " ").title())
