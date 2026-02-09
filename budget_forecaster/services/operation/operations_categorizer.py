"""Module to categorize operations from a given forecast."""
from typing import Iterable

from budget_forecaster.domain.forecast.forecast import Forecast
from budget_forecaster.domain.operation.historic_operation import HistoricOperation


def categorize_operations(
    operations: Iterable[HistoricOperation], forecast: Forecast
) -> tuple[HistoricOperation, ...]:
    """Categorize operations based on planned operations in the forecast.

    For each operation, checks planned operations in order. The first planned
    operation whose matcher matches on description, amount, and date range
    assigns its category to the operation.

    Args:
        operations: The historic operations to categorize.
        forecast: The forecast containing planned operations to match against.

    Returns:
        The operations with updated categories where matches were found.
    """
    categorized_operations: dict[int, HistoricOperation] = {
        op.unique_id: op for op in operations
    }
    for operation in categorized_operations.values():
        for planned_operation in forecast.operations:
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
