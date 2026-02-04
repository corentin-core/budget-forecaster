"""Operations screen for viewing and filtering operations."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from budget_forecaster.core.types import (
    Category,
    LinkType,
    MatcherKey,
    OperationId,
    TargetName,
)
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_service import OperationFilter
from budget_forecaster.tui.messages import DataRefreshRequested, SaveRequested
from budget_forecaster.tui.widgets.category_select import CategorySelect
from budget_forecaster.tui.widgets.operation_table import OperationTable


class OperationDetailPanel(Vertical):
    """Panel showing details of the selected operation."""

    DEFAULT_CSS = """
    OperationDetailPanel {
        width: 40;
        height: 100%;
        border: solid $primary;
        padding: 1;
        dock: right;
    }

    OperationDetailPanel .detail-title {
        text-style: bold;
        margin-bottom: 1;
    }

    OperationDetailPanel .detail-label {
        color: $text-muted;
    }

    OperationDetailPanel .detail-value {
        margin-bottom: 1;
    }

    OperationDetailPanel #edit-category-container {
        height: auto;
        margin-top: 1;
    }

    OperationDetailPanel #edit-category-container.hidden {
        display: none;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._operation_id: int | None = None
        self._app_service: ApplicationService | None = None

    def compose(self) -> ComposeResult:
        yield Static("Détail de l'opération", classes="detail-title")
        yield Static("ID:", classes="detail-label")
        yield Static("-", id="detail-id", classes="detail-value")
        yield Static("Date:", classes="detail-label")
        yield Static("-", id="detail-date", classes="detail-value")
        yield Static("Description:", classes="detail-label")
        yield Static("-", id="detail-description", classes="detail-value")
        yield Static("Montant:", classes="detail-label")
        yield Static("-", id="detail-amount", classes="detail-value")
        yield Static("Catégorie:", classes="detail-label")
        yield Static("-", id="detail-category", classes="detail-value")

        with Vertical(id="edit-category-container", classes="hidden"):
            yield Button("Modifier la catégorie", id="btn-edit-category")

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service."""
        self._app_service = service

    def show_operation(self, operation_id: int) -> None:
        """Display details for an operation.

        Args:
            operation_id: The ID of the operation to display.
        """
        self._operation_id = operation_id

        if not self._app_service:
            return

        if not (operation := self._app_service.get_operation_by_id(operation_id)):
            self._clear()
            return

        self.query_one("#detail-id", Static).update(str(operation.unique_id))
        self.query_one("#detail-date", Static).update(
            operation.date.strftime("%d/%m/%Y %H:%M")
        )
        self.query_one("#detail-description", Static).update(operation.description)

        amount_str = f"{operation.amount:+.2f} €"
        self.query_one("#detail-amount", Static).update(amount_str)
        self.query_one("#detail-category", Static).update(operation.category.value)

        # Show edit button
        self.query_one("#edit-category-container").remove_class("hidden")

    def _clear(self) -> None:
        """Clear the detail panel."""
        self._operation_id = None
        for widget_id in (
            "detail-id",
            "detail-date",
            "detail-description",
            "detail-amount",
            "detail-category",
        ):
            self.query_one(f"#{widget_id}", Static).update("-")
        self.query_one("#edit-category-container").add_class("hidden")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-edit-category" and self._operation_id:
            # Push category selection modal
            self.app.push_screen(
                CategoryEditModal(self._operation_id, self._app_service),
                self._on_category_edited,
            )

    def _on_category_edited(self, result: bool | None) -> None:
        """Handle category edit result."""
        if result and self._operation_id:
            self.show_operation(self._operation_id)
            self.post_message(DataRefreshRequested())


class CategoryEditModal(ModalScreen[bool]):
    """Modal for editing an operation's category."""

    DEFAULT_CSS = """
    CategoryEditModal {
        align: center middle;
    }

    CategoryEditModal > Container {
        width: 60;
        height: auto;
        max-height: 30;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    CategoryEditModal .modal-title {
        text-style: bold;
        margin-bottom: 1;
    }

    CategoryEditModal #btn-cancel {
        margin-top: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "Annuler")]

    def __init__(
        self,
        operation_id: int,
        app_service: ApplicationService | None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._operation_id = operation_id
        self._app_service = app_service

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Modifier la catégorie", classes="modal-title")

            # Get suggested category
            suggested = None
            if self._app_service:
                if operation := self._app_service.get_operation_by_id(
                    self._operation_id
                ):
                    suggested = self._app_service.suggest_category(operation)

            yield CategorySelect(suggested=suggested)
            yield Button("Annuler", id="btn-cancel", variant="default")

    def on_category_select_category_selected(
        self, event: CategorySelect.CategorySelected
    ) -> None:
        """Handle category selection."""
        if self._app_service:
            self._app_service.categorize_operations(
                (self._operation_id,), event.category
            )
            self.post_message(SaveRequested())
        self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(False)

    def action_cancel(self) -> None:
        """Cancel the modal."""
        self.dismiss(False)


class OperationsScreen(Container):
    """Screen for viewing and filtering operations."""

    DEFAULT_CSS = """
    OperationsScreen {
        width: 100%;
        height: 100%;
    }

    #filter-bar {
        height: auto;
        dock: top;
        padding: 0 1;
    }

    #filter-bar Input {
        width: 30;
    }

    #filter-bar Select {
        width: 25;
    }

    #filter-bar Button {
        margin-left: 1;
    }

    #operations-table {
        width: 100%;
        height: 1fr;
    }

    #status-bar {
        height: 1;
        dock: bottom;
        background: $surface;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._app_service: ApplicationService | None = None
        self._current_filter = OperationFilter()

    def compose(self) -> ComposeResult:
        # Filter bar
        with Horizontal(id="filter-bar"):
            yield Input(placeholder="Rechercher...", id="search-input")
            yield Select[str](
                [
                    (cat.value, cat.name)
                    for cat in sorted(Category, key=lambda c: c.value)
                ],
                prompt="Catégorie",
                id="category-filter",
                allow_blank=True,
            )
            yield Button("Filtrer", id="btn-filter")
            yield Button("Réinitialiser", id="btn-reset")

        # Table only - simplified layout
        yield OperationTable(id="operations-table")

        yield Static("0 opérations", id="status-bar")

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service and refresh."""
        self._app_service = service
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Apply the current filter and refresh the table."""
        if not self._app_service:
            return

        operations = self._app_service.get_operations(self._current_filter)

        # Build links and targets lookup dicts
        links: dict[OperationId, OperationLink] = {}
        targets: dict[MatcherKey, TargetName] = {}

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

        table = self.query_one("#operations-table", OperationTable)
        table.load_operations(operations, links, targets)

        status = self.query_one("#status-bar", Static)
        status.update(f"{len(operations)} opération(s)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-filter":
            self._update_filter()
        elif event.button.id == "btn-reset":
            self._reset_filter()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in search input."""
        if event.input.id == "search-input":
            self._update_filter()

    def _update_filter(self) -> None:
        """Update the filter from UI inputs."""
        search_input = self.query_one("#search-input", Input)
        category_select = self.query_one("#category-filter", Select[str])

        search_text = search_input.value.strip() or None
        category = None
        if category_select.value and category_select.value != Select.BLANK:
            category = Category[str(category_select.value)]

        self._current_filter = OperationFilter(
            search_text=search_text,
            category=category,
        )
        self._apply_filter()

    def _reset_filter(self) -> None:
        """Reset all filters."""
        self.query_one("#search-input", Input).value = ""
        self.query_one("#category-filter", Select[str]).value = Select.BLANK
        self._current_filter = OperationFilter()
        self._apply_filter()

    def on_operation_table_operation_highlighted(
        self, event: OperationTable.OperationHighlighted
    ) -> None:
        """Show operation details when highlighted (not yet implemented)."""
        _ = event  # Unused for now
