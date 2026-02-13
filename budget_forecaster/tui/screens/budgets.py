"""Budgets management screen for budget forecaster."""

import logging
from datetime import date

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Static

from budget_forecaster.core.date_range import RecurringDateRange
from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService

logger = logging.getLogger(__name__)


class BudgetsWidget(Vertical):
    """Widget for managing budgets."""

    DEFAULT_CSS = """
    BudgetsWidget {
        height: 1fr;
    }

    BudgetsWidget #budgets-header {
        height: 3;
        margin-bottom: 1;
    }

    BudgetsWidget #budgets-title {
        width: 1fr;
        padding: 0 1;
    }

    BudgetsWidget #budgets-buttons {
        width: auto;
    }

    BudgetsWidget Button {
        margin-left: 1;
    }

    BudgetsWidget #budgets-table {
        height: 1fr;
    }

    BudgetsWidget #budgets-status {
        height: 1;
        padding: 0 1;
    }
    """

    class BudgetSelected(Message):
        """Message sent when a budget is selected."""

        def __init__(self, budget: Budget | None) -> None:
            super().__init__()
            self.budget = budget

    class BudgetEditRequested(Message):
        """Message sent when budget edit is requested."""

        def __init__(self, budget: Budget | None) -> None:
            super().__init__()
            self.budget = budget  # None for new budget

    class BudgetDeleteRequested(Message):
        """Message sent when budget delete is requested."""

        def __init__(self, budget: Budget) -> None:
            super().__init__()
            self.budget = budget

    class BudgetSplitRequested(Message):
        """Message sent when budget split is requested."""

        def __init__(self, budget: Budget) -> None:
            super().__init__()
            self.budget = budget

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None
        self._budgets: tuple[Budget, ...] = ()
        self._selected_budget: Budget | None = None

    def compose(self) -> ComposeResult:
        """Create the widget layout."""
        with Horizontal(id="budgets-header"):
            yield Static(_("Budgets"), id="budgets-title")
            with Horizontal(id="budgets-buttons"):
                yield Button(_("Add"), id="btn-add-budget", variant="primary")
                yield Button(_("Edit"), id="btn-edit-budget", variant="default")
                yield Button(_("Split"), id="btn-split-budget", variant="default")
                yield Button(_("Delete"), id="btn-delete-budget", variant="error")

        yield DataTable(id="budgets-table")
        yield Static("", id="budgets-status")

    def on_mount(self) -> None:
        """Initialize the widget after mounting."""
        table = self.query_one("#budgets-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(
            "ID",
            _("Description"),
            _("Amount"),
            _("Category"),
            _("Start"),
            _("Duration"),
            _("Period"),
            _("End"),
        )
        self._update_button_states()

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service and refresh data."""
        self._app_service = service
        self.refresh_data()

    def refresh_data(self) -> None:
        """Refresh the budgets list from the database."""
        if self._app_service is None:
            return

        self._budgets = self._app_service.get_all_budgets()
        self._populate_table()
        self._update_status()
        self._update_button_states()

    def _populate_table(self) -> None:
        """Populate the data table with budgets."""
        table = self.query_one("#budgets-table", DataTable)
        table.clear()

        for budget in self._budgets:
            time_range = budget.date_range
            start_date = time_range.start_date.strftime("%Y-%m-%d")

            # Determine duration and periodicity
            if isinstance(time_range, RecurringDateRange):
                duration = self._format_duration(time_range.base_date_range)
                period = self._format_period(time_range.period)
                end_date = (
                    time_range.last_date.strftime("%Y-%m-%d")
                    if time_range.last_date != date.max
                    else "-"
                )
            else:
                duration = self._format_duration(time_range)
                period = "-"
                end_date = time_range.last_date.strftime("%Y-%m-%d")

            table.add_row(
                str(budget.id),
                budget.description,
                f"{budget.amount:.2f} {budget.currency}",
                budget.category.display_name,
                start_date,
                duration,
                period,
                end_date,
                key=str(budget.id),
            )

    def _format_duration(self, date_range) -> str:
        """Format the duration of a date range."""
        days = (date_range.last_date - date_range.start_date).days + 1
        if days == 1:
            return _("1 day")
        if days < 7:
            return _("{} days").format(days)
        if days < 30:
            weeks = days // 7
            return _("{} wk.").format(weeks) if weeks > 1 else "1 wk."
        if days < 365:
            months = days // 30
            return _("{} mo.").format(months)
        years = days // 365
        return _("{} yr.").format(years)

    def _format_period(self, period) -> str:
        """Format a relativedelta period."""
        if period.years:
            return _("{} yr.").format(period.years)
        if period.months:
            return _("{} mo.").format(period.months)
        if period.weeks:
            return _("{} wk.").format(period.weeks)
        if period.days:
            return _("{} d.").format(period.days)
        return "-"

    def _update_status(self) -> None:
        """Update the status display."""
        status = self.query_one("#budgets-status", Static)
        count = len(self._budgets)
        status.update(_("{} budget(s) configured").format(count))

    def _update_button_states(self) -> None:
        """Update button enabled states based on selection."""
        has_selection = self._selected_budget is not None
        self.query_one("#btn-edit-budget", Button).disabled = not has_selection
        self.query_one("#btn-delete-budget", Button).disabled = not has_selection

        # Split is only available for periodic budgets
        can_split = (
            has_selection
            and self._selected_budget is not None
            and isinstance(self._selected_budget.date_range, RecurringDateRange)
        )
        self.query_one("#btn-split-budget", Button).disabled = not can_split

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table."""
        if event.row_key is None:
            self._selected_budget = None
        else:
            budget_id = int(str(event.row_key.value))
            self._selected_budget = next(
                (b for b in self._budgets if b.id == budget_id), None
            )
        self._update_button_states()
        self.post_message(self.BudgetSelected(self._selected_budget))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-add-budget":
            self.post_message(self.BudgetEditRequested(None))
        elif event.button.id == "btn-edit-budget":
            if self._selected_budget:
                self.post_message(self.BudgetEditRequested(self._selected_budget))
        elif event.button.id == "btn-split-budget":
            if self._selected_budget and isinstance(
                self._selected_budget.date_range, RecurringDateRange
            ):
                self.post_message(self.BudgetSplitRequested(self._selected_budget))
        elif event.button.id == "btn-delete-budget":
            if self._selected_budget:
                self.post_message(self.BudgetDeleteRequested(self._selected_budget))
