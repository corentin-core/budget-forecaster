"""Categorization screen for uncategorized operations."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Static

from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.services import OperationService
from budget_forecaster.tui.widgets.category_select import CategorySelect
from budget_forecaster.tui.widgets.operation_table import OperationTable
from budget_forecaster.types import Category


class SimilarOperationsPanel(Vertical):
    """Panel showing similar operations for context."""

    DEFAULT_CSS = """
    SimilarOperationsPanel {
        width: 100%;
        height: 10;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    SimilarOperationsPanel .panel-title {
        text-style: bold;
        margin-bottom: 1;
    }

    SimilarOperationsPanel .similar-row {
        height: 1;
    }

    SimilarOperationsPanel .similar-desc {
        width: 40;
    }

    SimilarOperationsPanel .similar-cat {
        width: 20;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Opérations similaires", classes="panel-title")
        yield Vertical(id="similar-list")

    def show_similar(self, operations: list[HistoricOperation]) -> None:
        """Display similar operations.

        Args:
            operations: List of similar operations.
        """
        similar_list = self.query_one("#similar-list", Vertical)
        similar_list.remove_children()

        if not operations:
            similar_list.mount(Static("Aucune opération similaire"))
            return

        for op in operations[:5]:
            row = Horizontal(classes="similar-row")
            row.compose_add_child(
                Static(self._truncate(op.description, 38), classes="similar-desc")
            )
            row.compose_add_child(
                Static(f"→ {op.category.value}", classes="similar-cat")
            )
            similar_list.mount(row)

    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."


class CurrentOperationPanel(Container):
    """Panel showing the current operation to categorize."""

    DEFAULT_CSS = """
    CurrentOperationPanel {
        width: 100%;
        height: auto;
        border: solid $accent;
        padding: 1;
        margin-bottom: 1;
    }

    CurrentOperationPanel .op-title {
        text-style: bold;
        margin-bottom: 1;
    }

    CurrentOperationPanel .op-description {
        margin-bottom: 1;
    }

    CurrentOperationPanel .op-details {
        color: $text-muted;
    }

    CurrentOperationPanel .amount-negative {
        color: $error;
        text-style: bold;
    }

    CurrentOperationPanel .amount-positive {
        color: $success;
        text-style: bold;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Opération à catégoriser", classes="op-title")
        yield Static("-", id="op-description", classes="op-description")
        yield Static("-", id="op-details", classes="op-details")
        yield Static("-", id="op-amount")

    def show_operation(self, operation: HistoricOperation | None) -> None:
        """Display an operation.

        Args:
            operation: The operation to display, or None to clear.
        """
        if operation is None:
            self.query_one("#op-description", Static).update(
                "Aucune opération à catégoriser"
            )
            self.query_one("#op-details", Static).update("")
            self.query_one("#op-amount", Static).update("")
            return

        self.query_one("#op-description", Static).update(operation.description)
        self.query_one("#op-details", Static).update(
            f"ID: {operation.unique_id} | Date: {operation.date.strftime('%d/%m/%Y')}"
        )

        amount_widget = self.query_one("#op-amount", Static)
        amount_widget.update(f"{operation.amount:+.2f} €")
        amount_widget.remove_class("amount-negative", "amount-positive")
        if operation.amount < 0:
            amount_widget.add_class("amount-negative")
        else:
            amount_widget.add_class("amount-positive")


class CategorizeScreen(Container):
    """Screen for categorizing uncategorized operations."""

    DEFAULT_CSS = """
    CategorizeScreen {
        width: 100%;
        height: 100%;
    }

    #progress-bar {
        height: 1;
        dock: top;
        background: $surface;
        padding: 0 1;
    }

    #main-content {
        height: 1fr;
        padding: 1;
    }

    #left-panel {
        width: 2fr;
    }

    #right-panel {
        width: 1fr;
        margin-left: 1;
    }

    #pending-table {
        height: 1fr;
        border: solid $primary;
    }

    #action-buttons {
        height: 3;
        margin-top: 1;
    }

    #action-buttons Button {
        margin-right: 1;
    }

    .empty-message {
        text-align: center;
        color: $text-muted;
        margin-top: 5;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._service: OperationService | None = None
        self._current_operation: HistoricOperation | None = None
        self._pending_operations: list[HistoricOperation] = []

    def compose(self) -> ComposeResult:
        yield Static("0/0 opérations catégorisées", id="progress-bar")

        with Horizontal(id="main-content"):
            with Vertical(id="left-panel"):
                yield CurrentOperationPanel(id="current-op-panel")
                yield SimilarOperationsPanel(id="similar-panel")
                yield CategorySelect(id="category-selector")

                with Horizontal(id="action-buttons"):
                    yield Button("Passer", id="btn-skip", variant="default")
                    yield Button(
                        "Tout comme celui-ci", id="btn-bulk", variant="primary"
                    )

            with Vertical(id="right-panel"):
                yield Static("Opérations restantes", classes="op-title")
                yield OperationTable(id="pending-table")

    def refresh_data(self, service: OperationService) -> None:
        """Refresh with current data.

        Args:
            service: The operation service to get data from.
        """
        self._service = service
        self._pending_operations = service.get_uncategorized_operations()
        self._update_pending_table()
        self._show_next_operation()

    def _update_pending_table(self) -> None:
        """Update the pending operations table."""
        table = self.query_one("#pending-table", OperationTable)
        table.load_operations(self._pending_operations)

    def _show_next_operation(self) -> None:
        """Show the next uncategorized operation."""
        if not self._service:
            return

        total = len(self._service.operations)
        pending = len(self._pending_operations)
        categorized = total - pending

        progress = self.query_one("#progress-bar", Static)
        progress.update(
            f"{categorized}/{total} opérations catégorisées ({pending} restantes)"
        )

        if not self._pending_operations:
            self._current_operation = None
            self._show_empty_state()
            return

        self._current_operation = self._pending_operations[0]

        # Update current operation panel
        current_panel = self.query_one("#current-op-panel", CurrentOperationPanel)
        current_panel.show_operation(self._current_operation)

        # Update similar operations
        similar = self._service.find_similar_operations(self._current_operation)
        similar_panel = self.query_one("#similar-panel", SimilarOperationsPanel)
        similar_panel.show_similar(similar)

        # Update category selector with suggestion
        suggested = self._service.suggest_category(self._current_operation)
        category_select = self.query_one("#category-selector", CategorySelect)
        category_select.set_suggested(suggested)

    def _show_empty_state(self) -> None:
        """Show empty state when all operations are categorized."""
        current_panel = self.query_one("#current-op-panel", CurrentOperationPanel)
        current_panel.show_operation(None)

        similar_panel = self.query_one("#similar-panel", SimilarOperationsPanel)
        similar_panel.show_similar([])

    def on_category_select_category_selected(
        self, event: CategorySelect.CategorySelected
    ) -> None:
        """Handle category selection."""
        if not self._service or not self._current_operation:
            return

        self._service.categorize_operation(
            self._current_operation.unique_id, event.category
        )
        self._save_and_refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-skip":
            self._skip_operation()
        elif event.button.id == "btn-bulk":
            self._bulk_categorize()

    def _skip_operation(self) -> None:
        """Skip the current operation."""
        if self._pending_operations:
            # Move current to end of list
            skipped = self._pending_operations.pop(0)
            self._pending_operations.append(skipped)
            self._update_pending_table()
            self._show_next_operation()

    def _bulk_categorize(self) -> None:
        """Categorize all similar operations with the same category."""
        if not self._service or not self._current_operation:
            return

        # Get suggested category
        if not (suggested := self._service.suggest_category(self._current_operation)):
            self.app.notify("Pas de suggestion disponible", severity="warning")
            return

        # Find similar uncategorized operations
        similar = self._service.find_similar_operations(
            self._current_operation, limit=20
        )
        similar_ids = [op.unique_id for op in similar if op.category == Category.OTHER]

        # Include current operation
        all_ids = [self._current_operation.unique_id, *similar_ids]

        # Bulk categorize
        updated = self._service.bulk_categorize(all_ids, suggested)
        self.app.notify(f"{len(updated)} opération(s) catégorisée(s)")
        self._save_and_refresh()

    def _save_and_refresh(self) -> None:
        """Save changes and refresh the view."""
        # pylint: disable=import-outside-toplevel
        from budget_forecaster.tui.app import BudgetApp

        app = self.app
        if isinstance(app, BudgetApp):
            app.save_changes()

        if self._service:
            self._pending_operations = self._service.get_uncategorized_operations()
            self._update_pending_table()
            self._show_next_operation()

    def on_operation_table_operation_selected(
        self, event: OperationTable.OperationSelected
    ) -> None:
        """Handle selection in pending table - jump to that operation."""
        if event.operation in self._pending_operations:
            # Move selected operation to front
            self._pending_operations.remove(event.operation)
            self._pending_operations.insert(0, event.operation)
            self._show_next_operation()
