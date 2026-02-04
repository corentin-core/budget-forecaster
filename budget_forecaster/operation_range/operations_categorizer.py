"""Module to categorize operations from a given forecast."""
from typing import Iterable

from budget_forecaster.forecast.forecast import Forecast
from budget_forecaster.operation_range.historic_operation import HistoricOperation


class OperationsCategorizer:  # pylint: disable=too-few-public-methods
    """Categorizes operations from a given forecast."""

    def __init__(self, forecast: Forecast) -> None:
        self._forecast = forecast

    def __call__(
        self, operations: Iterable[HistoricOperation]
    ) -> tuple[HistoricOperation, ...]:
        categorized_operations: dict[int, HistoricOperation] = {
            op.unique_id: op for op in operations
        }
        for operation in categorized_operations.values():
            for planned_operation in self._forecast.operations:
                matcher = planned_operation.matcher
                if (
                    matcher.match_description(operation)
                    and matcher.match_amount(operation)
                    and matcher.match_date_range(operation)
                ):
                    categorized_operations[operation.unique_id] = operation.replace(
                        category=planned_operation.category
                    )
                    break
        return tuple(categorized_operations.values())
