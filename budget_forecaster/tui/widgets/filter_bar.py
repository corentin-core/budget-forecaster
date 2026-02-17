"""Reusable filter bar widget for data tables."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Input, Select, Static

from budget_forecaster.core.types import Category
from budget_forecaster.i18n import _


class FilterBar(Horizontal):
    """Reusable filter bar with search and category filter.

    Posts :class:`FilterChanged` when the user applies filters
    and :class:`FilterReset` when filters are cleared.
    """

    DEFAULT_CSS = """
    FilterBar {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }

    FilterBar Input {
        width: 30;
    }

    FilterBar Select {
        width: 25;
    }

    FilterBar Button {
        margin-left: 1;
    }

    FilterBar .filter-status {
        margin-left: 1;
        content-align: center middle;
        color: $text-muted;
    }
    """

    class FilterChanged(Message):
        """Posted when filter criteria are applied."""

        def __init__(
            self,
            search_text: str | None,
            category: Category | None,
        ) -> None:
            super().__init__()
            self.search_text = search_text
            self.category = category

    class FilterReset(Message):
        """Posted when all filters are cleared."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Create the filter bar layout."""
        yield Input(placeholder=_("Search..."), id="filter-search")
        yield Select[str](
            [
                (cat.display_name, cat.name)
                for cat in sorted(Category, key=lambda c: c.display_name)
            ],
            prompt=_("Category"),
            id="filter-category",
            allow_blank=True,
        )
        yield Button(_("Filter"), id="filter-apply")
        yield Button(_("Reset"), id="filter-reset", variant="default")
        yield Static("", id="filter-status", classes="filter-status")

    @property
    def search_text(self) -> str | None:
        """Return the current search text, or None if empty."""
        value = self.query_one("#filter-search", Input).value.strip()
        return value or None

    @property
    def category(self) -> Category | None:
        """Return the selected category, or None if blank."""
        select: Select[str] = self.query_one("#filter-category", Select)
        if select.value and select.value != Select.BLANK:
            return Category[str(select.value)]
        return None

    def reset(self) -> None:
        """Clear all filter inputs and post FilterReset."""
        self.query_one("#filter-search", Input).value = ""
        self.query_one("#filter-category", Select).value = Select.BLANK
        self.update_status(0, 0)
        self.post_message(self.FilterReset())

    def update_status(self, filtered: int, total: int) -> None:
        """Update the status label showing filtered count.

        Args:
            filtered: Number of items after filtering.
            total: Total number of items before filtering.
        """
        status = self.query_one("#filter-status", Static)
        if total in (filtered, 0):
            status.update("")
        else:
            status.update(
                _("{filtered} / {total}").format(filtered=filtered, total=total)
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "filter-apply":
            event.stop()
            self._apply()
        elif event.button.id == "filter-reset":
            event.stop()
            self.reset()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in search input."""
        if event.input.id == "filter-search":
            event.stop()
            self._apply()

    def _apply(self) -> None:
        """Read inputs and post FilterChanged."""
        self.post_message(
            self.FilterChanged(
                search_text=self.search_text,
                category=self.category,
            )
        )
