"""Module to actualize a forecast with actual data."""
import logging
from datetime import datetime, timedelta
from typing import Final, Iterable

from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account
from budget_forecaster.amount import Amount
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.operation_link import LinkType, OperationLink
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.types import (
    BudgetId,
    IterationDate,
    OperationId,
    PlannedOperationId,
)

logger = logging.getLogger(__name__)


class ForecastActualizer:  # pylint: disable=too-few-public-methods
    """Actualize a forecast with actual data."""

    def __init__(
        self,
        account: Account,
        operation_links: tuple[OperationLink, ...] = (),
    ) -> None:
        self.__account: Final = account
        self.__operation_links: Final = operation_links
        # Internal indexes built from operation_links
        self.__linked_iterations: dict[PlannedOperationId, set[IterationDate]] = {}
        self.__linked_op_ids: dict[
            tuple[BudgetId, IterationDate], set[OperationId]
        ] = {}
        self.__build_indexes()

    def __build_indexes(self) -> None:
        """Build internal indexes from operation links for efficient lookups."""
        for link in self.__operation_links:
            match link.linked_type:
                case LinkType.PLANNED_OPERATION:
                    self.__linked_iterations.setdefault(link.linked_id, set()).add(
                        link.iteration_date
                    )
                case LinkType.BUDGET:
                    key = (link.linked_id, link.iteration_date)
                    self.__linked_op_ids.setdefault(key, set()).add(
                        link.operation_unique_id
                    )
        logger.debug(
            "Built indexes from %d links: %d planned op entries, %d budget entries",
            len(self.__operation_links),
            len(self.__linked_iterations),
            len(self.__linked_op_ids),
        )

    def __call__(self, forecast: Forecast) -> Forecast:
        actualized_planned_operations = self.__actualize_planned_operations(
            forecast.operations
        )
        actualized_budgets = self.__actualize_budgets(forecast.budgets)
        return Forecast(actualized_planned_operations, actualized_budgets)

    def __get_linked_iterations(
        self, planned_operation: PlannedOperation
    ) -> set[datetime]:
        """Get iteration dates linked to a planned operation."""
        if planned_operation.id is None:
            return set()
        return self.__linked_iterations.get(planned_operation.id, set())

    def __get_linked_operation_ids(
        self, budget: Budget, iteration_date: IterationDate
    ) -> set[OperationId]:
        """Get operation IDs linked to a budget for a specific iteration."""
        if budget.id is None:
            return set()
        return self.__linked_op_ids.get((budget.id, iteration_date), set())

    def __actualize_planned_operation_with_links(
        self, planned_operation: PlannedOperation, linked_iterations: set[datetime]
    ) -> PlannedOperation | None:
        """Actualize a planned operation using linked iterations as source of truth."""
        balance_date = self.__account.balance_date

        # Find the last linked iteration up to balance_date
        if not (past_iterations := [d for d in linked_iterations if d <= balance_date]):
            # No past iterations linked, keep the operation as-is if future
            if planned_operation.time_range.is_future(balance_date):
                return planned_operation
            # Current/past operation with no links: advance to next period
            next_time_range = planned_operation.time_range.next_time_range(balance_date)
            if next_time_range is None:
                return None
            return planned_operation.replace(
                time_range=planned_operation.time_range.replace(
                    initial_date=next_time_range.initial_date
                )
            )

        last_linked_iteration = max(past_iterations)

        # Advance the planned operation to start after the last linked iteration
        next_time_range = planned_operation.time_range.next_time_range(
            last_linked_iteration
        )
        if next_time_range is None:
            return None

        return planned_operation.replace(
            time_range=planned_operation.time_range.replace(
                initial_date=next_time_range.initial_date
            )
        )

    def __actualize_planned_operations(
        self, planned_operations: Iterable[PlannedOperation]
    ) -> tuple[PlannedOperation, ...]:
        actualized_planned_operations: list[PlannedOperation] = []

        for planned_operation in sorted(
            planned_operations, key=lambda op: op.time_range.initial_date
        ):
            linked_iterations = self.__get_linked_iterations(planned_operation)
            updated = self.__actualize_planned_operation_with_links(
                planned_operation, linked_iterations
            )
            if updated is not None:
                actualized_planned_operations.append(updated)

        return tuple(actualized_planned_operations)

    def __compute_consumed_budget_amount(
        self, operation_amount: float, budget_amount: float
    ) -> float:
        return (
            min(operation_amount, budget_amount)
            if budget_amount > 0.0
            else max(operation_amount, budget_amount)
        )

    def __actualize_budget_with_links(
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
        operations_by_id = {op.unique_id: op for op in self.__account.operations}

        for op_id in linked_op_ids:
            if op_id not in operations_by_id:
                continue
            operation = operations_by_id[op_id]

            # Skip if sign mismatch (positive budget expects positive operations)
            if operation.amount * updated_amount < 0.0:
                continue

            consumed_amount = self.__compute_consumed_budget_amount(
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
        new_budget_start = self.__account.balance_date + timedelta(days=1)
        if new_budget_start > budget.time_range.last_date:
            return None

        return budget.replace(
            time_range=budget.time_range.replace(
                initial_date=new_budget_start,
                duration=budget.time_range.last_date
                - new_budget_start
                + relativedelta(days=1),
            ),
            amount=Amount(updated_amount, budget.currency),
        )

    def __actualize_budgets(self, budgets: Iterable[Budget]) -> tuple[Budget, ...]:
        updated_budgets: list[Budget] = []

        for budget in sorted(
            budgets, key=lambda b: (b.time_range.initial_date, b.time_range.last_date)
        ):
            balance_date = self.__account.balance_date
            if budget.time_range.is_expired(balance_date):
                # the budget is obsolete, discard it
                continue

            current_time_range = budget.time_range.current_time_range(balance_date)
            if current_time_range is not None:
                # create a budget for the current period and update it
                current_budget = budget.replace(time_range=current_time_range)
                iteration_date = current_time_range.initial_date

                linked_op_ids = self.__get_linked_operation_ids(
                    current_budget, iteration_date
                )
                new_budget = self.__actualize_budget_with_links(
                    current_budget, linked_op_ids
                )

                if new_budget is not None:
                    updated_budgets.append(new_budget)

                # update renewable budget to start after the current period
                if (
                    next_time_range := budget.time_range.next_time_range(balance_date)
                ) is not None:
                    # update renewable budget for the next period
                    updated_budgets.append(
                        budget.replace(
                            time_range=budget.time_range.replace(
                                initial_date=next_time_range.initial_date
                            )
                        )
                    )
                continue

            if budget.time_range.is_future(balance_date):
                updated_budgets.append(budget)

        return tuple(updated_budgets)
