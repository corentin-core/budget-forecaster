"""Data model for operation links.

An operation link represents a connection between a historic operation
and a specific iteration of a planned operation or budget.
"""

from datetime import datetime
from enum import StrEnum
from typing import NamedTuple


class LinkType(StrEnum):
    """Type of link target."""

    PLANNED_OPERATION = "planned_operation"
    BUDGET = "budget"


class OperationLink(NamedTuple):
    """Represents a link between a historic operation and a planned operation/budget iteration.

    An operation can only be linked to ONE iteration (enforced by DB UNIQUE constraint).

    Attributes:
        operation_unique_id: The unique ID of the historic operation.
        linked_type: The type of target (planned operation or budget).
        linked_id: The ID of the target planned operation or budget.
        iteration_date: The date of the specific iteration (initial_date of the TimeRange).
        is_manual: True if user-created, False if heuristic-created.
        notes: Optional comment (only for manual links).
    """

    operation_unique_id: int
    linked_type: LinkType
    linked_id: int
    iteration_date: datetime
    is_manual: bool = False
    notes: str | None = None
