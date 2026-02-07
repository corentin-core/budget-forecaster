"""Use case for managing planned operations and budgets (CRUD + split)."""

import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import RecurringDateRange
from budget_forecaster.core.types import (
    BudgetId,
    IterationDate,
    LinkType,
    MatcherKey,
    OperationId,
    PlannedOperationId,
    TargetId,
)
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.infrastructure.persistence.persistent_account import (
    PersistentAccount,
)
from budget_forecaster.services.forecast.forecast_service import ForecastService
from budget_forecaster.services.operation.operation_link_service import (
    OperationLinkService,
)
from budget_forecaster.services.use_cases.matcher_cache import MatcherCache

logger = logging.getLogger(__name__)


class ManageTargetsUseCase:
    """CRUD and split operations for planned operations and budgets."""

    def __init__(
        self,
        forecast_service: ForecastService,
        persistent_account: PersistentAccount,
        operation_link_service: OperationLinkService,
        matcher_cache: MatcherCache,
    ) -> None:
        self._forecast_service = forecast_service
        self._persistent_account = persistent_account
        self._operation_link_service = operation_link_service
        self._matcher_cache = matcher_cache

    # -------------------------------------------------------------------------
    # Planned operation CRUD
    # -------------------------------------------------------------------------

    def add_planned_operation(self, op: PlannedOperation) -> PlannedOperation:
        """Add a new planned operation and create heuristic links.

        Args:
            op: Planned operation to add (id should be None).

        Returns:
            The newly created planned operation with its assigned ID.
        """
        new_op = self._forecast_service.add_planned_operation(op)

        self._matcher_cache.add_matcher(new_op)

        if new_op.id is not None:
            operations = self._persistent_account.account.operations
            created_links = self._operation_link_service.create_heuristic_links(
                operations,
                {MatcherKey(LinkType.PLANNED_OPERATION, new_op.id): new_op.matcher},
            )
            logger.debug(
                "Created %d links for new planned operation %d",
                len(created_links),
                new_op.id,
            )

        return new_op

    def update_planned_operation(self, op: PlannedOperation) -> PlannedOperation:
        """Update a planned operation and recalculate its links.

        Args:
            op: Planned operation with updated values (id must not be None).

        Returns:
            The updated planned operation.
        """
        if op.id is None:
            raise ValueError("Planned operation must have a valid ID for update")

        updated_op = self._forecast_service.update_planned_operation(op)

        self._matcher_cache.add_matcher(updated_op)

        self._operation_link_service.delete_automatic_links_for_target(
            LinkType.PLANNED_OPERATION, op.id
        )
        operations = self._persistent_account.account.operations
        created_links = self._operation_link_service.create_heuristic_links(
            operations,
            {MatcherKey(LinkType.PLANNED_OPERATION, op.id): updated_op.matcher},
        )
        logger.debug(
            "Recalculated %d links for planned operation %d",
            len(created_links),
            op.id,
        )

        return updated_op

    def delete_planned_operation(self, op_id: PlannedOperationId) -> None:
        """Delete a planned operation and its links.

        Args:
            op_id: ID of the planned operation to delete.
        """
        self._operation_link_service.delete_links_for_target(
            LinkType.PLANNED_OPERATION, op_id
        )

        self._matcher_cache.remove_matcher(
            MatcherKey(LinkType.PLANNED_OPERATION, op_id)
        )

        self._forecast_service.delete_planned_operation(op_id)

    # -------------------------------------------------------------------------
    # Budget CRUD
    # -------------------------------------------------------------------------

    def add_budget(self, budget: Budget) -> Budget:
        """Add a new budget and create heuristic links.

        Args:
            budget: Budget to add (id should be None).

        Returns:
            The newly created budget with its assigned ID.
        """
        new_budget = self._forecast_service.add_budget(budget)

        self._matcher_cache.add_matcher(new_budget)

        if new_budget.id is not None:
            operations = self._persistent_account.account.operations
            created_links = self._operation_link_service.create_heuristic_links(
                operations,
                {MatcherKey(LinkType.BUDGET, new_budget.id): new_budget.matcher},
            )
            logger.debug(
                "Created %d links for new budget %d",
                len(created_links),
                new_budget.id,
            )

        return new_budget

    def update_budget(self, budget: Budget) -> Budget:
        """Update a budget and recalculate its links.

        Args:
            budget: Budget with updated values (id must not be None).

        Returns:
            The updated budget.
        """
        if budget.id is None:
            raise ValueError("Budget must have a valid ID for update")

        updated_budget = self._forecast_service.update_budget(budget)

        self._matcher_cache.add_matcher(updated_budget)

        self._operation_link_service.delete_automatic_links_for_target(
            LinkType.BUDGET, budget.id
        )
        operations = self._persistent_account.account.operations
        created_links = self._operation_link_service.create_heuristic_links(
            operations,
            {MatcherKey(LinkType.BUDGET, budget.id): updated_budget.matcher},
        )
        logger.debug(
            "Recalculated %d links for budget %d",
            len(created_links),
            budget.id,
        )

        return updated_budget

    def delete_budget(self, budget_id: BudgetId) -> None:
        """Delete a budget and its links.

        Args:
            budget_id: ID of the budget to delete.
        """
        self._operation_link_service.delete_links_for_target(LinkType.BUDGET, budget_id)

        self._matcher_cache.remove_matcher(MatcherKey(LinkType.BUDGET, budget_id))

        self._forecast_service.delete_budget(budget_id)

    # -------------------------------------------------------------------------
    # Split operations
    # -------------------------------------------------------------------------

    def get_next_non_actualized_iteration(
        self,
        target_type: LinkType,
        target_id: TargetId,
    ) -> IterationDate | None:
        """Find the next iteration that has no linked operation.

        Args:
            target_type: Type of target (PLANNED_OPERATION or BUDGET).
            target_id: ID of the target.

        Returns:
            The date of the next non-actualized iteration, or None if not found.
        """
        match target_type:
            case LinkType.PLANNED_OPERATION:
                target: PlannedOperation | Budget | None = (
                    self._forecast_service.get_planned_operation_by_id(target_id)
                )
            case LinkType.BUDGET:
                target = self._forecast_service.get_budget_by_id(target_id)

        if target is None or target.id is None:
            return None

        if not isinstance(target.date_range, RecurringDateRange):
            return None

        links = self._operation_link_service.load_links_for_target(target)
        actualized_dates = {link.iteration_date for link in links}

        today = date.today()
        for time_range in target.date_range.iterate_over_date_ranges(today):
            if time_range.start_date not in actualized_dates:
                return time_range.start_date

        return None

    def split_planned_operation_at_date(
        self,
        operation_id: OperationId,
        split_date: date,
        new_amount: Amount | None = None,
        new_period: relativedelta | None = None,
    ) -> PlannedOperation:
        """Split a planned operation at the given date.

        This terminates the original operation the day before split_date,
        creates a new operation starting at split_date with the updated values,
        and migrates links for iterations >= split_date to the new operation.

        Args:
            operation_id: ID of the planned operation to split.
            split_date: Date from which the new values apply.
            new_amount: New amount (if None, keeps the original).
            new_period: New period (if None, keeps the original).

        Returns:
            The newly created PlannedOperation.

        Raises:
            ValueError: If the operation doesn't exist or isn't periodic.
        """
        if (
            original := self._forecast_service.get_planned_operation_by_id(operation_id)
        ) is None:
            raise ValueError(f"Planned operation {operation_id} not found")

        terminated, continuation = original.split_at(split_date, new_amount, new_period)

        self._forecast_service.update_planned_operation(terminated)
        new_op = self._forecast_service.add_planned_operation(continuation)
        self._matcher_cache.add_matcher(new_op)

        if new_op.id is not None:
            self._migrate_links_after_split(
                LinkType.PLANNED_OPERATION,
                operation_id,
                new_op.id,
                split_date,
            )

        logger.info(
            "Split planned operation %d at %s, created new operation %d",
            operation_id,
            split_date,
            new_op.id,
        )

        return new_op

    def split_budget_at_date(
        self,
        budget_id: BudgetId,
        split_date: date,
        new_amount: Amount | None = None,
        new_period: relativedelta | None = None,
        new_duration: relativedelta | None = None,
    ) -> Budget:
        """Split a budget at the given date.

        This terminates the original budget the day before split_date,
        creates a new budget starting at split_date with the updated values,
        and migrates links for iterations >= split_date to the new budget.

        Args:
            budget_id: ID of the budget to split.
            split_date: Date from which the new values apply.
            new_amount: New amount (if None, keeps the original).
            new_period: New period (if None, keeps the original).
            new_duration: New duration (if None, keeps the original).

        Returns:
            The newly created Budget.

        Raises:
            ValueError: If the budget doesn't exist or isn't periodic.
        """
        if (original := self._forecast_service.get_budget_by_id(budget_id)) is None:
            raise ValueError(f"Budget {budget_id} not found")

        terminated, continuation = original.split_at(
            split_date, new_amount, new_period, new_duration
        )

        self._forecast_service.update_budget(terminated)
        new_budget = self._forecast_service.add_budget(continuation)
        self._matcher_cache.add_matcher(new_budget)

        if new_budget.id is not None:
            self._migrate_links_after_split(
                LinkType.BUDGET,
                budget_id,
                new_budget.id,
                split_date,
            )

        logger.info(
            "Split budget %d at %s, created new budget %d",
            budget_id,
            split_date,
            new_budget.id,
        )

        return new_budget

    def _migrate_links_after_split(
        self,
        target_type: LinkType,
        old_target_id: TargetId,
        new_target_id: TargetId,
        split_date: date,
    ) -> None:
        """Migrate links from old target to new target for iterations >= split_date.

        Args:
            target_type: Type of target (PLANNED_OPERATION or BUDGET).
            old_target_id: ID of the original target.
            new_target_id: ID of the new target.
            split_date: Date from which links should be migrated.
        """
        match target_type:
            case LinkType.PLANNED_OPERATION:
                old_target: PlannedOperation | Budget | None = (
                    self._forecast_service.get_planned_operation_by_id(old_target_id)
                )
            case LinkType.BUDGET:
                old_target = self._forecast_service.get_budget_by_id(old_target_id)

        if old_target is None:
            return

        links = self._operation_link_service.load_links_for_target(old_target)

        for link in links:
            if link.iteration_date >= split_date:
                self._operation_link_service.delete_link(link.operation_unique_id)
                new_link = OperationLink(
                    operation_unique_id=link.operation_unique_id,
                    target_type=target_type,
                    target_id=new_target_id,
                    iteration_date=link.iteration_date,
                    is_manual=link.is_manual,
                    notes=link.notes,
                )
                self._operation_link_service.upsert_link(new_link)
                logger.debug(
                    "Migrated link for operation %s from target %d to %d",
                    link.operation_unique_id,
                    old_target_id,
                    new_target_id,
                )
