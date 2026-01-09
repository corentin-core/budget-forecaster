"""TUI screens for budget forecaster."""

from budget_forecaster.tui.screens.categorize import CategorizeScreen
from budget_forecaster.tui.screens.dashboard import DashboardScreen
from budget_forecaster.tui.screens.forecast import ForecastWidget
from budget_forecaster.tui.screens.imports import ImportWidget
from budget_forecaster.tui.screens.operations import OperationsScreen

__all__ = [
    "CategorizeScreen",
    "DashboardScreen",
    "ForecastWidget",
    "ImportWidget",
    "OperationsScreen",
]
