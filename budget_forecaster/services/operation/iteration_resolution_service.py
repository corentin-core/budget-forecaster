"""Service for the user's decisions on unmatched planned iterations."""

from datetime import date, datetime, timezone

from budget_forecaster.core.types import (
    IterationAction,
    IterationDate,
    PlannedOperationId,
)
from budget_forecaster.domain.operation.iteration_resolution import IterationResolution
from budget_forecaster.infrastructure.persistence.repository_interface import (
    RepositoryInterface,
)


class IterationResolutionService:
    """Read and record what the user decided about unmatched iterations."""

    def __init__(self, repository: RepositoryInterface) -> None:
        self._repository = repository

    def get_all_resolutions(self) -> tuple[IterationResolution, ...]:
        """Get every stored decision, oldest iteration first."""
        return self._repository.get_iteration_resolutions()

    def get_resolutions_for_planned_operation(
        self, planned_operation_id: PlannedOperationId
    ) -> tuple[IterationResolution, ...]:
        """Get the decisions taken on one planned operation, oldest iteration first."""
        return self._repository.get_iteration_resolutions(planned_operation_id)

    def skip(
        self,
        planned_operation_id: PlannedOperationId,
        iteration_date: IterationDate,
        note: str | None = None,
    ) -> IterationResolution:
        """Declare that an iteration never happened, so it stops being counted."""
        return self._store(
            IterationResolution(
                planned_operation_id=planned_operation_id,
                iteration_date=iteration_date,
                action=IterationAction.SKIP,
                note=note,
                decided_at=datetime.now(timezone.utc),
            )
        )

    def postpone(
        self,
        planned_operation_id: PlannedOperationId,
        iteration_date: IterationDate,
        postponed_to: date,
        note: str | None = None,
    ) -> IterationResolution:
        """Move an iteration to a later date, where the forecast counts it."""
        return self._store(
            IterationResolution(
                planned_operation_id=planned_operation_id,
                iteration_date=iteration_date,
                action=IterationAction.POSTPONE,
                postponed_to=postponed_to,
                note=note,
                decided_at=datetime.now(timezone.utc),
            )
        )

    def restore(
        self,
        planned_operation_id: PlannedOperationId,
        iteration_date: IterationDate,
    ) -> None:
        """Drop the decision, letting the iteration go back to its derived state."""
        self._repository.delete_iteration_resolution(
            planned_operation_id, iteration_date
        )

    def _store(self, resolution: IterationResolution) -> IterationResolution:
        self._repository.upsert_iteration_resolution(resolution)
        return resolution
