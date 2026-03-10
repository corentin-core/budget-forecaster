"""Category detail modal — drill-down for a category in a given month."""

import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Static

from budget_forecaster.domain.operation.budget import Budget
from budget_forecaster.domain.operation.planned_operation import PlannedOperation
from budget_forecaster.i18n import _
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.services.forecast.forecast_service import (
    AttributedOperationDetail,
    CategoryDetail,
    ForecastSourceType,
    PlannedSourceDetail,
)
from budget_forecaster.tui.modals.budget_edit import BudgetEditModal
from budget_forecaster.tui.modals.operation_detail import OperationDetailModal
from budget_forecaster.tui.modals.planned_operation_edit import (
    PlannedOperationEditModal,
)
from budget_forecaster.tui.symbols import DisplaySymbol

logger = logging.getLogger(__name__)


class _SourceRow(Horizontal):
    """A focusable row for a planned source in the category detail modal."""

    can_focus = True


class _OperationRow(Horizontal):
    """A focusable row for an operation in the category detail modal."""

    can_focus = True


class CategoryDetailModal(ModalScreen[None]):
    """Modal showing planned sources and attributed operations for a category."""

    DEFAULT_CSS = """
    CategoryDetailModal {
        align: center middle;
    }

    CategoryDetailModal #modal-container {
        width: 80;
        height: auto;
        max-height: 40;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }

    CategoryDetailModal #modal-title {
        text-style: bold;
        height: 2;
        margin-bottom: 1;
    }

    CategoryDetailModal .section-title {
        text-style: bold;
        color: $text-muted;
        margin-top: 1;
    }

    CategoryDetailModal .separator {
        color: $text-muted;
    }

    CategoryDetailModal .subsection-title {
        color: $accent;
        margin-top: 1;
    }

    CategoryDetailModal .source-row {
        height: 1;
    }

    CategoryDetailModal .source-row:hover {
        background: $boost;
    }

    CategoryDetailModal .source-row:focus {
        background: $boost;
    }

    CategoryDetailModal .source-desc {
        width: 36;
    }

    CategoryDetailModal .source-period {
        width: 22;
        color: $text-muted;
    }

    CategoryDetailModal .source-amount {
        width: 16;
        text-align: right;
    }

    CategoryDetailModal .op-row {
        height: 1;
    }

    CategoryDetailModal .op-row:hover {
        background: $boost;
    }

    CategoryDetailModal .op-row:focus {
        background: $boost;
    }

    CategoryDetailModal .op-date {
        width: 8;
        color: $text-muted;
    }

    CategoryDetailModal .op-desc {
        width: 42;
    }

    CategoryDetailModal .op-amount {
        width: 16;
        text-align: right;
    }

    CategoryDetailModal .annotation {
        height: 1;
        color: $warning;
        padding-left: 9;
    }

    CategoryDetailModal .link-annotation {
        height: 1;
        color: $accent;
        padding-left: 9;
    }

    CategoryDetailModal .total-row {
        height: 1;
        text-style: bold;
    }

    CategoryDetailModal .total-label {
        width: 58;
    }

    CategoryDetailModal .total-amount {
        width: 16;
        text-align: right;
        text-style: bold;
    }

    CategoryDetailModal #footer-summary {
        margin-top: 1;
        height: 1;
    }

    CategoryDetailModal #buttons-row {
        height: 3;
        margin-top: 1;
        align: right middle;
    }

    CategoryDetailModal .amount-positive {
        color: $success;
    }

    CategoryDetailModal .amount-negative {
        color: $error;
    }
    """

    BINDINGS = [
        ("escape", "close", _("Close")),
        ("enter", "activate_row", _("Detail / Edit")),
    ]

    def __init__(
        self,
        detail: CategoryDetail,
        app_service: ApplicationService | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._detail = detail
        self._app_service = app_service

    def compose(self) -> ComposeResult:
        detail = self._detail
        month = detail["month"]
        month_label = f"{_(month.strftime('%B'))} {month.year}"
        category_name = detail["category"].display_name
        title = f"{category_name} {DisplaySymbol.EM_DASH} {month_label}"
        separator = DisplaySymbol.SEPARATOR * 74

        with Vertical(id="modal-container"):
            yield Static(title, id="modal-title")

            # Planned sources section
            if detail["planned_sources"]:
                yield Static(_("Planned sources"), classes="section-title")

                budgets = [
                    s
                    for s in detail["planned_sources"]
                    if s["forecast_source_type"] == ForecastSourceType.BUDGET
                ]
                planned_ops = [
                    s
                    for s in detail["planned_sources"]
                    if s["forecast_source_type"] == ForecastSourceType.PLANNED_OPERATION
                ]

                if budgets:
                    yield Static(_("Budgets"), classes="subsection-title")
                    yield Static(separator, classes="separator")
                    for source in budgets:
                        yield from self._compose_source_row(source)

                if planned_ops:
                    yield Static(_("Planned operations"), classes="subsection-title")
                    yield Static(separator, classes="separator")
                    for source in planned_ops:
                        yield from self._compose_source_row(source)

                yield Static(separator, classes="separator")
                yield from self._compose_total_row(
                    _("Total planned"), detail["total_planned"]
                )

            # Operations section
            yield Static(_("Operations"), classes="section-title")
            yield Static(separator, classes="separator")
            if detail["operations"]:
                for op in detail["operations"]:
                    yield from self._compose_operation_row(op)
            else:
                yield Static(_("No operations for this category"), classes="op-desc")
            yield Static(separator, classes="separator")
            yield from self._compose_total_row(
                _("Total actual"), detail["total_actual"]
            )

            # Footer summary
            yield Static(self._build_footer_summary(detail), id="footer-summary")

            with Horizontal(id="buttons-row"):
                yield Button(_("Close"), id="btn-close", variant="default")

    @staticmethod
    def _compose_source_row(source: PlannedSourceDetail) -> ComposeResult:
        """Compose a single planned source row."""
        amount_class = "amount-positive" if source["amount"] > 0 else "amount-negative"
        source_type = source["forecast_source_type"].name
        source_id = source["source_id"]
        row_name = f"{source_type}:{source_id}" if source_id is not None else None
        row = _SourceRow(classes="source-row", name=row_name)
        with row:
            yield Static(source["description"][:34], classes="source-desc")
            yield Static(source["periodicity"], classes="source-period")
            yield Static(
                f"{source['amount']:+.2f} {DisplaySymbol.EURO}",
                classes=f"source-amount {amount_class}",
            )

    @staticmethod
    def _compose_operation_row(op: AttributedOperationDetail) -> ComposeResult:
        """Compose a single operation row with optional annotations."""
        date_str = op["operation_date"].strftime("%m/%d")
        amount_class = "amount-positive" if op["amount"] > 0 else "amount-negative"
        row = _OperationRow(classes="op-row", name=str(op["operation_id"]))
        with row:
            yield Static(date_str, classes="op-date")
            yield Static(op["description"][:40], classes="op-desc")
            yield Static(
                f"{op['amount']:+.2f} {DisplaySymbol.EURO}",
                classes=f"op-amount {amount_class}",
            )
        if op["cross_month_annotation"]:
            yield Static(
                f"{DisplaySymbol.ARROW_LEFT} {op['cross_month_annotation']}",
                classes="annotation",
            )
        if op["link_target_name"]:
            link_label = _("budget") if op["link_type"] == "budget" else _("planned")
            yield Static(
                f"{DisplaySymbol.ARROW_RIGHT} {_('linked to')} {link_label}: "
                f"{op['link_target_name']}",
                classes="link-annotation",
            )

    @staticmethod
    def _compose_total_row(label: str, amount: float) -> ComposeResult:
        """Compose a total row."""
        with Horizontal(classes="total-row"):
            yield Static(label, classes="total-label")
            yield Static(f"{amount:+.2f} {DisplaySymbol.EURO}", classes="total-amount")

    @staticmethod
    def _build_footer_summary(detail: CategoryDetail) -> str:
        """Build the footer summary line."""
        remaining = detail["remaining"]
        sign = "+" if remaining > 0 else ""
        remaining_str = f"{sign}{remaining:,.0f}" if remaining != 0 else "0"
        euro = DisplaySymbol.EURO
        return (
            f"{_('Planned')}: {abs(detail['total_planned']):,.0f} {euro} / "
            f"{_('Actual')}: {abs(detail['total_actual']):,.0f} {euro} / "
            f"{_('Forecast')}: {abs(detail['forecast']):,.0f} {euro} / "
            f"{_('Remaining')}: {remaining_str} {euro}"
        )

    def _open_operation_detail(self, operation_id: int) -> None:
        """Open operation detail modal for the given operation."""
        if self._app_service:
            self.app.push_screen(
                OperationDetailModal(operation_id, self._app_service),
            )

    def _open_source_edit(self, source_type: str, source_id: int) -> None:
        """Open the edit modal for a planned source."""
        if not self._app_service:
            return

        try:
            if source_type == ForecastSourceType.BUDGET.name:
                if budget := self._app_service.get_budget_by_id(source_id):
                    self.app.push_screen(
                        BudgetEditModal(budget),
                        self._on_budget_edited,
                    )
            elif source_type == ForecastSourceType.PLANNED_OPERATION.name:
                if operation := self._app_service.get_planned_operation_by_id(
                    source_id
                ):
                    self.app.push_screen(
                        PlannedOperationEditModal(operation),
                        self._on_planned_operation_edited,
                    )
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error opening source edit modal")
            self.app.notify(_("Error opening edit modal"), severity="error")

    def _on_budget_edited(self, budget: Budget | None) -> None:
        """Handle budget edit completion."""
        if budget is None or not self._app_service:
            return
        try:
            self._app_service.update_budget(budget)
            self.app.notify(_("Budget '{}' modified").format(budget.description))
            self._refresh_detail()
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error saving budget")
            self.app.notify(_("Error saving budget"), severity="error")

    def _on_planned_operation_edited(self, operation: PlannedOperation | None) -> None:
        """Handle planned operation edit completion."""
        if operation is None or not self._app_service:
            return
        try:
            self._app_service.update_planned_operation(operation)
            self.app.notify(_("Operation '{}' modified").format(operation.description))
            self._refresh_detail()
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error saving planned operation")
            self.app.notify(_("Error saving planned operation"), severity="error")

    def _refresh_detail(self) -> None:
        """Re-fetch category detail and recompose the modal."""
        if not self._app_service:
            return
        try:
            detail = self._detail
            self._detail = self._app_service.get_category_detail(
                detail["category"].value, detail["month"]
            )
            self.call_later(self.recompose)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error refreshing category detail")

    def action_activate_row(self) -> None:
        """Activate the focused row: edit for source rows, detail for op rows."""
        focused = self.focused
        if focused is None or focused.name is None:
            return

        if "source-row" in focused.classes:
            self._activate_source_row(focused.name)
        elif "op-row" in focused.classes:
            self._open_operation_detail(int(focused.name))

    def _activate_source_row(self, row_name: str) -> None:
        """Parse source row name and open the edit modal."""
        parts = row_name.split(":", 1)
        if len(parts) != 2:
            return
        source_type, source_id_str = parts
        try:
            source_id = int(source_id_str)
        except ValueError:
            return
        self._open_source_edit(source_type, source_id)

    def on_click(self, event: Click) -> None:
        """Handle click on a row."""
        widget: Widget | None = event.widget
        while widget is not None and widget is not self:
            if widget.name is not None:
                if "source-row" in widget.classes:
                    self._activate_source_row(widget.name)
                    return
                if "op-row" in widget.classes:
                    self._open_operation_detail(int(widget.name))
                    return
            widget = widget.parent if isinstance(widget.parent, Widget) else None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-close":
            self.dismiss(None)

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(None)
