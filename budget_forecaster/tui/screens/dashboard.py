"""Dashboard screen showing account summary."""

from datetime import date
from typing import Any

from dateutil.relativedelta import relativedelta
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from budget_forecaster.core.types import LinkType, MatcherKey, OperationId, TargetName
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import (
    ApplicationService,
    UpcomingIteration,
)
from budget_forecaster.services.operation.operation_service import OperationFilter
from budget_forecaster.tui.modals.operation_detail import OperationDetailModal
from budget_forecaster.tui.symbols import DisplaySymbol
from budget_forecaster.tui.widgets.operation_table import OperationTable


class CategoryRow(Horizontal):
    """A row showing a category total."""

    DEFAULT_CSS = """
    CategoryRow {
        height: 1;
        width: 100%;
    }

    CategoryRow .cat-name {
        width: 30;
    }

    CategoryRow .cat-amount {
        width: 15;
        text-align: right;
    }

    CategoryRow .cat-bar {
        width: 1fr;
        margin-left: 1;
    }
    """

    def __init__(
        self, name: str, amount: float, max_amount: float, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._cat_name: str = name
        self._amount: float = amount
        self._max_amount: float = max_amount

    def compose(self) -> ComposeResult:
        yield Static(self._cat_name, classes="cat-name")
        yield Static(f"{self._amount:+.2f} {DisplaySymbol.EURO}", classes="cat-amount")

        if self._max_amount > 0:
            progress_width = int(abs(self._amount) / self._max_amount * 20)
            progress_bar = "█" * progress_width
        else:
            progress_bar = ""
        yield Static(progress_bar, classes="cat-bar")


def format_period(period: relativedelta | None) -> str:
    """Format a relativedelta period for display."""
    if period is None:
        return "-"
    if period.years:
        return _("{} yr.").format(period.years)
    if period.months:
        return _("{} mo.").format(period.months)
    if period.weeks:
        return _("{} wk.").format(period.weeks)
    if period.days:
        return _("{} d.").format(period.days)
    return "-"


class UpcomingHeaderRow(Horizontal):
    """Header row for the upcoming operations list."""

    DEFAULT_CSS = """
    UpcomingHeaderRow {
        height: 1;
        width: 100%;
        text-style: bold;
        color: $text-muted;
    }

    UpcomingHeaderRow .upcoming-date {
        width: 12;
    }

    UpcomingHeaderRow .upcoming-description {
        width: 1fr;
    }

    UpcomingHeaderRow .upcoming-amount {
        width: 15;
        text-align: right;
    }

    UpcomingHeaderRow .upcoming-period {
        width: 10;
        text-align: right;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(_("Date"), classes="upcoming-date")
        yield Static(_("Description"), classes="upcoming-description")
        yield Static(_("Amount"), classes="upcoming-amount")
        yield Static(_("Period"), classes="upcoming-period")


class UpcomingOperationRow(Horizontal):
    """A row showing an upcoming planned operation."""

    DEFAULT_CSS = """
    UpcomingOperationRow {
        height: 1;
        width: 100%;
    }

    UpcomingOperationRow .upcoming-date {
        width: 12;
    }

    UpcomingOperationRow .upcoming-description {
        width: 1fr;
    }

    UpcomingOperationRow .upcoming-amount {
        width: 15;
        text-align: right;
    }

    UpcomingOperationRow .upcoming-amount-negative {
        color: $error;
    }

    UpcomingOperationRow .upcoming-amount-positive {
        color: $success;
    }

    UpcomingOperationRow .upcoming-period {
        width: 10;
        text-align: right;
    }
    """

    def __init__(self, iteration: UpcomingIteration, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._iteration = iteration

    def compose(self) -> ComposeResult:
        it = self._iteration
        yield Static(it.iteration_date.strftime("%b %d"), classes="upcoming-date")
        yield Static(it.description, classes="upcoming-description")
        amount_class = (
            "upcoming-amount upcoming-amount-negative"
            if it.amount < 0
            else "upcoming-amount upcoming-amount-positive"
        )
        yield Static(f"{it.amount:+.2f} {it.currency}", classes=amount_class)
        yield Static(format_period(it.period), classes="upcoming-period")


class DashboardScreen(Vertical):
    """Dashboard screen showing account summary, categories, and recent operations."""

    DEFAULT_CSS = """
    DashboardScreen {
        height: 1fr;
    }

    DashboardScreen #stats-row {
        height: 3;
        margin-bottom: 1;
    }

    DashboardScreen #stats-row Static {
        width: 1fr;
        border: solid $primary;
        padding: 0 1;
        margin: 0 1;
    }

    DashboardScreen .stat-positive {
        color: $success;
    }

    DashboardScreen .stat-negative {
        color: $error;
    }

    DashboardScreen #upcoming-section {
        height: 10;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    DashboardScreen #upcoming-title {
        text-style: bold;
        margin-bottom: 1;
    }

    DashboardScreen #upcoming-list {
        height: 1fr;
        overflow-y: auto;
    }

    DashboardScreen #categories-section {
        height: 12;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    DashboardScreen #categories-title {
        text-style: bold;
        margin-bottom: 1;
    }

    DashboardScreen #categories-list {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="stats-row"):
            yield Static(_("Balance: -"), id="stat-balance")
            yield Static(_("Operations this month: -"), id="stat-month-ops")
            yield Static(_("Uncategorized: -"), id="stat-uncategorized")
        with Vertical(id="upcoming-section"):
            yield Static(
                _("Upcoming planned operations (next 30 days)"),
                id="upcoming-title",
            )
            yield Vertical(id="upcoming-list")
        with Vertical(id="categories-section"):
            yield Static(
                _("Expenses by category (this month)"),
                id="categories-title",
            )
            yield Vertical(id="categories-list")
        yield OperationTable(id="dashboard-table")

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service and refresh all sections."""
        self._app_service = service
        self._refresh()

    def _refresh(self) -> None:
        """Refresh all dashboard sections."""
        if not self._app_service:
            return
        self._update_stats()
        self._update_upcoming()
        self._update_categories()
        self._update_recent_operations()

    def _build_lookups(
        self,
    ) -> tuple[dict[OperationId, OperationLink], dict[MatcherKey, TargetName]]:
        """Build links and targets lookup dicts."""
        links: dict[OperationId, OperationLink] = {}
        targets: dict[MatcherKey, TargetName] = {}

        if not self._app_service:
            return links, targets

        for link in self._app_service.get_all_links():
            links[link.operation_unique_id] = link

        for planned_op in self._app_service.get_all_planned_operations():
            if planned_op.id is not None:
                key = MatcherKey(LinkType.PLANNED_OPERATION, planned_op.id)
                targets[key] = planned_op.description
        for budget in self._app_service.get_all_budgets():
            if budget.id is not None:
                key = MatcherKey(LinkType.BUDGET, budget.id)
                targets[key] = budget.description

        return links, targets

    def _update_stats(self) -> None:
        """Update the statistics row."""
        if not self._app_service:
            return

        balance = self._app_service.balance
        stat_balance = self.query_one("#stat-balance", Static)
        stat_balance.update(
            _("Balance: {} {}").format(f"{balance:,.2f}", self._app_service.currency)
        )
        stat_balance.remove_class("stat-positive", "stat-negative")
        stat_balance.add_class("stat-negative" if balance < 0 else "stat-positive")

        now = date.today()
        month, year = now.month - 3, now.year
        if month <= 0:
            month, year = month + 12, year - 1
        recent_filter = OperationFilter(date_from=date(year, month, 1))
        recent_ops = self._app_service.get_operations(recent_filter)
        self.query_one("#stat-month-ops", Static).update(
            _("Last 3 months: {} operations").format(len(recent_ops))
        )

        uncategorized = self._app_service.get_uncategorized_operations()
        stat_uncat = self.query_one("#stat-uncategorized", Static)
        stat_uncat.update(_("Uncategorized: {}").format(len(uncategorized)))
        stat_uncat.remove_class("stat-positive", "stat-negative")
        stat_uncat.add_class("stat-negative" if uncategorized else "stat-positive")

    def _update_upcoming(self) -> None:
        """Update the upcoming planned operations section."""
        if not self._app_service:
            return

        iterations = self._app_service.get_upcoming_planned_iterations()
        upcoming_list = self.query_one("#upcoming-list", Vertical)
        upcoming_list.remove_children()
        if not iterations:
            upcoming_list.mount(Static(_("No upcoming planned operations")))
        else:
            upcoming_list.mount(UpcomingHeaderRow())
            for iteration in iterations:
                upcoming_list.mount(UpcomingOperationRow(iteration))

    def _update_categories(self) -> None:
        """Update the expenses by category section."""
        if not self._app_service:
            return

        now = date.today()
        month_start = date(now.year, now.month, 1)
        month_filter = OperationFilter(date_from=month_start)
        totals = self._app_service.get_category_totals(month_filter)
        expense_totals = {cat: amt for cat, amt in totals.items() if amt < 0}
        sorted_categories = sorted(expense_totals.items(), key=lambda x: x[1])
        max_expense = abs(min(expense_totals.values())) if expense_totals else 0

        categories_list = self.query_one("#categories-list", Vertical)
        categories_list.remove_children()
        for cat, amount in sorted_categories[:10]:
            categories_list.mount(CategoryRow(cat.display_name, amount, max_expense))

    def _update_recent_operations(self) -> None:
        """Update the recent operations table with last 3 months."""
        if not self._app_service:
            return

        now = date.today()
        month, year = now.month - 3, now.year
        if month <= 0:
            month, year = month + 12, year - 1
        recent_filter = OperationFilter(date_from=date(year, month, 1))
        recent_ops = self._app_service.get_operations(recent_filter)

        links, targets = self._build_lookups()
        self.query_one("#dashboard-table", OperationTable).load_operations(
            recent_ops, links, targets
        )

    def on_operation_table_operation_selected(
        self, event: OperationTable.OperationSelected
    ) -> None:
        """Open operation detail modal from the dashboard table."""
        event.stop()
        if self._app_service:
            self.app.push_screen(
                OperationDetailModal(event.operation.unique_id, self._app_service),
                self._on_detail_modal_closed,
            )

    def _on_detail_modal_closed(self, modified: bool | None) -> None:
        """Refresh dashboard if data was modified."""
        if modified:
            self._refresh()
