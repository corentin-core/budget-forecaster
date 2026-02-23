"""Dashboard screen showing account summary."""

from datetime import date
from typing import Any

from dateutil.relativedelta import relativedelta
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from budget_forecaster.core.types import Category
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import (
    ApplicationService,
    UpcomingIteration,
)
from budget_forecaster.services.operation.operation_service import OperationFilter


class StatCard(Static):
    """A card displaying a statistic."""

    DEFAULT_CSS = """
    StatCard {
        width: 1fr;
        height: 5;
        border: solid $primary;
        padding: 0 1;
        margin: 0 1;
    }

    StatCard .stat-title {
        color: $text-muted;
    }

    StatCard .stat-value {
        text-style: bold;
    }

    StatCard .stat-positive {
        color: $success;
    }

    StatCard .stat-negative {
        color: $error;
    }
    """

    def __init__(self, title: str, value: str = "-", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._value = value
        self._is_negative = False

    def compose(self) -> ComposeResult:
        yield Static(self._title, classes="stat-title")
        yield Static(self._value, classes="stat-value", id="value")

    def update_value(self, value: str, is_negative: bool = False) -> None:
        """Update the displayed value."""
        self._value = value
        self._is_negative = is_negative
        value_widget = self.query_one("#value", Static)
        value_widget.update(value)
        value_widget.remove_class("stat-positive", "stat-negative")
        if is_negative:
            value_widget.add_class("stat-negative")
        else:
            value_widget.add_class("stat-positive")


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
        yield Static(f"{self._amount:+.2f} €", classes="cat-amount")

        # Create a simple progress bar
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
    """Dashboard screen showing account summary and statistics."""

    DEFAULT_CSS = """
    DashboardScreen {
        width: 100%;
        height: 1fr;
    }

    #stats-row {
        height: 7;
        margin-bottom: 1;
    }

    #categories-section {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }

    #categories-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #categories-list {
        height: 1fr;
        overflow-y: auto;
    }

    #upcoming-section {
        height: auto;
        max-height: 12;
        border: solid $primary;
        padding: 1;
        margin-top: 1;
    }

    #upcoming-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #upcoming-list {
        height: auto;
        max-height: 8;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="stats-row"):
            yield StatCard(_("Current balance"), id="balance-card")
            yield StatCard(_("Operations this month"), id="month-ops-card")
            yield StatCard(_("Expenses this month"), id="month-expenses-card")
            yield StatCard(_("Uncategorized"), id="uncategorized-card")

        with Vertical(id="categories-section"):
            yield Static(_("Expenses by category (this month)"), id="categories-title")
            yield Vertical(id="categories-list")

        with Vertical(id="upcoming-section"):
            yield Static(
                _("Upcoming planned operations (next 30 days)"),
                id="upcoming-title",
            )
            yield Vertical(id="upcoming-list")

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service and refresh.

        Args:
            service: The application service to get data from.
        """
        self._app_service = service
        self._update_stats()
        self._update_categories()
        self._update_upcoming()

    def _update_stats(self) -> None:
        """Update the statistics cards."""
        if not self._app_service:
            return

        # Balance
        balance = self._app_service.balance
        balance_card = self.query_one("#balance-card", StatCard)
        balance_card.update_value(
            f"{balance:,.2f} {self._app_service.currency}",
            is_negative=balance < 0,
        )

        # Current month operations
        now = date.today()
        month_start = date(now.year, now.month, 1)
        month_filter = OperationFilter(date_from=month_start)
        month_ops = self._app_service.get_operations(month_filter)

        month_ops_card = self.query_one("#month-ops-card", StatCard)
        month_ops_card.update_value(str(len(month_ops)))

        # Month expenses
        expenses = sum(op.amount for op in month_ops if op.amount < 0)
        expenses_card = self.query_one("#month-expenses-card", StatCard)
        expenses_card.update_value(f"{expenses:,.2f} €", is_negative=expenses < 0)

        # Uncategorized
        uncategorized = self._app_service.get_uncategorized_operations()
        uncat_card = self.query_one("#uncategorized-card", StatCard)
        uncat_card.update_value(
            str(len(uncategorized)),
            is_negative=len(uncategorized) > 0,
        )

    def _update_categories(self) -> None:
        """Update the category breakdown."""
        if not self._app_service:
            return

        # Get current month's category totals
        now = date.today()
        month_start = date(now.year, now.month, 1)
        month_filter = OperationFilter(date_from=month_start)

        totals = self._app_service.get_category_totals(month_filter)

        # Filter to only expenses (negative amounts) and sort by amount
        expense_totals = {cat: amount for cat, amount in totals.items() if amount < 0}
        sorted_categories = sorted(
            expense_totals.items(), key=lambda x: x[1]
        )  # Most negative first

        # Calculate max for bar scaling
        max_expense = abs(min(expense_totals.values())) if expense_totals else 0

        # Update the list
        categories_list = self.query_one("#categories-list", Vertical)
        categories_list.remove_children()

        for cat, amount in sorted_categories[:15]:  # Top 15 expenses
            if cat not in (Category.OTHER, Category.UNCATEGORIZED) or amount != 0:
                row = CategoryRow(cat.display_name, amount, max_expense)
                categories_list.mount(row)

    def _update_upcoming(self) -> None:
        """Update the upcoming planned operations section."""
        if not self._app_service:
            return

        iterations = self._app_service.get_upcoming_planned_iterations()

        upcoming_list = self.query_one("#upcoming-list", Vertical)
        upcoming_list.remove_children()

        if not iterations:
            upcoming_list.mount(Static(_("No upcoming planned operations")))
            return

        for iteration in iterations:
            upcoming_list.mount(UpcomingOperationRow(iteration))
