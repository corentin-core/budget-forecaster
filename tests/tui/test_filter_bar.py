"""Tests for FilterBar widget."""

from datetime import date

from textual.app import App, ComposeResult
from textual.widgets import Input, Select, Static

from budget_forecaster.core.types import Category
from budget_forecaster.tui.widgets.filter_bar import FilterBar


class FilterBarTestApp(App[None]):
    """Test app containing just a FilterBar (basic mode, no date/amount)."""

    def __init__(self) -> None:
        super().__init__()
        self.filter_changed_events: list[FilterBar.FilterChanged] = []
        self.filter_reset_count: int = 0

    def compose(self) -> ComposeResult:
        yield FilterBar()

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Track FilterChanged events."""
        self.filter_changed_events.append(event)

    def on_filter_bar_filter_reset(self, event: FilterBar.FilterReset) -> None:
        """Track FilterReset events."""
        _ = event
        self.filter_reset_count += 1


class FilterBarExtendedTestApp(App[None]):
    """Test app with FilterBar in extended mode (date + amount range)."""

    def __init__(self) -> None:
        super().__init__()
        self.filter_changed_events: list[FilterBar.FilterChanged] = []
        self.filter_reset_count: int = 0

    def compose(self) -> ComposeResult:
        yield FilterBar(show_date_range=True, show_amount_range=True)

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Track FilterChanged events."""
        self.filter_changed_events.append(event)

    def on_filter_bar_filter_reset(self, event: FilterBar.FilterReset) -> None:
        """Track FilterReset events."""
        _ = event
        self.filter_reset_count += 1


class TestFilterBarUnit:
    """Unit tests for FilterBar properties."""

    async def test_search_text_empty_returns_none(self) -> None:
        """Empty search input returns None."""
        app = FilterBarTestApp()
        async with app.run_test():
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.search_text is None

    async def test_category_blank_returns_none(self) -> None:
        """Blank category select returns None."""
        app = FilterBarTestApp()
        async with app.run_test():
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.category is None

    async def test_date_range_none_when_not_shown(self) -> None:
        """Date properties return None when date range is not shown."""
        app = FilterBarTestApp()
        async with app.run_test():
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.date_from is None
            assert filter_bar.date_to is None

    async def test_amount_range_none_when_not_shown(self) -> None:
        """Amount properties return None when amount range is not shown."""
        app = FilterBarTestApp()
        async with app.run_test():
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.min_amount is None
            assert filter_bar.max_amount is None


class TestFilterBarIntegration:
    """Integration tests using Textual test framework."""

    async def test_click_filter_posts_filter_changed(self) -> None:
        """Clicking Filter button posts FilterChanged message."""
        app = FilterBarTestApp()
        async with app.run_test() as pilot:
            await pilot.click("#filter-apply")
            assert len(app.filter_changed_events) == 1
            event = app.filter_changed_events[0]
            assert event.search_text is None
            assert event.category is None

    async def test_click_reset_posts_filter_reset(self) -> None:
        """Clicking Reset button posts FilterReset message."""
        app = FilterBarTestApp()
        async with app.run_test() as pilot:
            await pilot.click("#filter-reset")
            assert app.filter_reset_count == 1

    async def test_search_then_filter_includes_text(self) -> None:
        """Setting search text and clicking Filter includes search text."""
        app = FilterBarTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "carrefour"
            await pilot.click("#filter-apply")

            assert len(app.filter_changed_events) == 1
            assert app.filter_changed_events[0].search_text == "carrefour"

    async def test_enter_in_search_triggers_filter(self) -> None:
        """Pressing Enter in search input triggers FilterChanged."""
        app = FilterBarTestApp()
        async with app.run_test() as pilot:
            search_input = app.query_one("#filter-search", Input)
            search_input.value = "loyer"
            search_input.focus()
            await pilot.press("enter")

            assert len(app.filter_changed_events) == 1
            assert app.filter_changed_events[0].search_text == "loyer"

    async def test_reset_clears_search_input(self) -> None:
        """Reset clears the search input value."""
        app = FilterBarTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-search", Input).value = "test"
            await pilot.click("#filter-reset")

            filter_bar = app.query_one(FilterBar)
            assert filter_bar.search_text is None

    async def test_reset_clears_category_select(self) -> None:
        """Reset clears the category selection."""
        app = FilterBarTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-category", Select).value = Category.GROCERIES.name
            await pilot.click("#filter-reset")

            filter_bar = app.query_one(FilterBar)
            assert filter_bar.category is None

    async def test_category_property_returns_selected(self) -> None:
        """Category property returns the selected category."""
        app = FilterBarTestApp()
        async with app.run_test():
            app.query_one("#filter-category", Select).value = Category.GROCERIES.name

            filter_bar = app.query_one(FilterBar)
            assert filter_bar.category == Category.GROCERIES

    async def test_update_status_shows_filtered_count(self) -> None:
        """update_status displays filtered/total when they differ."""
        app = FilterBarTestApp()
        async with app.run_test():
            filter_bar = app.query_one(FilterBar)
            filter_bar.update_status(42, 459)

            status = app.query_one("#filter-status", Static)
            rendered = str(status.render())
            assert "42" in rendered
            assert "459" in rendered

    async def test_update_status_empty_when_equal(self) -> None:
        """update_status shows nothing when filtered equals total."""
        app = FilterBarTestApp()
        async with app.run_test():
            filter_bar = app.query_one(FilterBar)
            filter_bar.update_status(459, 459)

            status = app.query_one("#filter-status", Static)
            assert str(status.render()) == ""


