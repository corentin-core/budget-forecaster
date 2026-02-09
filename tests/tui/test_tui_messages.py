"""Tests for TUI message communication (DataRefreshRequested, SaveRequested)."""

from datetime import date
from typing import Any
from unittest.mock import Mock

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import OptionList

from budget_forecaster.core.amount import Amount
from budget_forecaster.core.types import Category
from budget_forecaster.domain.operation.historic_operation import HistoricOperation
from budget_forecaster.services.application_service import ApplicationService
from budget_forecaster.tui.messages import SaveRequested
from budget_forecaster.tui.screens.operations import CategoryEditModal
from budget_forecaster.tui.widgets.category_select import CategorySelect


def make_test_operation(unique_id: int = 1) -> HistoricOperation:
    """Create a test operation."""
    return HistoricOperation(
        unique_id=unique_id,
        operation_date=date(2025, 1, 15),
        description="Test operation",
        amount=Amount(-100.00, "EUR"),
        category=Category.UNCATEGORIZED,
    )


class MessageTrackingApp(App[None]):
    """Base test app that tracks messages."""

    def __init__(self) -> None:
        super().__init__()
        self.received_messages: list[Any] = []

    def on_save_requested(self, event: SaveRequested) -> None:
        """Track SaveRequested messages."""
        self.received_messages.append(event)


class CategoryEditModalTestApp(MessageTrackingApp):
    """Test app for CategoryEditModal."""

    def __init__(self, app_service: ApplicationService | None = None) -> None:
        super().__init__()
        self._app_service = app_service
        self.modal_result: bool | None = None

    def compose(self) -> ComposeResult:
        yield Container()

    def open_modal(self) -> None:
        """Open the category edit modal."""
        self.push_screen(
            CategoryEditModal(operation_id=1, app_service=self._app_service),
            self._on_modal_closed,
        )

    def _on_modal_closed(self, result: bool | None) -> None:
        """Track modal result."""
        self.modal_result = result


class TestCategoryEditModalMessages:
    """Tests for CategoryEditModal message emission."""

    async def test_emits_save_requested_on_category_selection(self) -> None:
        """Verify SaveRequested is emitted when a category is selected."""
        # Create mock app service with proper return values
        mock_service = Mock(spec=ApplicationService)
        mock_service.categorize_operations = Mock()
        mock_service.get_operation_by_id = Mock(return_value=make_test_operation())
        mock_service.suggest_category = Mock(return_value=None)

        app = CategoryEditModalTestApp(app_service=mock_service)
        async with app.run_test() as pilot:
            # Open the modal
            app.open_modal()
            await pilot.pause()

            # The modal is on the screen stack - query from the active screen
            modal = app.screen
            option_list = modal.query_one("#category-list", OptionList)
            option_list.focus()
            await pilot.pause()
            # Highlight first option and select
            option_list.action_first()
            await pilot.pause()
            option_list.action_select()
            await pilot.pause()

            # Verify SaveRequested was emitted
            save_messages = [
                m for m in app.received_messages if isinstance(m, SaveRequested)
            ]
            assert len(save_messages) == 1, "Expected one SaveRequested message"

    async def test_no_save_requested_on_cancel(self) -> None:
        """Verify SaveRequested is NOT emitted when modal is cancelled."""
        app = CategoryEditModalTestApp(app_service=None)
        async with app.run_test() as pilot:
            # Open the modal
            app.open_modal()
            await pilot.pause()

            # Cancel with escape
            await pilot.press("escape")
            await pilot.pause()

            # Verify no SaveRequested was emitted
            save_messages = [
                m for m in app.received_messages if isinstance(m, SaveRequested)
            ]
            assert len(save_messages) == 0, "Expected no SaveRequested on cancel"
            assert app.modal_result is False

    async def test_modal_dismisses_with_true_on_selection(self) -> None:
        """Verify modal dismisses with True when category is selected."""
        mock_service = Mock(spec=ApplicationService)
        mock_service.categorize_operations = Mock()
        mock_service.get_operation_by_id = Mock(return_value=make_test_operation())
        mock_service.suggest_category = Mock(return_value=None)

        app = CategoryEditModalTestApp(app_service=mock_service)
        async with app.run_test() as pilot:
            app.open_modal()
            await pilot.pause()

            # The modal is on the screen stack - query from the active screen
            modal = app.screen
            option_list = modal.query_one("#category-list", OptionList)
            option_list.focus()
            await pilot.pause()
            # Highlight first option and select
            option_list.action_first()
            await pilot.pause()
            option_list.action_select()
            await pilot.pause()

            assert app.modal_result is True


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
