"""TUI screens for budget forecaster."""

from budget_forecaster.tui.screens.budgets import BudgetsWidget
from budget_forecaster.tui.screens.dashboard import DashboardScreen
from budget_forecaster.tui.screens.forecast import ForecastWidget
from budget_forecaster.tui.screens.imports import ImportWidget
from budget_forecaster.tui.screens.operations import OperationsScreen
from budget_forecaster.tui.screens.planned_operations import PlannedOperationsWidget

__all__ = [
    "BudgetsWidget",
    "DashboardScreen",
    "ForecastWidget",
    "ImportWidget",
    "OperationsScreen",
    "PlannedOperationsWidget",
]
