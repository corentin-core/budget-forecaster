"""Category selection modal for categorizing operations."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from budget_forecaster.operation_range.historic_operation import HistoricOperation
from budget_forecaster.types import Category


class CategoryModal(ModalScreen[Category | None]):
    """Modal for selecting a category."""

    DEFAULT_CSS = """
    CategoryModal {
        align: center middle;
    }

    CategoryModal #modal-container {
        width: 80;
        height: 30;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    CategoryModal #op-info {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $accent;
    }

    CategoryModal #op-description {
        height: auto;
        max-height: 4;
    }

    CategoryModal #op-details {
        color: $text-muted;
    }

    CategoryModal .amount-positive {
        color: $success;
    }

    CategoryModal .amount-negative {
        color: $error;
    }

    CategoryModal OptionList {
        height: 1fr;
    }
    """

    BINDINGS = [("escape", "cancel", "Annuler")]

    def __init__(self, operation: HistoricOperation, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._operation = operation

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        op = self._operation
        amount_class = "amount-negative" if op.amount < 0 else "amount-positive"

        with Vertical(id="modal-container"):
            with Vertical(id="op-info"):
                yield Static(op.description, id="op-description")
                yield Static(
                    f"{op.date.strftime('%d/%m/%Y')} | {op.amount:+.2f} €",
                    id="op-details",
                    classes=amount_class,
                )
            categories = sorted(Category, key=lambda c: c.value)
            options = [Option(cat.value, id=cat.name) for cat in categories]
            yield OptionList(*options, id="category-list")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle category selection."""
        if event.option.id:
            self.dismiss(Category[event.option.id])

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)
