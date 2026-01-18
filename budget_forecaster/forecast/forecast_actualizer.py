"""Module to actualize a forecast with actual data."""
from datetime import timedelta
from typing import Final, Iterable

from dateutil.relativedelta import relativedelta

from budget_forecaster.account.account import Account
from budget_forecaster.amount import Amount
from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.operation_range.planned_operation import PlannedOperation
from budget_forecaster.time_range import DailyTimeRange, TimeRangeInterface
from budget_forecaster.types import OperationId


class ForecastActualizer:  # pylint: disable=too-few-public-methods
    """Actualize a forecast with actual data."""

    def __init__(self, account: Account) -> None:
        self.__not_assigned_operations: dict[OperationId, HistoricOperation] = {}
        self.__assigned_operations: dict[OperationId, HistoricOperation] = {}
        self.__account: Final = account

    def __call__(self, forecast: Forecast) -> Forecast:
        self.__not_assigned_operations = {
            operation.unique_id: operation for operation in self.__account.operations
        }
        self.__assigned_operations.clear()

        actualized_planned_operations = self.__actualize_planned_operations(
            forecast.operations
        )
        actualized_budgets = self.__actualize_budgets(forecast.budgets)

        self.__not_assigned_operations.clear()
        self.__assigned_operations.clear()

        return Forecast(actualized_planned_operations, actualized_budgets)

    def __assign_operation(self, operation: HistoricOperation) -> None:
        self.__assigned_operations[operation.unique_id] = operation
        self.__not_assigned_operations.pop(operation.unique_id)

    def __handle_late_operations(
        self, planned_operation: PlannedOperation
    ) -> tuple[PlannedOperation, ...]:
        actualized_planned_operations: list[PlannedOperation] = []
        matcher = planned_operation.matcher
        balance_date = self.__account.balance_date

        if not (
            late_time_ranges := tuple(
                matcher.late_time_ranges(
                    balance_date, self.__not_assigned_operations.values()
                )
            )
        ):
            return tuple(actualized_planned_operations)

        # some operations are late, postpone them in the future
        postponed_operation_date = balance_date + timedelta(days=1)
        actualized_planned_operations.extend(
            (
                planned_operation.replace(
                    time_range=DailyTimeRange(postponed_operation_date)
                ),
            )
            * len(late_time_ranges)
        )

        # update the periodic planned operation to start after the postponed operations
        if (
            next_time_range := planned_operation.time_range.next_time_range(
                postponed_operation_date
            )
        ) is not None:
            actualized_planned_operations.append(
                planned_operation.replace(
                    time_range=planned_operation.time_range.replace(
                        initial_date=next_time_range.initial_date
                    )
                )
            )

        return tuple(actualized_planned_operations)

    def __handle_anticipated_operations(
        self, planned_operation: PlannedOperation
    ) -> PlannedOperation | None:
        balance_date = self.__account.balance_date
        updated_planned_operation = planned_operation

        last_executed_time_range: TimeRangeInterface | None = None
        for (
            anticipated_time_range,
            anticipated_operation,
        ) in planned_operation.matcher.anticipated_time_ranges(
            balance_date, self.__not_assigned_operations.values()
        ):
            if anticipated_operation.unique_id in self.__assigned_operations:
                continue

            self.__assign_operation(anticipated_operation)
            last_executed_time_range = anticipated_time_range

        if last_executed_time_range is not None:
            next_time_range = updated_planned_operation.time_range.next_time_range(
                last_executed_time_range.initial_date
            )
            if next_time_range is None:
                return None
            updated_planned_operation = updated_planned_operation.replace(
                time_range=planned_operation.time_range.replace(
                    initial_date=next_time_range.initial_date
                )
            )

        return updated_planned_operation

    def __actualize_planned_operations(
        self, planned_operations: Iterable[PlannedOperation]
    ) -> tuple[PlannedOperation, ...]:
        actualized_planned_operations: list[PlannedOperation] = []

        balance_date = self.__account.balance_date
        for planned_operation in sorted(
            planned_operations, key=lambda op: op.time_range.initial_date
        ):
            if update := self.__handle_late_operations(planned_operation):
                actualized_planned_operations.extend(update)
                continue

            updated_planned_operation = self.__handle_anticipated_operations(
                planned_operation
            )
            if updated_planned_operation is None:
                continue

            if updated_planned_operation.time_range.is_future(balance_date):
                actualized_planned_operations.append(updated_planned_operation)
                continue

            next_time_range = updated_planned_operation.time_range.next_time_range(
                balance_date
            )
            if next_time_range is None:
                continue

            actualized_planned_operations.append(
                updated_planned_operation.replace(
                    time_range=planned_operation.time_range.replace(
                        initial_date=next_time_range.initial_date
                    )
                )
            )

        return tuple(actualized_planned_operations)

    def __compute_consumed_budget_amount(
        self, operation_amount: float, budget_amount: float
    ) -> float:
        return (
            min(operation_amount, budget_amount)
            if budget_amount > 0.0
            else max(operation_amount, budget_amount)
        )

    def __actualize_budget(self, budget: Budget) -> Budget | None:
        updated_amount = budget.amount
        matcher = budget.matcher
        for operation in sorted(
            matcher.matches(self.__account.operations), key=lambda op: op.date
        ):
            if operation.amount * updated_amount < 0.0:
                continue

            if operation.unique_id not in self.__assigned_operations:
                self.__assign_operation(operation)
                consumed_amount = self.__compute_consumed_budget_amount(
                    operation.amount, updated_amount
                )
            else:
                unassigned_operation_amount = (
                    operation.amount
                    - self.__assigned_operations[operation.unique_id].amount
                )
                consumed_amount = self.__compute_consumed_budget_amount(
                    unassigned_operation_amount, updated_amount
                )
            updated_amount -= consumed_amount
            self.__assigned_operations[operation.unique_id] = operation.replace(
                amount=Amount(consumed_amount, operation.currency)
            )
            if updated_amount == 0.0:
                return None
        if updated_amount == 0.0:
            # budget is fully consumed
            return None
        new_budget_start = self.__account.balance_date + timedelta(days=1)
        if new_budget_start > budget.time_range.last_date:
            # this was the last day for this budget
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
                new_budget = self.__actualize_budget(
                    budget.replace(
                        time_range=current_time_range,
                    )
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