class TestFilterBarExtended:
    """Tests for FilterBar with date and amount range inputs."""

    async def test_date_from_parses_valid_date(self) -> None:
        """Valid date string is parsed into a date object."""
        app = FilterBarExtendedTestApp()
        async with app.run_test():
            app.query_one("#filter-date-from", Input).value = "2025-01-15"
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.date_from == date(2025, 1, 15)

    async def test_date_to_parses_valid_date(self) -> None:
        """Valid date string is parsed into a date object."""
        app = FilterBarExtendedTestApp()
        async with app.run_test():
            app.query_one("#filter-date-to", Input).value = "2025-12-31"
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.date_to == date(2025, 12, 31)

    async def test_invalid_date_returns_none(self) -> None:
        """Invalid date string returns None."""
        app = FilterBarExtendedTestApp()
        async with app.run_test():
            app.query_one("#filter-date-from", Input).value = "not-a-date"
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.date_from is None

    async def test_empty_date_returns_none(self) -> None:
        """Empty date input returns None."""
        app = FilterBarExtendedTestApp()
        async with app.run_test():
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.date_from is None
            assert filter_bar.date_to is None

    async def test_min_amount_parses_valid_float(self) -> None:
        """Valid float string is parsed."""
        app = FilterBarExtendedTestApp()
        async with app.run_test():
            app.query_one("#filter-amount-min", Input).value = "-50.00"
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.min_amount == -50.00

    async def test_max_amount_parses_valid_float(self) -> None:
        """Valid float string is parsed."""
        app = FilterBarExtendedTestApp()
        async with app.run_test():
            app.query_one("#filter-amount-max", Input).value = "100"
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.max_amount == 100.0

    async def test_invalid_amount_returns_none(self) -> None:
        """Invalid amount string returns None."""
        app = FilterBarExtendedTestApp()
        async with app.run_test():
            app.query_one("#filter-amount-min", Input).value = "abc"
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.min_amount is None

    async def test_empty_amount_returns_none(self) -> None:
        """Empty amount input returns None."""
        app = FilterBarExtendedTestApp()
        async with app.run_test():
            filter_bar = app.query_one(FilterBar)
            assert filter_bar.min_amount is None
            assert filter_bar.max_amount is None

    async def test_filter_includes_date_and_amount(self) -> None:
        """FilterChanged includes date and amount values."""
        app = FilterBarExtendedTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-date-from", Input).value = "2025-01-01"
            app.query_one("#filter-date-to", Input).value = "2025-06-30"
            app.query_one("#filter-amount-min", Input).value = "-200"
            app.query_one("#filter-amount-max", Input).value = "-10"
            await pilot.click("#filter-apply")

            assert len(app.filter_changed_events) == 1
            event = app.filter_changed_events[0]
            assert event.date_from == date(2025, 1, 1)
            assert event.date_to == date(2025, 6, 30)
            assert event.min_amount == -200.0
            assert event.max_amount == -10.0

    async def test_filter_with_no_range_values(self) -> None:
        """FilterChanged has None for empty range fields."""
        app = FilterBarExtendedTestApp()
        async with app.run_test() as pilot:
            await pilot.click("#filter-apply")

            assert len(app.filter_changed_events) == 1
            event = app.filter_changed_events[0]
            assert event.date_from is None
            assert event.date_to is None
            assert event.min_amount is None
            assert event.max_amount is None

    async def test_reset_clears_date_inputs(self) -> None:
        """Reset clears date range inputs."""
        app = FilterBarExtendedTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-date-from", Input).value = "2025-01-01"
            app.query_one("#filter-date-to", Input).value = "2025-12-31"
            await pilot.click("#filter-reset")

            filter_bar = app.query_one(FilterBar)
            assert filter_bar.date_from is None
            assert filter_bar.date_to is None

    async def test_reset_clears_amount_inputs(self) -> None:
        """Reset clears amount range inputs."""
        app = FilterBarExtendedTestApp()
        async with app.run_test() as pilot:
            app.query_one("#filter-amount-min", Input).value = "-100"
            app.query_one("#filter-amount-max", Input).value = "0"
            await pilot.click("#filter-reset")

            filter_bar = app.query_one(FilterBar)
            assert filter_bar.min_amount is None
            assert filter_bar.max_amount is None

    async def test_enter_in_date_input_triggers_filter(self) -> None:
        """Pressing Enter in a date input triggers FilterChanged."""
        app = FilterBarExtendedTestApp()
        async with app.run_test() as pilot:
            date_input = app.query_one("#filter-date-from", Input)
            date_input.value = "2025-03-01"
            date_input.focus()
            await pilot.press("enter")

            assert len(app.filter_changed_events) == 1
            assert app.filter_changed_events[0].date_from == date(2025, 3, 1)
