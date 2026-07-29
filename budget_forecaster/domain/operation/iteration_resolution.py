"""Data model for iteration resolutions.

A resolution is the user's decision about one iteration of a planned operation
that no historic operation ever matched: either it will never happen, or it is
moved to a later date. Everything else about an iteration is derived from links
and dates.
"""

from dataclasses import dataclass
from datetime import date, datetime

from budget_forecaster.core.types import (
    IterationAction,
    IterationDate,
    PlannedOperationId,
)


@dataclass(frozen=True)
class IterationResolution:
    """The user's decision about one iteration of a planned operation.

    Attributes:
        iteration_date: The iteration's own planned date; identifies it.
            A plain date: a datetime is refused.
        postponed_to: Required for a postponement, forbidden otherwise.
        decided_at: Aware UTC; None until the decision is stored.
    """

    planned_operation_id: PlannedOperationId
    iteration_date: IterationDate
    action: IterationAction
    postponed_to: date | None = None
    note: str | None = None
    decided_at: datetime | None = None

    def __post_init__(self) -> None:
        # datetime subclasses date, so it type-checks everywhere and then stores an
        # ISO string that date.fromisoformat refuses to read back.
        for field, value in (
            ("iteration_date", self.iteration_date),
            ("postponed_to", self.postponed_to),
        ):
            if isinstance(value, datetime):
                raise TypeError(f"{field} must be a date, got a datetime")

        if self.action is IterationAction.POSTPONE:
            if self.postponed_to is None:
                raise ValueError("A postponed iteration needs a new date")
            if self.postponed_to <= self.iteration_date:
                raise ValueError(
                    f"postponed_to must be after the iteration date, got "
                    f"{self.postponed_to} <= {self.iteration_date}"
                )
        elif self.postponed_to is not None:
            raise ValueError(f"A {self.action} iteration cannot carry a new date")
