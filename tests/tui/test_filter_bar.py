"""Tests for FilterBar widget."""

from textual.app import App, ComposeResult
from textual.widgets import Input, Select, Static

from budget_forecaster.core.types import Category
from budget_forecaster.tui.widgets.filter_bar import FilterBar


class FilterBarTestApp(App[None]):
    """Test app containing just a FilterBar."""

    def __init__(self) -> None:
        super().__init__()
        self.filter_changed_events: list[FilterBar.FilterChanged] = []
        self.filter_reset_count: int = 0

    def compose(self) -> ComposeResult:
        yield FilterBar()

    def on_filter_bar_filter_changed(self, event: FilterBar.FilterChanged) -> None:
        """Track FilterChanged events."""
        self.filter_changed_events.append(event)

    def on_filter_bar_filter_reset(self, _event: FilterBar.FilterReset) -> None:
        """Track FilterReset events."""
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
