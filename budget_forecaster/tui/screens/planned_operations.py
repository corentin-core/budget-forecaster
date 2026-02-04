"""Planned operations management screen for budget forecaster."""

# pylint: disable=no-else-return

import logging
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Static

from budget_forecaster.core.time_range import PeriodicDailyTimeRange
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.services.application_service import ApplicationService

logger = logging.getLogger(__name__)


class PlannedOperationsWidget(Vertical):
    """Widget for managing planned operations."""

    DEFAULT_CSS = """
    PlannedOperationsWidget {
        height: 1fr;
    }

    PlannedOperationsWidget #planned-ops-header {
        height: 3;
        margin-bottom: 1;
    }

    PlannedOperationsWidget #planned-ops-title {
        width: 1fr;
        padding: 0 1;
    }

    PlannedOperationsWidget #planned-ops-buttons {
        width: auto;
    }

    PlannedOperationsWidget Button {
        margin-left: 1;
    }

    PlannedOperationsWidget #planned-ops-table {
        height: 1fr;
    }

    PlannedOperationsWidget #planned-ops-status {
        height: 1;
        padding: 0 1;
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
        self._operations: tuple[PlannedOperation, ...] = ()
        self._selected_operation: PlannedOperation | None = None

    def compose(self) -> ComposeResult:
        """Create the widget layout."""
        with Horizontal(id="planned-ops-header"):
            yield Static("Opérations planifiées", id="planned-ops-title")
            with Horizontal(id="planned-ops-buttons"):
                yield Button("Ajouter", id="btn-add-op", variant="primary")
                yield Button("Modifier", id="btn-edit-op", variant="default")
                yield Button("Scinder", id="btn-split-op", variant="default")
                yield Button("Supprimer", id="btn-delete-op", variant="error")

        yield DataTable(id="planned-ops-table")
        yield Static("", id="planned-ops-status")

    def on_mount(self) -> None:
        """Initialize the widget after mounting."""
        table = self.query_one("#planned-ops-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(
            "ID",
            "Description",
            "Montant",
            "Catégorie",
            "Date",
            "Périodicité",
            "Fin",
            "Mots-clés",
        )
        self._update_button_states()

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service and refresh data."""
        self._app_service = service
        self.refresh_data()

    def refresh_data(self) -> None:
        """Refresh the operations list from the database."""
        if self._app_service is None:
            return

        self._operations = self._app_service.get_all_planned_operations()
        self._populate_table()
        self._update_status()
        self._update_button_states()

    def _populate_table(self) -> None:
        """Populate the data table with planned operations."""
        table = self.query_one("#planned-ops-table", DataTable)
        table.clear()

        for op in self._operations:
            time_range = op.time_range
            start_date = time_range.initial_date.strftime("%Y-%m-%d")

            # Determine periodicity and end date
            if isinstance(time_range, PeriodicDailyTimeRange):
                period = self._format_period(time_range.period)
                end_date = (
                    time_range.last_date.strftime("%Y-%m-%d")
                    if time_range.last_date != datetime.max
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

            table.add_row(
                str(op.id),
                op.description,
                f"{op.amount:.2f} {op.currency}",
                op.category.value,
                start_date,
                period,
                end_date,
                hints,
                key=str(op.id),
            )

    def _format_period(self, period) -> str:
        """Format a relativedelta period."""
        if period.years:
            return f"{period.years} an(s)"
        elif period.months:
            return f"{period.months} mois"
        elif period.weeks:
            return f"{period.weeks} sem."
        elif period.days:
            return f"{period.days} j."
        return "-"

    def _update_status(self) -> None:
        """Update the status display."""
        status = self.query_one("#planned-ops-status", Static)
        count = len(self._operations)
        status.update(f"{count} opération(s) planifiée(s)")

    def _update_button_states(self) -> None:
        """Update button enabled states based on selection."""
        has_selection = self._selected_operation is not None
        self.query_one("#btn-edit-op", Button).disabled = not has_selection
        self.query_one("#btn-delete-op", Button).disabled = not has_selection

        # Split is only available for periodic operations
        can_split = (
            has_selection
            and self._selected_operation is not None
            and isinstance(self._selected_operation.time_range, PeriodicDailyTimeRange)
        )
        self.query_one("#btn-split-op", Button).disabled = not can_split

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table."""
        if event.row_key is None:
            self._selected_operation = None
        else:
            op_id = int(str(event.row_key.value))
            self._selected_operation = next(
                (op for op in self._operations if op.id == op_id), None
            )
        self._update_button_states()
        self.post_message(self.OperationSelected(self._selected_operation))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-add-op":
            self.post_message(self.OperationEditRequested(None))
        elif event.button.id == "btn-edit-op":
            if self._selected_operation:
                self.post_message(self.OperationEditRequested(self._selected_operation))
        elif event.button.id == "btn-split-op":
            if self._selected_operation and isinstance(
                self._selected_operation.time_range, PeriodicDailyTimeRange
            ):
                self.post_message(
                    self.OperationSplitRequested(self._selected_operation)
                )
        elif event.button.id == "btn-delete-op":
            if self._selected_operation:
                self.post_message(
                    self.OperationDeleteRequested(self._selected_operation)
                )
