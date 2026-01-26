"""Data model for operation links.

An operation link represents a connection between a historic operation
and a specific iteration of a planned operation or budget.
"""

from typing import NamedTuple

from budget_forecaster.types import IterationDate, LinkType, OperationId


class OperationLink(NamedTuple):
    """Represents a link between a historic operation and a planned operation/budget iteration.

    An operation can only be linked to ONE iteration (enforced by DB UNIQUE constraint).

    Attributes:
        operation_unique_id: The unique ID of the historic operation.
        target_type: The type of target (planned operation or budget).
        target_id: The ID of the target planned operation or budget.
        iteration_date: The date of the specific iteration (initial_date of the TimeRange).
        is_manual: True if user-created, False if heuristic-created.
        notes: Optional comment (only for manual links).
        link_id: Database id (only set when read from DB, None when creating).
    """

    operation_unique_id: OperationId
    target_type: LinkType
    target_id: int
    iteration_date: IterationDate
    is_manual: bool = False
    notes: str | None = None
    link_id: int | None = None
