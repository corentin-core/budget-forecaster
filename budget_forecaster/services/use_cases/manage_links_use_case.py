"""Use case for managing manual operation links."""

from datetime import date

from budget_forecaster.core.types import LinkType
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.operation.iteration_resolution_service import (
    IterationResolutionService,
)
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)


class ManageLinksUseCase:  # pylint: disable=too-few-public-methods
    """Create manual links between operations and targets."""

    def __init__(
        self,
        operation_link_service: OperationLinkService,
        iteration_resolution_service: IterationResolutionService,
    ) -> None:
        self._operation_link_service = operation_link_service
        self._iteration_resolution_service = iteration_resolution_service

    def create_manual_link(
        self,
        operation: HistoricOperation,
        target: PlannedOperation | Budget,
        iteration_date: date,
    ) -> OperationLink:
        """Create a manual link between an operation and a target.

        A matched iteration is settled, so any decision the user had recorded
        about it is dropped rather than left behind with an undo that does
        nothing: the lifecycle already gives the link precedence.

        Args:
            operation: The historic operation to link.
            target: The planned operation or budget to link to.
            iteration_date: The iteration date for the link.

        Returns:
            The created link.

        Raises:
            ValueError: If target has no ID.
        """
        if target.id is None:
            raise ValueError("Target must have an ID")

        target_type = (
            LinkType.PLANNED_OPERATION
            if isinstance(target, PlannedOperation)
            else LinkType.BUDGET
        )

        link = OperationLink(
            operation_unique_id=operation.unique_id,
            target_type=target_type,
            target_id=target.id,
            iteration_date=iteration_date,
            is_manual=True,
        )
        self._operation_link_service.upsert_link(link)
        if target_type is LinkType.PLANNED_OPERATION:
            self._iteration_resolution_service.restore(target.id, iteration_date)
        return link
