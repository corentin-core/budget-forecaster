"""Category selection modal for categorizing operations."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation


class CategoryModal(ModalScreen[Category | None]):
    """Modal for selecting a category."""

    DEFAULT_CSS = """
    CategoryModal {
        align: center middle;
    }

    CategoryModal #modal-container {
        width: 80;
        height: auto;
        max-height: 45;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    CategoryModal #ops-panel {
        height: auto;
        max-height: 12;
        margin-bottom: 1;
        padding: 1;
        border: solid $accent;
    }

    CategoryModal .panel-title {
        text-style: bold;
        margin-bottom: 1;
    }

    CategoryModal .op-row {
        height: 1;
    }

    CategoryModal .op-date {
        width: 12;
        color: $text-muted;
    }

    CategoryModal .op-desc {
        width: 45;
    }

    CategoryModal .op-amount {
        width: 12;
        text-align: right;
    }

    CategoryModal .amount-positive {
        color: $success;
    }

    CategoryModal .amount-negative {
        color: $error;
    }

    CategoryModal #similar-panel {
        height: auto;
        max-height: 8;
        margin-bottom: 1;
        padding: 1;
        border: solid $secondary;
    }

    CategoryModal .similar-row {
        height: 1;
    }

    CategoryModal .similar-desc {
        width: 50;
    }

    CategoryModal .similar-cat {
        color: $text-muted;
    }

    CategoryModal #suggestion-hint {
        height: 1;
        color: $warning;
        margin-bottom: 1;
    }

    CategoryModal OptionList {
        height: 1fr;
        min-height: 10;
    }
    """

    BINDINGS = [("escape", "cancel", "Annuler")]

    def __init__(
        self,
        operations: tuple[HistoricOperation, ...],
        similar_operations: tuple[HistoricOperation, ...] = (),
        suggested_category: Category | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._operations = operations
        self._similar_operations = similar_operations
        self._suggested_category = suggested_category

    def compose(self) -> ComposeResult:
        """Create the modal layout."""
        with Vertical(id="modal-container"):
            # Selected operations panel
            with Vertical(id="ops-panel"):
                count = len(self._operations)
                title = (
                    "Opération à catégoriser"
                    if count == 1
                    else f"{count} opérations à catégoriser"
                )
                yield Static(title, classes="panel-title")

                for op in self._operations[:8]:
                    amount_class = (
                        "amount-negative" if op.amount < 0 else "amount-positive"
                    )
                    with Horizontal(classes="op-row"):
                        yield Static(
                            op.date.strftime("%d/%m/%Y"),
                            classes="op-date",
                        )
                        yield Static(
                            self._truncate(op.description, 43),
                            classes="op-desc",
                        )
                        yield Static(
                            f"{op.amount:+.2f} €",
                            classes=f"op-amount {amount_class}",
                        )

                if count > 8:
                    yield Static(
                        f"... et {count - 8} autre(s)",
                        classes="op-date",
                    )

            # Similar operations panel (based on first operation)
            if self._similar_operations:
                with Vertical(id="similar-panel"):
                    yield Static("Opérations similaires", classes="panel-title")
                    for similar_op in self._similar_operations[:5]:
                        with Horizontal(classes="similar-row"):
                            yield Static(
                                self._truncate(similar_op.description, 48),
                                classes="similar-desc",
                            )
                            yield Static(
                                f"→ {similar_op.category.value}",
                                classes="similar-cat",
                            )

            # Suggestion hint
            if self._suggested_category:
                yield Static(
                    f"Suggestion: {self._suggested_category.value}",
                    id="suggestion-hint",
                )

            # Category list
            categories = sorted(Category, key=lambda c: c.value)
            options = []
            for cat in categories:
                label = cat.value
                if cat == self._suggested_category:
                    label = f"★ {label} (suggestion)"
                options.append(Option(label, id=cat.name))
            yield OptionList(*options, id="category-list")

    def on_mount(self) -> None:
        """Pre-select the suggested category when mounted."""
        if self._suggested_category is None:
            return

        categories = sorted(Category, key=lambda c: c.value)
        try:
            index = categories.index(self._suggested_category)
            option_list = self.query_one("#category-list", OptionList)
            option_list.highlighted = index
        except (ValueError, IndexError):
            pass

    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length with ellipsis."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle category selection."""
        if event.option.id:
            self.dismiss(Category[event.option.id])

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)
