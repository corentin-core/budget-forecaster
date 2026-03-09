"""Tests for TUI message communication (DataRefreshRequested, SaveRequested)."""

from textual.app import App, ComposeResult
from textual.widgets import OptionList

from budget_forecaster.core.types import Category
from budget_forecaster.tui.widgets.category_select import CategorySelect


class TestCategorySelectMessages:
    """Tests for CategorySelect widget message emission."""

    async def test_emits_category_selected_on_option_select(self) -> None:
        """Verify CategorySelected is emitted when an option is selected."""

        class CategorySelectTestApp(App[None]):
            """Test app that tracks category selection."""

            def __init__(self) -> None:
                super().__init__()
                self.selected_category: Category | None = None

            def compose(self) -> ComposeResult:
                """Compose the test app."""
                yield CategorySelect()

            def on_category_select_category_selected(
                self, event: CategorySelect.CategorySelected
            ) -> None:
                """Track selected category."""
                self.selected_category = event.category

        app = CategorySelectTestApp()
        async with app.run_test() as pilot:
            # Wait for mount and options to load
            await pilot.pause()

            # Focus the option list, move to first option, and select
            option_list = app.query_one("#category-list", OptionList)
            option_list.focus()
            await pilot.pause()
            # Highlight first option and select
            option_list.action_first()
            await pilot.pause()
            option_list.action_select()
            await pilot.pause()

            assert app.selected_category is not None
            assert isinstance(app.selected_category, Category)

    async def test_emits_category_selected_on_search_submit(self) -> None:
        """Verify CategorySelected is emitted when Enter is pressed in search."""

        class CategorySelectTestApp(App[None]):
            """Test app that tracks category selection."""

            def __init__(self) -> None:
                super().__init__()
                self.selected_category: Category | None = None

            def compose(self) -> ComposeResult:
                """Compose the test app."""
                yield CategorySelect()

            def on_category_select_category_selected(
                self, event: CategorySelect.CategorySelected
            ) -> None:
                """Track selected category."""
                self.selected_category = event.category

        app = CategorySelectTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()

            # Focus the search input and press Enter
            search_input = app.query_one("#category-search")
            search_input.focus()
            await pilot.press("enter")
            await pilot.pause()

            assert app.selected_category is not None
