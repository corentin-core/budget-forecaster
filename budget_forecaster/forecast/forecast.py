"""Module for the Forecast class."""
from typing import NamedTuple

from budget_forecaster.operation_range.budget import Budget
from budget_forecaster.operation_range.planned_operation import PlannedOperation


class Forecast(NamedTuple):
    """A forecast is a list of planned operations and budgets."""

    operations: tuple[PlannedOperation, ...]
    budgets: tuple[Budget, ...]
