"""Category detail modal — drill-down for a category in a given month."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from budget_forecaster.core.types import Category
from budget_forecaster.i18n import _
from budget_forecaster.services.forecast.forecast_service import (
    AttributedOperationDetail,
    CategoryDetail,
    PlannedSourceDetail,
)


def _translate_category(name: str) -> str:
    """Translate a category identifier to its display name."""
    try:
        return Category(name).display_name
    except ValueError:
        return name


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

    BINDINGS = [("escape", "close", _("Close"))]

    def __init__(self, detail: CategoryDetail, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._detail = detail

    def compose(self) -> ComposeResult:
        detail = self._detail
        month = detail["month"]
        month_label = f"{_(month.strftime('%B'))} {month.year}"
        title = f"{_translate_category(detail['category'])} \u2014 {month_label}"

        with Vertical(id="modal-container"):
            yield Static(title, id="modal-title")

            # Planned sources section
            if detail["planned_sources"]:
                yield Static(_("Planned sources"), classes="section-title")

                budgets = [s for s in detail["planned_sources"] if s["tag"] == "budget"]
                planned_ops = [
                    s for s in detail["planned_sources"] if s["tag"] == "planned"
                ]

                if budgets:
                    yield Static(_("Budgets"), classes="subsection-title")
                    yield Static("\u2500" * 74, classes="separator")
                    for source in budgets:
                        yield from self._compose_source_row(source)

                if planned_ops:
                    yield Static(_("Planned operations"), classes="subsection-title")
                    yield Static("\u2500" * 74, classes="separator")
                    for source in planned_ops:
                        yield from self._compose_source_row(source)

                yield Static("\u2500" * 74, classes="separator")
                yield from self._compose_total_row(
                    _("Total planned"), detail["total_planned"]
                )

            # Operations section
            yield Static(_("Operations"), classes="section-title")
            yield Static("\u2500" * 74, classes="separator")
            if detail["operations"]:
                for op in detail["operations"]:
                    yield from self._compose_operation_row(op)
            else:
                yield Static(_("No operations for this category"), classes="op-desc")
            yield Static("\u2500" * 74, classes="separator")
            yield from self._compose_total_row(
                _("Total actual"), detail["total_actual"]
            )

            # Footer summary
            remaining = detail["remaining"]
            sign = "+" if remaining > 0 else ""
            remaining_str = f"{sign}{remaining:,.0f}" if remaining != 0 else "0"

            summary = (
                f"{_('Planned')}: {abs(detail['total_planned']):,.0f} \u20ac / "
                f"{_('Actual')}: {abs(detail['total_actual']):,.0f} \u20ac / "
                f"{_('Forecast')}: {abs(detail['forecast']):,.0f} \u20ac / "
                f"{_('Remaining')}: {remaining_str} \u20ac"
            )
            yield Static(summary, id="footer-summary")

            with Horizontal(id="buttons-row"):
                yield Button(_("Close"), id="btn-close", variant="default")

    @staticmethod
    def _compose_source_row(source: PlannedSourceDetail) -> ComposeResult:
        """Compose a single planned source row."""
        amount_class = "amount-positive" if source["amount"] > 0 else "amount-negative"
        with Horizontal(classes="source-row"):
            yield Static(source["description"][:34], classes="source-desc")
            yield Static(source["periodicity"], classes="source-period")
            yield Static(
                f"{source['amount']:+.2f} \u20ac",
                classes=f"source-amount {amount_class}",
            )

    @staticmethod
    def _compose_operation_row(op: AttributedOperationDetail) -> ComposeResult:
        """Compose a single operation row with optional cross-month annotation."""
        date_str = op["operation_date"].strftime("%m/%d")
        amount_class = "amount-positive" if op["amount"] > 0 else "amount-negative"
        with Horizontal(classes="op-row"):
            yield Static(date_str, classes="op-date")
            yield Static(op["description"][:40], classes="op-desc")
            yield Static(
                f"{op['amount']:+.2f} \u20ac",
                classes=f"op-amount {amount_class}",
            )
        if op["cross_month_annotation"]:
            yield Static(f"\u2190 {op['cross_month_annotation']}", classes="annotation")

    @staticmethod
    def _compose_total_row(label: str, amount: float) -> ComposeResult:
        """Compose a total row."""
        with Horizontal(classes="total-row"):
            yield Static(label, classes="total-label")
            yield Static(f"{amount:+.2f} \u20ac", classes="total-amount")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "btn-close":
            self.dismiss(None)

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(None)
