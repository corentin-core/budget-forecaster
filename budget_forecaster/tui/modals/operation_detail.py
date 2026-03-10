"""Modal for displaying full operation details."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.date_range import SingleDay
from budget_forecaster.core.types import LinkType
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.tui.messages import DataRefreshRequested, SaveRequested
from budget_forecaster.tui.modals.category import CategoryModal
from budget_forecaster.tui.modals.planned_operation_edit import (
    PlannedOperationEditModal,
)
from budget_forecaster.tui.symbols import DisplaySymbol


class OperationDetailModal(ModalScreen[bool]):
    """Modal showing full details of a historic operation.

    Displays date, full description, amount, category and link info.
    Provides actions to change category or create a planned operation.

    Returns True if data was modified, False otherwise.
    """

    DEFAULT_CSS = """
    OperationDetailModal {
        align: center middle;
    }

    OperationDetailModal #modal-container {
        width: 90;
        height: auto;
        max-height: 35;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    OperationDetailModal #modal-title {
        text-style: bold;
        margin-bottom: 1;
    }

    OperationDetailModal .detail-label {
        color: $text-muted;
        width: 16;
    }

    OperationDetailModal .detail-value {
        width: 1fr;
    }

    OperationDetailModal .detail-row {
        height: auto;
        margin-bottom: 1;
    }

    OperationDetailModal .amount-positive {
        color: $success;
    }

    OperationDetailModal .amount-negative {
        color: $error;
    }

    OperationDetailModal .link-none {
        color: $text-muted;
    }

    OperationDetailModal #buttons-row {
        height: 3;
        margin-top: 1;
        align: right middle;
    }

    OperationDetailModal #buttons-row Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        ("escape", "close", _("Close")),
        ("c", "change_category", _("Change category")),
        ("p", "plan_operation", _("Create planned operation")),
    ]

    def __init__(
        self, operation_id: int, app_service: ApplicationService, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self._operation_id = operation_id
        self._app_service = app_service
        self._modified = False

    def compose(self) -> ComposeResult:
        operation = self._app_service.get_operation_by_id(self._operation_id)

        with Vertical(id="modal-container"):
            yield Static(_("Operation detail"), id="modal-title")

            with Horizontal(classes="detail-row"):
                yield Static(_("Date:"), classes="detail-label")
                yield Static(
                    operation.operation_date.strftime("%d/%m/%Y"),
                    classes="detail-value",
                )

            with Horizontal(classes="detail-row"):
                yield Static(_("Description:"), classes="detail-label")
                yield Static(
                    operation.description,
                    classes="detail-value",
                    id="detail-description",
                )

            amount_str = f"{operation.amount:+.2f} {DisplaySymbol.EURO}"
            amount_class = (
                "amount-positive" if operation.amount > 0 else "amount-negative"
            )
            with Horizontal(classes="detail-row"):
                yield Static(_("Amount:"), classes="detail-label")
                yield Static(amount_str, classes=f"detail-value {amount_class}")

            with Horizontal(classes="detail-row"):
                yield Static(_("Category:"), classes="detail-label")
                yield Static(
                    operation.category.display_name,
                    classes="detail-value",
                    id="detail-category",
                )

            with Horizontal(classes="detail-row"):
                yield Static(_("Link:"), classes="detail-label")
                yield Static(
                    self._resolve_link_label(),
                    classes="detail-value",
                    id="detail-link",
                )

            with Horizontal(id="buttons-row"):
                yield Button(
                    _("Change category"), id="btn-change-category", variant="primary"
                )
                yield Button(
                    _("Create planned operation"),
                    id="btn-plan-operation",
                    variant="default",
                )
                yield Button(_("Close"), id="btn-close", variant="default")

    def on_mount(self) -> None:
        """Prevent auto-focus on buttons when the modal opens."""
        self.call_after_refresh(self.set_focus, None)

    def _resolve_link_label(self) -> str:
        """Resolve the link target name for display."""
        if (
            link := self._app_service.get_link_for_operation(self._operation_id)
        ) is None:
            return _("No link")

        if target_name := self._find_target_name(link.target_type, link.target_id):
            return f"🔗 {target_name}"
        return "🔗"

    def _find_target_name(self, target_type: LinkType, target_id: int) -> str:
        """Find the name of a link target."""
        if target_type == LinkType.PLANNED_OPERATION:
            for planned_op in self._app_service.get_all_planned_operations():
                if planned_op.id == target_id:
                    return planned_op.description
        elif target_type == LinkType.BUDGET:
            for budget in self._app_service.get_all_budgets():
                if budget.id == target_id:
                    return budget.description
        return ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-close":
            self.dismiss(self._modified)
        elif event.button.id == "btn-change-category":
            self._change_category()
        elif event.button.id == "btn-plan-operation":
            self._plan_operation()

    def _change_category(self) -> None:
        """Open category selection modal."""
        operation = self._app_service.get_operation_by_id(self._operation_id)
        suggested = self._app_service.suggest_category(operation)

        self.app.push_screen(
            CategoryModal(
                operations=(operation,),
                suggested_category=suggested,
            ),
            self._on_category_changed,
        )

    def _on_category_changed(self, result: Any) -> None:
        """Handle category change result."""
        if result is not None:
            self._app_service.categorize_operations((self._operation_id,), result)
            self.post_message(SaveRequested())
            self._modified = True

            # Refresh displayed category
            operation = self._app_service.get_operation_by_id(self._operation_id)
            self.query_one("#detail-category", Static).update(
                operation.category.display_name
            )

    def _plan_operation(self) -> None:
        """Open planned operation creation modal."""
        operation = self._app_service.get_operation_by_id(self._operation_id)

        prefilled = PlannedOperation(
            record_id=None,
            description=operation.description,
            amount=Amount(operation.amount, operation.currency),
            category=operation.category,
            date_range=SingleDay(operation.operation_date),
        )

        self.app.push_screen(
            PlannedOperationEditModal(prefilled),
            self._on_planned_operation_created,
        )

    def _on_planned_operation_created(self, result: Any) -> None:
        """Handle planned operation creation result."""
        if result is not None:
            self._modified = True
            self.post_message(DataRefreshRequested())

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(self._modified)

    def action_change_category(self) -> None:
        """Keyboard shortcut for changing category."""
        self._change_category()

    def action_plan_operation(self) -> None:
        """Keyboard shortcut for creating planned operation."""
        self._plan_operation()
