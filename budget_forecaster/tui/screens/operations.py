"""Operations screen for viewing and filtering operations."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from budget_forecaster.core.types import (
    LinkType,
    MatcherKey,
    OperationId,
    TargetName,
)
from budget_forecaster.domain.operation.operation_link import OperationLink
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.operation.operation_service import OperationFilter
from budget_forecaster.tui.messages import DataRefreshRequested, SaveRequested
from budget_forecaster.tui.widgets.category_select import CategorySelect
from budget_forecaster.tui.widgets.filter_bar import FilterBar
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
        yield Static(_("Operation detail"), classes="detail-title")
        yield Static(_("ID:"), classes="detail-label")
        yield Static("-", id="detail-id", classes="detail-value")
        yield Static(_("Date:"), classes="detail-label")
        yield Static("-", id="detail-date", classes="detail-value")
        yield Static(_("Description:"), classes="detail-label")
        yield Static("-", id="detail-description", classes="detail-value")
        yield Static(_("Amount:"), classes="detail-label")
        yield Static("-", id="detail-amount", classes="detail-value")
        yield Static(_("Category:"), classes="detail-label")
        yield Static("-", id="detail-category", classes="detail-value")

        with Vertical(id="edit-category-container", classes="hidden"):
            yield Button(_("Change category"), id="btn-edit-category")

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

        operation = self._app_service.get_operation_by_id(operation_id)

        self.query_one("#detail-id", Static).update(str(operation.unique_id))
        self.query_one("#detail-date", Static).update(
            operation.operation_date.strftime("%d/%m/%Y %H:%M")
        )
        self.query_one("#detail-description", Static).update(operation.description)

        amount_str = f"{operation.amount:+.2f} €"
        self.query_one("#detail-amount", Static).update(amount_str)
        self.query_one("#detail-category", Static).update(
            operation.category.display_name
        )

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

    BINDINGS = [("escape", "cancel", _("Cancel"))]

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
            yield Static(_("Change category"), classes="modal-title")

            # Get suggested category
            suggested = None
            if self._app_service:
                operation = self._app_service.get_operation_by_id(self._operation_id)
                suggested = self._app_service.suggest_category(operation)

            yield CategorySelect(suggested=suggested)
            yield Button(_("Cancel"), id="btn-cancel", variant="default")

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


class OperationsScreen(Vertical):
    """Screen for viewing and filtering operations."""

    DEFAULT_CSS = """
    OperationsScreen {
        height: 1fr;
    }

    OperationsScreen #operations-table {
        height: 1fr;
    }

    OperationsScreen #status-bar {
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
        self._total_count: int = 0

    def compose(self) -> ComposeResult:
        yield FilterBar(
            show_date_range=True,
            show_amount_range=True,
            id="operations-filter-bar",
        )
        yield OperationTable(id="operations-table")
        yield Static(_("0 operations"), id="status-bar")

    def set_app_service(self, service: ApplicationService) -> None:
        """Set the application service and refresh."""
        self._app_service = service
        self._apply_filter()

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

    def _apply_filter(self) -> None:
        """Apply the current filter and refresh the table."""
        if not self._app_service:
            return

        all_operations = self._app_service.get_operations()
        self._total_count = len(all_operations)

        filtered_operations = self._app_service.get_operations(self._current_filter)
        filtered_count = len(filtered_operations)

        links, targets = self._build_lookups()

        table = self.query_one("#operations-table", OperationTable)
        table.load_operations(filtered_operations, links, targets)

        status = self.query_one("#status-bar", Static)
        status.update(_("{} operation(s)").format(filtered_count))

        filter_bar = self.query_one("#operations-filter-bar", FilterBar)
        filter_bar.update_status(filtered_count, self._total_count)

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Handle filter changes from the filter bar."""
        event.stop()
        self._current_filter = OperationFilter(
            search_text=event.search_text,
            category=event.category,
            date_from=event.date_from,
            date_to=event.date_to,
            min_amount=event.min_amount,
            max_amount=event.max_amount,
        )
        self._apply_filter()

    def on_filter_bar_filter_reset(self, event: FilterBar.FilterReset) -> None:
        """Handle filter reset from the filter bar."""
        event.stop()
        self._current_filter = OperationFilter()
        self._apply_filter()

    def on_operation_table_operation_highlighted(
        self, event: OperationTable.OperationHighlighted
    ) -> None:
        """Show operation details when highlighted (not yet implemented)."""
        _ = event
