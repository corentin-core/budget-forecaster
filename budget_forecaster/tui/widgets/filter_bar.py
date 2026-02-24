"""Reusable filter bar widget for data tables."""

import enum
import logging
from datetime import date
from typing import Any, NamedTuple

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import Button, Input, Select, Static

from budget_forecaster.core.types import Category
from budget_forecaster.i18n import _

logger = logging.getLogger(__name__)


class DateRange(NamedTuple):
    """Date range filter values."""

    date_from: date | None = None
    date_to: date | None = None


class AmountRange(NamedTuple):
    """Amount range filter values."""

    min_amount: float | None = None
    max_amount: float | None = None


class StatusFilter(enum.StrEnum):
    """Status filter options for items that can be expired."""

    ACTIVE = "active"
    EXPIRED = "expired"
    ALL = "all"

    @property
    def display_name(self) -> str:
        """Return the localized display name."""
        return _(self.value.title())


class FilterBar(Vertical):
    """Reusable filter bar with search and category filter.

    Posts :class:`FilterChanged` when the user applies filters
    and :class:`FilterReset` when filters are cleared.

    Args:
        show_date_range: Show date from/to inputs.
        show_amount_range: Show min/max amount inputs.
        show_status_filter: Show status filter (Active/Expired/All).
    """

    DEFAULT_CSS = """
    FilterBar {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }

    FilterBar Horizontal {
        height: auto;
    }

    FilterBar Input {
        width: 20;
    }

    FilterBar #filter-search {
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

    FilterBar .range-label {
        width: auto;
        padding: 1 1 0 0;
        color: $text-muted;
    }

    FilterBar #filter-date-from,
    FilterBar #filter-date-to {
        width: 16;
    }

    FilterBar #filter-amount-min,
    FilterBar #filter-amount-max {
        width: 14;
    }
    """

    class FilterChanged(Message):
        """Posted when filter criteria are applied."""

        def __init__(
            self,
            search_text: str | None,
            category: Category | None,
            *,
            date_range: DateRange = DateRange(),
            amount_range: AmountRange = AmountRange(),
            status_filter: StatusFilter = StatusFilter.ACTIVE,
        ) -> None:
            super().__init__()
            self.search_text = search_text
            self.category = category
            self.date_from = date_range.date_from
            self.date_to = date_range.date_to
            self.min_amount = amount_range.min_amount
            self.max_amount = amount_range.max_amount
            self.status_filter = status_filter

    class FilterReset(Message):
        """Posted when all filters are cleared."""

    def __init__(
        self,
        *,
        show_date_range: bool = False,
        show_amount_range: bool = False,
        show_status_filter: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._show_date_range = show_date_range
        self._show_amount_range = show_amount_range
        self._show_status_filter = show_status_filter

    def compose(self) -> ComposeResult:
        """Create the filter bar layout."""
        with Horizontal(id="filter-row-main"):
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
            if self._show_status_filter:
                yield Select[str](
                    [(status.display_name, status.value) for status in StatusFilter],
                    value=StatusFilter.ACTIVE.value,
                    id="filter-status-select",
                    allow_blank=False,
                )
            yield Button(_("Filter"), id="filter-apply")
            yield Button(_("Reset"), id="filter-reset", variant="default")
            yield Static("", id="filter-status", classes="filter-status")

        if self._show_date_range or self._show_amount_range:
            with Horizontal(id="filter-row-range"):
                if self._show_date_range:
                    yield Static(_("From"), classes="range-label")
                    yield Input(
                        placeholder="YYYY-MM-DD",
                        id="filter-date-from",
                    )
                    yield Static(_("To"), classes="range-label")
                    yield Input(
                        placeholder="YYYY-MM-DD",
                        id="filter-date-to",
                    )
                if self._show_amount_range:
                    yield Static(_("Min"), classes="range-label")
                    yield Input(
                        placeholder=_("Amount"),
                        id="filter-amount-min",
                    )
                    yield Static(_("Max"), classes="range-label")
                    yield Input(
                        placeholder=_("Amount"),
                        id="filter-amount-max",
                    )

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

    @property
    def status_filter(self) -> StatusFilter:
        """Return the selected status filter, or ACTIVE if not shown."""
        try:
            select: Select[str] = self.query_one("#filter-status-select", Select)
            if select.value and select.value != Select.BLANK:
                return StatusFilter(str(select.value))
        except NoMatches:
            pass
        return StatusFilter.ACTIVE

    @property
    def date_from(self) -> date | None:
        """Return the 'from' date, or None if empty/invalid."""
        return self._parse_date_input("filter-date-from")

    @property
    def date_to(self) -> date | None:
        """Return the 'to' date, or None if empty/invalid."""
        return self._parse_date_input("filter-date-to")

    @property
    def min_amount(self) -> float | None:
        """Return the minimum amount, or None if empty/invalid."""
        return self._parse_float_input("filter-amount-min")

    @property
    def max_amount(self) -> float | None:
        """Return the maximum amount, or None if empty/invalid."""
        return self._parse_float_input("filter-amount-max")

    def _parse_date_input(self, input_id: str) -> date | None:
        """Parse a date from an input widget, returning None if missing or invalid."""
        try:
            value = self.query_one(f"#{input_id}", Input).value.strip()
        except NoMatches:
            return None
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            logger.debug("Invalid date value in %s: %r", input_id, value)
            return None

    def _parse_float_input(self, input_id: str) -> float | None:
        """Parse a float from an input widget, returning None if missing or invalid."""
        try:
            value = self.query_one(f"#{input_id}", Input).value.strip()
        except NoMatches:
            return None
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            logger.debug("Invalid amount value in %s: %r", input_id, value)
            return None

    def reset(self) -> None:
        """Clear all filter inputs and post FilterReset."""
        self.query_one("#filter-search", Input).value = ""
        self.query_one("#filter-category", Select).value = Select.BLANK
        try:
            self.query_one(
                "#filter-status-select", Select
            ).value = StatusFilter.ACTIVE.value
        except NoMatches:
            pass
        for input_id in (
            "filter-date-from",
            "filter-date-to",
            "filter-amount-min",
            "filter-amount-max",
        ):
            try:
                self.query_one(f"#{input_id}", Input).value = ""
            except NoMatches:
                pass
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
        """Handle Enter key in any filter input."""
        if event.input.id and event.input.id.startswith("filter-"):
            event.stop()
            self._apply()

    def _apply(self) -> None:
        """Read inputs and post FilterChanged."""
        self.post_message(
            self.FilterChanged(
                search_text=self.search_text,
                category=self.category,
                date_range=DateRange(self.date_from, self.date_to),
                amount_range=AmountRange(self.min_amount, self.max_amount),
                status_filter=self.status_filter,
            )
        )
