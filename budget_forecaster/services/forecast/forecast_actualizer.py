"""Module to actualize a forecast with actual data."""
import logging
from datetime import date, timedelta
from typing import Final, Iterable

from dateutil.relativedelta import relativedelta

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import SingleDay
from budget_forecaster.core.types import (
    BudgetId,
    IterationDate,
    LinkType,
    OperationId,
    PlannedOperationId,
)
from budget_forecaster.domain.account.account import Account
from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.domain.operation.planned_operation import PlannedOperation

logger = logging.getLogger(__name__)


class ForecastActualizer:  # pylint: disable=too-few-public-methods
    """Actualize a forecast with actual data."""

    def __init__(
        self,
        account: Account,
        operation_links: tuple[OperationLink, ...] = (),
    ) -> None:
        self._account: Final = account
        self._operation_links: Final = operation_links
        # Internal indexes built from operation_links
        self._linked_iterations: dict[PlannedOperationId, set[IterationDate]] = {}
        self._linked_op_ids: dict[tuple[BudgetId, IterationDate], set[OperationId]] = {}
        # Map operation_id -> operation date for date lookups
        self._operation_dates: dict[OperationId, date] = {
            op.unique_id: op.operation_date for op in account.operations
        }
        # Map (planned_op_id, iteration_date) -> set of linked operation IDs
        self._planned_op_linked_ops: dict[
            tuple[PlannedOperationId, IterationDate], set[OperationId]
        ] = {}
        self._build_indexes()

    def _build_indexes(self) -> None:
        """Build internal indexes from operation links for efficient lookups."""
        for link in self._operation_links:
            match link.target_type:
                case LinkType.PLANNED_OPERATION:
                    self._linked_iterations.setdefault(link.target_id, set()).add(
                        link.iteration_date
                    )
                    # Also track which operations are linked to each iteration
                    key = (link.target_id, link.iteration_date)
                    self._planned_op_linked_ops.setdefault(key, set()).add(
                        link.operation_unique_id
                    )
                case LinkType.BUDGET:
                    key = (link.target_id, link.iteration_date)
                    self._linked_op_ids.setdefault(key, set()).add(
                        link.operation_unique_id
                    )
        logger.debug(
            "Built indexes from %d links: %d planned op entries, %d budget entries",
            len(self._operation_links),
            len(self._linked_iterations),
            len(self._linked_op_ids),
        )

    def __call__(self, forecast: Forecast) -> Forecast:
        actualized_planned_operations = self._actualize_planned_operations(
            forecast.operations
        )
        actualized_budgets = self._actualize_budgets(forecast.budgets)
        return Forecast(actualized_planned_operations, actualized_budgets)

    def _get_linked_iterations(self, planned_operation: PlannedOperation) -> set[date]:
        """Get iteration dates linked to a planned operation."""
        if planned_operation.id is None:
            return set()
        return self._linked_iterations.get(planned_operation.id, set())

    def _get_linked_operation_ids(
        self, budget: Budget, iteration_date: IterationDate
    ) -> set[OperationId]:
        """Get operation IDs linked to a budget for a specific iteration."""
        if budget.id is None:
            return set()
        return self._linked_op_ids.get((budget.id, iteration_date), set())

    def _get_late_iterations(
        self,
        planned_operation: PlannedOperation,
        linked_iterations: set[date],
    ) -> tuple[date, ...]:
        """Find iterations that are late (past due and no link).

        An iteration is considered late if:
        1. It's past (before balance_date) but within the approximation window
        2. It has no link to an operation

        Note: Heuristic matching is handled by automatic link creation during import,
        so we only need to check for links here.
        """
        if planned_operation.id is None:
            return ()

        balance_date = self._account.balance_date
        late_iterations: list[date] = []
        approximation = planned_operation.matcher.approximation_date_range

        # Iterate over date ranges starting before the approximation window
        for dr in planned_operation.date_range.iterate_over_date_ranges(
            balance_date - approximation
        ):
            # Stop if we've reached or passed balance_date (not late yet)
            if (iteration_date := dr.start_date) >= balance_date:
                break

            # Check if within the approximation window (not too old)
            if not dr.is_within(balance_date, approx_after=approximation):
                continue

            # Check if this iteration has a link - if not, it's late
            if iteration_date not in linked_iterations:
                late_iterations.append(iteration_date)

        return tuple(late_iterations)

    def _handle_late_iterations(
        self,
        planned_operation: PlannedOperation,
        late_iterations: tuple[date, ...],
    ) -> tuple[PlannedOperation, ...]:
        """Create postponed operations for late iterations.

        Returns a tuple of:
        - One SingleDay operation for each late iteration (postponed to tomorrow)
        - The original periodic operation advanced to after the postponed date (if applicable)
        """
        if not late_iterations:
            return ()

        balance_date = self._account.balance_date
        postponed_date = balance_date + timedelta(days=1)

        result: list[PlannedOperation] = []

        # Create one postponed operation per late iteration
        for _ in late_iterations:
            result.append(
                planned_operation.replace(date_range=SingleDay(postponed_date))
            )

        # Advance the periodic operation to start after the postponed date
        if (
            next_dr := planned_operation.date_range.next_date_range(postponed_date)
        ) is not None:
            result.append(
                planned_operation.replace(
                    date_range=planned_operation.date_range.replace(
                        start_date=next_dr.start_date
                    )
                )
            )

        logger.debug(
            "Postponed %d late iteration(s) for planned op %s to %s",
            len(late_iterations),
            planned_operation.id,
            postponed_date,
        )

        return tuple(result)

    def _is_iteration_actualized(
        self, planned_op_id: PlannedOperationId, iteration_date: IterationDate
    ) -> bool:
        """Check if an iteration is actualized (has been executed).

        An iteration is considered actualized if:
        1. The iteration date <= balance_date (normal case), OR
        2. A linked operation exists with date <= balance_date
           (operation happened early, before the planned iteration date)
        """
        balance_date = self._account.balance_date

        # Case 1: Iteration date has passed
        if iteration_date <= balance_date:
            return True

        # Case 2: Linked operation has already occurred (even if iteration is future)
        key = (planned_op_id, iteration_date)
        linked_op_ids = self._planned_op_linked_ops.get(key, set())
        for op_id in linked_op_ids:
            op_date = self._operation_dates.get(op_id)
            if op_date is not None and op_date <= balance_date:
                return True

        return False

    def _actualize_planned_operation_with_links(
        self, planned_operation: PlannedOperation, linked_iterations: set[date]
    ) -> PlannedOperation | None:
        """Actualize a planned operation using linked iterations as source of truth."""
        balance_date = self._account.balance_date

        if planned_operation.id is None:
            return planned_operation

        # Find actualized iterations (either past or linked to past operations)
        actualized_iterations = tuple(
            d
            for d in linked_iterations
            if self._is_iteration_actualized(planned_operation.id, d)
        )

        if not actualized_iterations:
            # No actualized iterations, keep the operation as-is if future
            if planned_operation.date_range.is_future(balance_date):
                return planned_operation
            # Current/past operation with no links: advance to next period
            if (
                next_dr := planned_operation.date_range.next_date_range(balance_date)
            ) is None:
                return None
            return planned_operation.replace(
                date_range=planned_operation.date_range.replace(
                    start_date=next_dr.start_date
                )
            )

        last_actualized_iteration = max(actualized_iterations)

        # Advance the planned operation to start after the last actualized iteration
        next_dr = planned_operation.date_range.next_date_range(
            last_actualized_iteration
        )
        if next_dr is None:
            return None

        return planned_operation.replace(
            date_range=planned_operation.date_range.replace(
                start_date=next_dr.start_date
            )
        )

    def _actualize_planned_operations(
        self, planned_operations: Iterable[PlannedOperation]
    ) -> tuple[PlannedOperation, ...]:
        actualized_planned_operations: list[PlannedOperation] = []

        for planned_operation in sorted(
            planned_operations, key=lambda op: op.date_range.start_date
        ):
            linked_iterations = self._get_linked_iterations(planned_operation)
            # Check for late iterations (past iterations without links)
            late_iterations = self._get_late_iterations(
                planned_operation, linked_iterations
            )
            if late_iterations:
                # Some iterations are late, postpone them to tomorrow
                postponed = self._handle_late_iterations(
                    planned_operation, late_iterations
                )
                actualized_planned_operations.extend(postponed)
            else:
                # No late iterations, use link-based actualization
                updated = self._actualize_planned_operation_with_links(
                    planned_operation, linked_iterations
                )
                if updated is not None:
                    actualized_planned_operations.append(updated)

        return tuple(actualized_planned_operations)

    def _compute_consumed_budget_amount(
        self, operation_amount: float, budget_amount: float
    ) -> float:
        return (
            min(operation_amount, budget_amount)
            if budget_amount > 0.0
            else max(operation_amount, budget_amount)
        )

    def _actualize_budget_with_links(
        self, budget: Budget, linked_op_ids: set[OperationId]
    ) -> Budget | None:
        """Actualize a budget using linked operations as source of truth."""
        logger.debug(
            "Actualizing budget %s (%s) with %d linked operations",
            budget.id,
            budget.category,
            len(linked_op_ids),
        )
        updated_amount = budget.amount
        operations_by_id = {op.unique_id: op for op in self._account.operations}

        for op_id in linked_op_ids:
            if op_id not in operations_by_id:
                continue
            operation = operations_by_id[op_id]

            # Skip if sign mismatch (positive budget expects positive operations)
            if operation.amount * updated_amount < 0.0:
                continue

            consumed_amount = self._compute_consumed_budget_amount(
                operation.amount, updated_amount
            )
            updated_amount -= consumed_amount

            if updated_amount == 0.0:
                logger.debug("Budget %s fully consumed", budget.id)
                return None

        consumed_total = budget.amount - updated_amount
        logger.debug(
            "Budget %s: consumed %.2f, remaining %.2f",
            budget.id,
            consumed_total,
            updated_amount,
        )
        new_budget_start = self._account.balance_date + timedelta(days=1)
        if new_budget_start > budget.date_range.last_date:
            return None

        return budget.replace(
            date_range=budget.date_range.replace(
                start_date=new_budget_start,
                duration=budget.date_range.last_date
                - new_budget_start
                + relativedelta(days=1),
            ),
            amount=Amount(updated_amount, budget.currency),
        )

    def _actualize_budgets(self, budgets: Iterable[Budget]) -> tuple[Budget, ...]:
        updated_budgets: list[Budget] = []

        for budget in sorted(
            budgets, key=lambda b: (b.date_range.start_date, b.date_range.last_date)
        ):
            balance_date = self._account.balance_date
            if budget.date_range.is_expired(balance_date):
                # the budget is obsolete, discard it
                continue

            if (
                current_dr := budget.date_range.current_date_range(balance_date)
            ) is not None:
                # create a budget for the current period and update it
                current_budget = budget.replace(date_range=current_dr)
                iteration_date = current_dr.start_date

                linked_op_ids = self._get_linked_operation_ids(
                    current_budget, iteration_date
                )
                new_budget = self._actualize_budget_with_links(
                    current_budget, linked_op_ids
                )

                if new_budget is not None:
                    updated_budgets.append(new_budget)

                # update renewable budget to start after the current period
                if (
                    next_dr := budget.date_range.next_date_range(balance_date)
                ) is not None:
                    # update renewable budget for the next period
                    updated_budgets.append(
                        budget.replace(
                            date_range=budget.date_range.replace(
                                start_date=next_dr.start_date
                            )
                        )
                    )
                continue

            if budget.date_range.is_future(balance_date):
                updated_budgets.append(budget)

        return tuple(updated_budgets)
