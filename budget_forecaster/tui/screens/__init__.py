"""TUI screens for budget forecaster."""

from budget_forecaster.tui.screens.analytics import AnalyticsWidget
from budget_forecaster.tui.screens.balance import BalanceWidget
from budget_forecaster.tui.screens.budgets import BudgetsWidget
from budget_forecaster.tui.screens.dashboard import DashboardScreen
from budget_forecaster.tui.screens.expense_breakdown import ExpenseBreakdownWidget
from budget_forecaster.tui.screens.imports import ImportWidget
from budget_forecaster.tui.screens.operations import OperationsScreen
from budget_forecaster.tui.screens.planned_operations import PlannedOperationsWidget
from budget_forecaster.tui.screens.review import ReviewWidget

__all__ = [
    "AnalyticsWidget",
    "BalanceWidget",
    "BudgetsWidget",
    "DashboardScreen",
    "ExpenseBreakdownWidget",
    "ImportWidget",
    "OperationsScreen",
    "PlannedOperationsWidget",
    "ReviewWidget",
]
