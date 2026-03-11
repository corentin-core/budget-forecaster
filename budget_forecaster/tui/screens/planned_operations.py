"""Planned operations management screen for budget forecaster."""

import logging
from datetime import date

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Static

from budget_forecaster.core.date_range import RecurringDay
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.tui.widgets.filter_bar import FilterBar, StatusFilter

logger = logging.getLogger(__name__)


class PlannedOperationsWidget(Vertical):
    """Widget for managing planned operations."""

    DEFAULT_CSS = """
    PlannedOperationsWidget {
        height: 1fr;
    }

    PlannedOperationsWidget #planned-ops-toolbar {
        height: auto;
        margin-bottom: 1;
    }

    PlannedOperationsWidget #btn-add-op {
        margin-right: 1;
    }

    PlannedOperationsWidget #planned-ops-table {
        height: 1fr;
    }

    PlannedOperationsWidget #planned-ops-status-bar {
        height: auto;
        padding: 0 1;
    }

    PlannedOperationsWidget #planned-ops-status {
        width: 1fr;
    }

    """

    class OperationSelected(Message):
        """Message sent when a planned operation is selected."""

        def __init__(self, operation: PlannedOperation | None) -> None:
            super().__init__()
            self.operation = operation

    class OperationEditRequested(Message):
        """Message sent when operation edit is requested."""

        def __init__(self, operation: PlannedOperation | None) -> None:
            super().__init__()
            self.operation = operation  # None for new operation

    class OperationDeleteRequested(Message):
        """Message sent when operation delete is requested."""

        def __init__(self, operation: PlannedOperation) -> None:
            super().__init__()
            self.operation = operation

    class OperationSplitRequested(Message):
        """Message sent when operation split is requested."""

        def __init__(self, operation: PlannedOperation) -> None:
            super().__init__()
            self.operation = operation

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None
        self._all_operations: tuple[PlannedOperation, ...] = ()
        self._filtered_operations: tuple[PlannedOperation, ...] = ()
        self._selected_operation: PlannedOperation | None = None
        self._search_text: str | None = None
        self._filter_category: Category | None = None
        self._status_filter: StatusFilter = StatusFilter.ACTIVE

    def compose(self) -> ComposeResult:
        """Create the widget layout."""
        with Horizontal(id="planned-ops-toolbar"):
            yield Button(_("Add"), id="btn-add-op", variant="primary")
            yield FilterBar(id="planned-ops-filter-bar", show_status_filter=True)
        yield DataTable(id="planned-ops-table")
        with Horizontal(id="planned-ops-status-bar"):
            yield Static("", id="planned-ops-status")

    def on_mount(self) -> None:
        """Initialize the widget after mounting."""
        table = self.query_one("#planned-ops-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(
            "ID",
            _("Description"),
            _("Amount"),
            _("Category"),
            _("Date"),
            _("Period"),
            _("End"),
            _("Keywords"),
        )

    @property
    def planned_operations(self) -> tuple[PlannedOperation, ...]:
        """Get the currently displayed (filtered) planned operations."""
        return self._filtered_operations

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service and refresh data."""
        self._app_service = service
        self.refresh_data()

    def refresh_data(self) -> None:
        """Refresh the operations list from the database."""
        if self._app_service is None:
            return

        self._all_operations = self._app_service.get_all_planned_operations()
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Apply current filter criteria and refresh the table."""
        self._filtered_operations = self._filter_operations(
            self._all_operations,
            self._search_text,
            self._filter_category,
            self._status_filter,
        )
        self._populate_table()
        self._update_status()

        filter_bar = self.query_one("#planned-ops-filter-bar", FilterBar)
        filter_bar.update_status(
            len(self._filtered_operations), len(self._all_operations)
        )

    @staticmethod
    def _filter_operations(
        operations: tuple[PlannedOperation, ...],
        search_text: str | None,
        category: Category | None,
        status_filter: StatusFilter = StatusFilter.ACTIVE,
    ) -> tuple[PlannedOperation, ...]:
        """Filter planned operations by search text, category, and status."""
        today = date.today()
        result: tuple[PlannedOperation, ...] = operations

        # Apply status filter
        if status_filter == StatusFilter.ACTIVE:
            result = tuple(op for op in result if not op.date_range.is_expired(today))
        elif status_filter == StatusFilter.EXPIRED:
            result = tuple(op for op in result if op.date_range.is_expired(today))
        # StatusFilter.ALL: no status filtering

        if search_text:
            text_lower = search_text.lower()
            result = tuple(op for op in result if text_lower in op.description.lower())
        if category is not None:
            result = tuple(op for op in result if op.category == category)
        return result

    def _populate_table(self) -> None:
        """Populate the data table with filtered planned operations."""
        table = self.query_one("#planned-ops-table", DataTable)
        table.clear()

        for op in self._filtered_operations:
            time_range = op.date_range
            start_date = time_range.start_date.strftime("%Y-%m-%d")

            # Determine periodicity and end date
            if isinstance(time_range, RecurringDay):
                period = self._format_period(time_range.period)
                end_date = (
                    time_range.last_date.strftime("%Y-%m-%d")
                    if time_range.last_date != date.max
                    else "-"
                )
            else:
                period = "-"
                end_date = "-"

            # Format description hints
            hints = (
                ", ".join(op.matcher.description_hints)
                if op.matcher.description_hints
                else "-"
            )
            if len(hints) > 30:
                hints = hints[:27] + "..."

            desc = op.description
            if len(desc) > 30:
                desc = desc[:27] + "..."

            table.add_row(
                f"{op.id:<4}",
                f"{desc:<30}",
                f"{op.amount:>10.2f} {op.currency}",
                f"{op.category.display_name:<20}",
                start_date,
                f"{period:<6}",
                f"{end_date:<10}",
                hints,
                key=str(op.id),
            )

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
        status = self.query_one("#planned-ops-status", Static)
        count = len(self._filtered_operations)
        status.update(_("{} planned operation(s)").format(count))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track the currently highlighted planned operation."""
        if event.row_key is None:
            self._selected_operation = None
        else:
            op_id = int(str(event.row_key.value))
            self._selected_operation = next(
                (op for op in self._filtered_operations if op.id == op_id), None
            )
        self.post_message(self.OperationSelected(self._selected_operation))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open edit modal on Enter/click."""
        if event.row_key is not None:
            op_id = int(str(event.row_key.value))
            operation = next(
                (op for op in self._filtered_operations if op.id == op_id), None
            )
            if operation:
                self.post_message(self.OperationEditRequested(operation))

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter changes from the filter bar."""
        event.stop()
        self._search_text = event.search_text
        self._filter_category = event.category
        self._status_filter = event.status_filter
        self._apply_filter()

    def on_filter_bar_filter_reset(self, event: FilterBar.FilterReset) -> None:
        """Handle filter reset from the filter bar."""
        event.stop()
        self._search_text = None
        self._filter_category = None
        self._status_filter = StatusFilter.ACTIVE
        self._apply_filter()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-add-op":
            self.post_message(self.OperationEditRequested(None))
