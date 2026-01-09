"""Widget for selecting a category."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from budget_forecaster.types import Category


class CategorySelect(Vertical):
    """A widget for selecting a category with search functionality."""

    DEFAULT_CSS = """
    CategorySelect {
        height: auto;
        max-height: 20;
        border: solid $primary;
        padding: 0 1;
    }

    CategorySelect > Input {
        margin-bottom: 1;
    }

    CategorySelect > OptionList {
        height: auto;
        max-height: 15;
    }

    CategorySelect > Static {
        height: 1;
        color: $text-muted;
    }
    """

    class CategorySelected(Message):
        """Message sent when a category is selected."""

        def __init__(self, category: Category) -> None:
            self.category = category
            super().__init__()

    def __init__(
        self,
        suggested: Category | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the category selector.

        Args:
            suggested: Optional suggested category to highlight.
            **kwargs: Additional arguments passed to Vertical.
        """
        super().__init__(**kwargs)
        self._suggested = suggested
        self._all_categories = sorted(Category, key=lambda c: c.value)
        self._filtered_categories = self._all_categories.copy()

    def compose(self) -> ComposeResult:
        """Create the widget layout."""
        hint = "Suggestion: " + self._suggested.value if self._suggested else ""
        yield Static(hint, id="suggestion-hint")
        yield Input(placeholder="Rechercher une catégorie...", id="category-search")
        yield OptionList(id="category-list")

    def on_mount(self) -> None:
        """Initialize the option list on mount."""
        self._update_options()
        # Focus the search input
        self.query_one("#category-search", Input).focus()

    def _update_options(self) -> None:
        """Update the option list with filtered categories."""
        option_list = self.query_one("#category-list", OptionList)
        option_list.clear_options()

        for cat in self._filtered_categories:
            # Mark suggested category
            label = cat.value
            if cat == self._suggested:
                label = f"★ {label} (suggestion)"
            option_list.add_option(Option(label, id=cat.name))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter categories based on search input."""
        if event.input.id != "category-search":
            return

        search = event.value.lower()
        if not search:
            self._filtered_categories = self._all_categories.copy()
        else:
            self._filtered_categories = [
                cat for cat in self._all_categories if search in cat.value.lower()
            ]

        self._update_options()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Select the first category when Enter is pressed in search."""
        if event.input.id != "category-search":
            return

        if self._filtered_categories:
            self._select_category(self._filtered_categories[0])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle category selection from the list."""
        if event.option.id:
            category = Category[event.option.id]
            self._select_category(category)

    def _select_category(self, category: Category) -> None:
        """Select a category and post the message."""
        self.post_message(self.CategorySelected(category))

    def set_suggested(self, category: Category | None) -> None:
        """Update the suggested category.

        Args:
            category: The category to suggest, or None.
        """
        self._suggested = category
        hint_widget = self.query_one("#suggestion-hint", Static)
        if category:
            hint_widget.update(f"Suggestion: {category.value}")
        else:
            hint_widget.update("")
        self._update_options()
