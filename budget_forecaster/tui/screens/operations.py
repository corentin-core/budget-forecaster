"""Operations screen for viewing and filtering operations."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

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
from budget_forecaster.tui.modals.operation_detail import OperationDetailModal
from budget_forecaster.tui.widgets.filter_bar import FilterBar
from budget_forecaster.tui.widgets.operation_table import OperationTable


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

    def on_operation_table_operation_selected(
        self, event: OperationTable.OperationSelected
    ) -> None:
        """Open operation detail modal when an operation is selected."""
        event.stop()
        if self._app_service:
            self.app.push_screen(
                OperationDetailModal(event.operation.unique_id, self._app_service),
                self._on_detail_modal_closed,
            )

    def _on_detail_modal_closed(self, modified: bool | None) -> None:
        """Refresh operations table if data was modified."""
        if modified:
            self._apply_filter()
